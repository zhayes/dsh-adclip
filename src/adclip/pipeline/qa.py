"""Minimal QA checks for the first slice."""
from __future__ import annotations

from typing import Any

from .. import params, store
from ..media import ffmpeg


def check(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    advanced = params.merged_advanced(run.advanced)
    final = store.run_artifact(run_id, "final.mp4")
    facts = ffmpeg.probe(final)
    target = float(advanced.get("duration") or 12)
    checks = []

    def add(cid: str, label: str, status: str, value: Any, note: str = "") -> None:
        checks.append({"id": cid, "label": label, "status": status, "value": value, "note": note})

    delta = round(float(facts["duration_s"]) - target, 2)
    add("duration", "时长", "pass" if abs(delta) <= max(0.5, target * 0.1) else "warn", {"final_s": facts["duration_s"], "target_s": target, "delta_s": delta})
    add("aspect", "画幅", "pass" if facts.get("width") and facts.get("height") else "fail", {"width": facts.get("width"), "height": facts.get("height")})
    add("audio", "音轨", "pass" if facts.get("has_audio") else "fail", {"has_audio": facts.get("has_audio")})
    srt = store.run_artifact(run_id, "subtitles.srt")
    add("subtitles", "字幕", "pass" if srt.is_file() and srt.stat().st_size > 0 else "warn", {"path": store.rel_to_data(srt)})
    storyboard = store.read_json(store.run_dir(run_id) / "artifacts" / "storyboard.json", {}) or {}
    beats = storyboard.get("segments") or []
    add("segments", "分镜", "pass" if beats else "warn", {"count": len(beats)})
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
