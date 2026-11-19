"""Minimal QA checks for the first slice."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .. import params, requirements, store
from ..media import asr, ffmpeg, similarity, vision
from . import remake_spec, timing


SCORE_WEIGHTS = {
    "structure": 0.30,
    "timing": 0.10,
    "visual": 0.20,
    "dialogue": 0.25,
    "audio": 0.15,
}

# Per-rung acceptance lines. A weaker rung is not a failure when it clears its
# own bar; it is a failure when it cannot even do that.
SCORE_THRESHOLDS = {
    "h3_reference": 80,
    "reference": 65,
    "keyframe": 45,
    "generation": 45,
}


def _check_value(by_id: dict[str, dict[str, Any]], check_id: str) -> dict[str, Any]:
    item = by_id.get(check_id) or {}
    value = item.get("value")
    return value if isinstance(value, dict) else {}


def _remake_score(checks: list[dict[str, Any]], *, final: Any, source: Any) -> dict[str, Any] | None:
    """One 0–100 replication score with per-dimension parts.

    Parts we cannot measure (for example spoken copy while ASR is unavailable)
    are dropped from the total and reported in `unchecked`, instead of being
    scored as a pass.
    """
    by_id = {str(item.get("id")): item for item in checks}
    parts: dict[str, float] = {}

    structure = _check_value(by_id, "structure")
    reference_cuts = structure.get("reference_cuts")
    final_cuts = structure.get("final_cuts")
    if isinstance(reference_cuts, int) and isinstance(final_cuts, int):
        if reference_cuts == 0 and final_cuts == 0:
            parts["structure"] = 1.0
        else:
            parts["structure"] = max(0.0, 1.0 - abs(final_cuts - reference_cuts) / max(1, reference_cuts))

    timing: list[float] = []
    duration = _check_value(by_id, "duration")
    if duration:
        target = float(duration.get("target_s") or 0) or 1.0
        delta = abs(float(duration.get("delta_s") or 0.0))
        timing.append(max(0.0, 1.0 - min(1.0, delta / max(0.5, target * 0.25))))
    aspect = by_id.get("aspect") or {}
    if aspect:
        timing.append(1.0 if aspect.get("status") == "pass" else 0.0)
    if timing:
        parts["timing"] = sum(timing) / len(timing)

    if source and Path(str(source)).is_file() and Path(str(final)).is_file():
        span = min(float(duration.get("target_s") or 0), float(duration.get("final_s") or 0))
        if span <= 0.5:
            span = min(float(_probe_duration(source)), float(_probe_duration(final)))
        if span > 0.5:
            try:
                visual = similarity.frame_similarity(source, final, [span * 0.2, span * 0.5, span * 0.8])
            except Exception:
                visual = None
            if visual is not None:
                parts["visual"] = float(visual)

    copy = by_id.get("audio_copy")
    if copy:
        parts["dialogue"] = 1.0 if copy.get("status") == "pass" else 0.4

    audio = by_id.get("audio") or {}
    if audio:
        parts["audio"] = 1.0 if audio.get("status") == "pass" else 0.0
        if (by_id.get("audio_overlap") or {}).get("status") == "warn":
            parts["audio"] *= 0.6

    used = {key: weight for key, weight in SCORE_WEIGHTS.items() if key in parts}
    total_weight = sum(used.values())
    if not used or total_weight <= 0:
        return None
    total = sum(parts[key] * weight for key, weight in used.items()) / total_weight
    return {
        "total": round(100 * total),
        "parts": {key: round(value, 3) for key, value in parts.items()},
        "weights": {key: round(weight / total_weight, 3) for key, weight in used.items()},
        "unchecked": sorted(set(SCORE_WEIGHTS) - set(parts)),
    }


def _requirement_checks(run: Any, advanced: dict[str, Any], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the brief asked for and whether the output can be checked for it.

    Only spoken requirements can be verified without another paid vision call;
    the rest are reported as unchecked instead of being counted as a pass.
    """
    req = requirements.derive(str((run.inputs or {}).get("brief") or ""), advanced)
    transcript = "".join(str(item.get("text") or "") for item in words).strip()
    transcript_digits = re.sub(r"\D", "", transcript)
    delivered = bool(words)
    checks: list[dict[str, Any]] = []
    prices = [str(value).strip() for value in req.get("prices") or [] if str(value).strip()]
    if prices:
        missing = [value for value in prices if re.sub(r"\D", "", value) not in transcript_digits]
        checks.append({
            "id": "req_price",
            "label": "要求·价格",
            "status": "pass" if (delivered and not missing) else "warn",
            "value": {"prices": prices, "missing": missing, "verified": delivered},
            "note": "" if (delivered and not missing) else ("口播里没听到价格" if delivered else "无法转写口播，未校验价格"),
        })
    product = str(req.get("product_hint") or "").strip()
    if product:
        hit = delivered and product[:2] in transcript
        checks.append({
            "id": "req_product",
            "label": "要求·商品名",
            "status": "pass" if hit else "warn",
            "value": {"product": product, "verified": delivered},
            "note": "" if hit else ("口播里没听到商品名" if delivered else "无法转写口播，未校验商品名"),
        })
    for index, line in enumerate(req.get("quoted") or []):
        hit = delivered and line[:4] in transcript
        checks.append({
            "id": f"req_line_{index}",
            "label": "要求·指定台词",
            "status": "pass" if hit else "warn",
            "value": {"text": line, "verified": delivered},
            "note": "" if hit else ("指定台词未出现在口播里" if delivered else "无法转写口播，未校验指定台词"),
        })
    if req.get("clean_text"):
        checks.append({
            "id": "req_clean_text",
            "label": "要求·去文字",
            "status": "warn",
            "value": {"verified": False},
            "note": "画面文字需人工核对，未自动校验",
        })
    return checks


def _dialogue_timing(run: Any, skeleton: dict[str, Any], script_doc: dict[str, Any], duration: float) -> dict[str, Any] | None:
    """Does every line physically fit the slot the prompt gave it?

    A slot shorter than the line means the clip cuts away mid-sentence, which
    is exactly the "视频结束了台词还没念完" symptom.
    """
    try:
        spec = remake_spec.build_spec(run, skeleton, script_doc)
    except Exception:  # noqa: BLE001
        return None
    rows = [row for shot in spec.get("shots") or [] for row in shot.get("timed_lines") or []]
    if not rows:
        return None
    tight = []
    chars = 0
    for row in rows:
        text = str(row.get("text") or "")
        chars += len(text)
        span = float(row.get("end_s") or 0) - float(row.get("start_s") or 0)
        need = timing.speak_seconds(text, timing.MAX_CPS)
        if span + 1e-6 < need:
            tight.append({"text": text[:24], "slot_s": round(span, 2), "need_s": round(need, 2)})
    cps = round(chars / max(0.5, duration), 2) if duration else None
    return {"lines": len(rows), "chars": chars, "cps": cps, "tight": tight[:4], "tight_count": len(tight)}


def _text_overlay(run_id: str, final: Any, duration: float) -> dict[str, Any] | None:
    """Sample the output with the vision ladder and report burned-in text.

    Providers do add their own overlays, and a generation model sometimes paints
    a caption on its own. Prompt wording cannot guarantee otherwise, so this is
    measured and reported instead of assumed.
    """
    if os.environ.get("ADSTUDIO_QA_VISION", "1") == "0" or not vision.available() or not Path(str(final)).is_file():
        return None
    points = [0.2, 0.7]
    frames: list[dict[str, Any]] = []
    for index, ratio in enumerate(points):
        path = store.run_artifact(run_id, f"qa/frame_{index}.jpg")
        try:
            ffmpeg.extract_frame(final, max(0.1, ratio * max(0.5, duration)), path, width=640)
        except Exception:  # noqa: BLE001
            continue
        at = round(ratio * max(0.5, duration), 2)
        frames.append({"id": f"q{index}", "path": str(path), "start_s": at, "end_s": round(at + 0.1, 2)})
    if not frames:
        return None
    rows = vision.analyze_frames(frames, max_frames=len(frames))
    if not rows:
        return None
    found = []
    for frame in frames:
        text = str((rows.get(str(frame["id"])) or {}).get("on_screen_text") or "").strip()
        if text:
            found.append({"at_s": frame["start_s"], "text": text[:60]})
    return {"frames": len(frames), "found": found, "model": str(getattr(vision, "LAST_MODEL", "") or "")}


def _probe_duration(path: Any) -> float:
    try:
        return float(ffmpeg.probe(path)["duration_s"])
    except Exception:  # noqa: BLE001
        return 0.0


def _mode(selection: dict[str, Any]) -> str:
    """Execution mode, tolerating selections written before the rung rename."""
    mode = str(selection.get("mode") or "")
    return {"reference_fallback": "reference", "generation_fallback": "generation"}.get(mode, mode)


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
    # Post keeps whatever length the model delivered (its pacing drifts with the
    # product copy), so compare against the duration we asked the provider for,
    # not the reference's exact length.
    requested = (selection.get("params") or {}).get("duration")
    try:
        target = float(requested) if requested not in (None, "", "reference") else None
    except (TypeError, ValueError):
        target = None
    target = target or float(source_duration or advanced.get("duration") or 12)
    checks = []

    def add(cid: str, label: str, status: str, value: Any, note: str = "") -> None:
        checks.append({"id": cid, "label": label, "status": status, "value": value, "note": note})

    delta = round(float(facts["duration_s"]) - target, 2)
    add("duration", "时长", "pass" if abs(delta) <= max(0.5, target * 0.1) else "warn", {"final_s": facts["duration_s"], "target_s": target, "reference_s": source_duration, "delta_s": delta})
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
    mode = _mode(selection)
    if mode == "h3_reference":
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
    words: list[dict[str, Any]] = []
    if (
        run.scenario == "viral-remake"
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
    if run.scenario == "viral-remake" and mode in {"generation", "reference", "keyframe"} and (script_doc.get("source") or {}).get("degraded"):
        add("script", "台词", "warn", {"degraded": True}, "文字模型不可用，台词未由模型生成；重试可补")
    timing_info = _dialogue_timing(run, skeleton, script_doc, float(facts.get("duration_s") or 0)) if run.scenario == "viral-remake" else None
    if timing_info:
        tight = int(timing_info.get("tight_count") or 0)
        slow = float(timing_info.get("cps") or 0) > timing.MAX_CPS
        add(
            "dialogue_timing",
            "台词时长",
            "warn" if (tight or slow) else "pass",
            timing_info,
            "有台词在分配的时间里念不完，会被切掉；缩短台词或降低语速要求" if tight
            else ("整体语速超过每秒 %.1f 字，模型容易漏句" % timing.MAX_CPS if slow else ""),
        )
    overlay = _text_overlay(run_id, final, float(facts.get("duration_s") or 0)) if run.scenario == "viral-remake" else None
    if overlay is not None:
        found = overlay.get("found") or []
        add(
            "text_overlay",
            "画面文字",
            "warn" if found else "pass",
            overlay,
            "画面里出现了文字/标签，可能是模型自绘的标注；需要干净画面建议再生成" if found else "抽样帧未发现叠加文字",
        )
    requirement_checks = _requirement_checks(run, advanced, words) if run.scenario == "viral-remake" else []
    checks.extend(requirement_checks)
    score = None
    if run.scenario == "viral-remake" and source_id:
        try:
            score = _remake_score(checks, final=final, source=store.asset_media_path(str(source_id)))
        except Exception:  # noqa: BLE001
            score = None
    if score:
        score["mode"] = mode
        threshold = SCORE_THRESHOLDS.get(mode)
        score["threshold"] = threshold
        if threshold:
            score["passed"] = score["total"] >= threshold
            weakest = sorted(score["parts"].items(), key=lambda item: item[1])[:2]
            add(
                "remake_score",
                "复刻度",
                "pass" if score["passed"] else "warn",
                {"total": score["total"], "threshold": threshold, "weakest": [name for name, _ in weakest]},
                "达到本档及格线" if score["passed"] else "低于本档及格线，建议再生成或先编辑分镜",
            )
    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    report = {
        "version": 1,
        "checks": checks,
        "summary": {"pass": len(checks) - len(failed) - len(warned), "warn": len(warned), "fail": len(failed), "shippable": not failed},
        "demo": bool(run.demo),
    }
    if score:
        report["remake_score"] = score
    if run.scenario == "viral-remake":
        report["requirement_check"] = requirement_checks
        report["asr_available"] = asr.available()
    store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "qa.json", report)
    return report
