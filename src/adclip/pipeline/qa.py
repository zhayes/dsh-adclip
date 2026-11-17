"""Minimal QA checks for the first slice."""
from __future__ import annotations

import os
import re
from typing import Any

from .. import params, store
from ..media import asr, ffmpeg


def check(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    advanced = params.merged_advanced(run.advanced)
    final = store.run_artifact(run_id, "final.mp4")
    facts = ffmpeg.probe(final)
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    selection = getattr(run, "selection", None) or {}
    source_duration = (skeleton.get("source") or {}).get("duration_s")
    target = float(source_duration or advanced.get("duration") or 12)
    checks = []

    def add(cid: str, label: str, status: str, value: Any, note: str = "") -> None:
        checks.append({"id": cid, "label": label, "status": status, "value": value, "note": note})

    delta = round(float(facts["duration_s"]) - target, 2)
    add("duration", "时长", "pass" if abs(delta) <= max(0.5, target * 0.1) else "warn", {"final_s": facts["duration_s"], "target_s": target, "delta_s": delta})
    expected_aspect = str((skeleton.get("source") or {}).get("aspect") or advanced.get("aspect") or "9:16")
    actual_aspect = "9:16" if facts.get("height", 0) > facts.get("width", 0) * 1.15 else ("16:9" if facts.get("width", 0) > facts.get("height", 0) * 1.15 else "1:1")
    add("aspect", "画幅", "pass" if actual_aspect == expected_aspect else "warn", {"width": facts.get("width"), "height": facts.get("height"), "expected": expected_aspect, "actual": actual_aspect})
    add("audio", "音轨", "pass" if facts.get("has_audio") else "fail", {"has_audio": facts.get("has_audio")})
    srt = store.run_artifact(run_id, "subtitles.srt")
    if str(advanced.get("subtitle") or "off") == "sidecar":
        add("subtitles", "字幕", "pass" if srt.is_file() and srt.stat().st_size > 0 else "warn", {"path": store.rel_to_data(srt)})
    else:
        add("subtitles", "字幕", "pass", {"enabled": False, "path": None}, "未启用（按配置）")
    storyboard = store.read_json(store.run_dir(run_id) / "artifacts" / "storyboard.json", {}) or {}
    beats = storyboard.get("segments") or []
    add("segments", "分镜", "pass" if beats else "warn", {"count": len(beats)})
    analysis = skeleton.get("analysis") or {}
    add(
        "analysis",
        "参考片拆解",
        "pass" if analysis and not analysis.get("degraded") else "warn",
        {"mode": analysis.get("mode"), "model": analysis.get("model"), "degraded": bool(analysis.get("degraded"))},
        str(analysis.get("reason") or ""),
    )
    source_id = (run.inputs or {}).get("reference_asset_id")
    if source_id:
        try:
            source = store.asset_media_path(str(source_id))
            source_facts = ffmpeg.probe(source)
            if os.environ.get("ADCLIP_TEST_MODE", "").strip() == "1":
                source_cuts, final_cuts = [], []
            else:
                source_cuts = ffmpeg.detect_cuts(source, float(source_facts.get("duration_s") or 0))
                final_cuts = ffmpeg.detect_cuts(final, float(facts.get("duration_s") or 0))
            delta = abs(len(source_cuts) - len(final_cuts))
            add(
                "structure",
                "结构",
                "pass" if delta <= max(1, int(round(len(source_cuts) * 0.5))) else "warn",
                {"reference_cuts": len(source_cuts), "final_cuts": len(final_cuts), "duration_delta_s": round(float(facts["duration_s"]) - float(source_facts["duration_s"]), 2)},
                "切点/时长与参考片对比，需人工复核人物/商品替换",
            )
        except Exception as exc:  # noqa: BLE001
            add("structure", "结构", "warn", {"error": str(exc)[:160]}, "无法计算结构偏差")
    result_meta = run.result or {}
    if selection.get("mode") == "h3_reference":
        add(
            "audio_source",
            "口播来源",
            "pass" if result_meta.get("audio_source") else "warn",
            {
                "audio_mode": advanced.get("audio_mode") or "regenerate",
                "audio_source": result_meta.get("audio_source") or "",
            },
            "参考片原声" if result_meta.get("audio_source") == "reference" else "H3 新生成",
        )
    script_doc = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    if (
        run.scenario == "viral-remake"
        and selection.get("mode") == "h3_reference"
        and str(advanced.get("audio_mode") or "regenerate") != "preserve"
        and asr.available()
    ):
        try:
            words = asr.transcribe_words(final)
            transcript = "".join(str(item.get("text") or "") for item in words).strip()
            overlaps = []
            for index in range(1, len(words)):
                previous, current = words[index - 1], words[index]
                if float(current.get("start_s") or 0) < float(previous.get("end_s") or 0) - 0.2:
                    overlaps.append({
                        "at_s": current.get("start_s"),
                        "previous": previous.get("text"),
                        "current": current.get("text"),
                    })
            add(
                "audio_overlap",
                "口播重叠",
                "warn" if overlaps else "pass",
                {"count": len(overlaps), "examples": overlaps[:3]},
                "检测到词级时间重叠，需人工听感复核" if overlaps else "",
            )
            script_lines = " ".join(
                str((line or {}).get("text") or "")
                for beat in (script_doc.get("beats") or [])
                for line in (beat.get("lines") or [])
            )
            expected = str((run.inputs or {}).get("brief") or "") + " " + script_lines
            tokens = re.findall(r"[0-9]+|[一二三四五六七八九十百千万两]+", expected)
            tokens = [token for token in tokens if len(token) >= 1]
            missing_numbers = [token for token in tokens if token not in transcript][:5]
            product = str((run.inputs or {}).get("brief") or "").split("，")[0].strip()[:8]
            product_missing = bool(product) and product[:2] not in transcript
            add(
                "audio_copy",
                "口播",
                "warn" if (missing_numbers or product_missing) else "pass",
                {"transcript": transcript[:240], "missing_numbers": missing_numbers, "product": product, "product_missing": product_missing},
                "口播未完全命中 brief/脚本，需人工复核" if (missing_numbers or product_missing) else "",
            )
        except Exception as exc:  # noqa: BLE001
            add("audio_copy", "口播", "warn", {"error": str(exc)[:160]}, "无法转写口播，需人工复核")
    if run.scenario == "viral-remake" and selection.get("mode") == "generation_fallback" and (script_doc.get("source") or {}).get("degraded"):
        add("script", "台词", "warn", {"degraded": True}, "文字模型不可用，台词未由模型生成；重试可补")
    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    report = {
        "version": 1,
        "checks": checks,
        "summary": {"pass": len(checks) - len(failed) - len(warned), "warn": len(warned), "fail": len(failed), "shippable": not failed},
        "demo": bool(run.demo),
    }
    store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "qa.json", report)
    return report
