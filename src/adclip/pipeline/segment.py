"""Storyboard derivation from the final clip and the script."""
from __future__ import annotations

from typing import Any

from .. import params, store
from ..media import ffmpeg


def _segments_for(run: Any, skeleton: dict[str, Any], script: dict[str, Any], final_s: float) -> list[dict[str, Any]]:
    advanced = params.merged_advanced(run.advanced)
    # The storyboard describes the clip that was actually produced, so the
    # probed final duration wins over the requested one. Otherwise the segment
    # times and the prompt's dialogue times use different timelines.
    target = float(final_s or advanced.get("duration") or 6)
    source_s = float((skeleton.get("source") or {}).get("duration_s") or target)
    scale = (target / source_s) if source_s > 0 else 1.0
    script_beats = {row.get("id"): row for row in script.get("beats") or []}
    beats = skeleton.get("beats") or []
    rows: list[dict[str, Any]] = []
    for i, beat in enumerate(beats):
        start = float(beat.get("start_s") or 0) * scale
        end = float(beat.get("end_s") or target) * scale
        start = min(max(0.0, start), max(0.0, target - 0.3))
        end = min(max(start + 0.3, end), target)
        line = " / ".join(str(x.get("text") or "") for x in (script_beats.get(beat.get("id")) or {}).get("lines") or [])
        visual = beat.get("visual") or {}
        cast = [
            {"key": str(item.get("key") or ""), "role": str(item.get("role") or ""), "description": str(item.get("description") or "")}
            for item in (visual.get("cast") or [])
            if isinstance(item, dict) and str(item.get("description") or "").strip()
        ]
        rows.append({
            "id": f"s{len(rows)}",
            "index": len(rows),
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "function": beat.get("function") or "beat",
            "source": "one_shot_slice",
            "thumbnail": None,
            "dialogue": line,
            "action": (script_beats.get(beat.get("id")) or {}).get("shot") or visual.get("action") or "",
            "scene": str(visual.get("scene") or ""),
            "background": str(visual.get("background") or ""),
            "lighting": str(visual.get("lighting") or ""),
            "expression": str(visual.get("expression") or ""),
            "cast": cast,
            "product": str((visual.get("product") or {}).get("name") or "") if isinstance(visual.get("product"), dict) else "",
            "status": "ok",
            "asset_id": None,
            "take": 1,
            "note": "demo analysis segment",
        })
    if not rows:
        rows = [{
            "id": "s0", "index": 0, "start_s": 0.0, "end_s": round(target, 3), "function": "beat",
            "source": "one_shot_slice", "thumbnail": None, "dialogue": "", "action": "",
            "scene": "", "background": "", "lighting": "", "expression": "", "cast": [],
            "product": "", "status": "ok", "asset_id": None, "take": 1, "note": "demo",
        }]
    return rows


def build_storyboard(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    final = store.run_artifact(run_id, "final.mp4")
    final_s = 0.0
    if final.is_file():
        try:
            final_s = float(ffmpeg.probe(final)["duration_s"])
        except Exception:
            pass
    rows = _segments_for(run, skeleton, script, final_s)
    # Show the same time slots the prompt hands the model, so a line that cannot
    # be spoken before the cut is visible in the UI instead of only in the video.
    if run.scenario == "viral-remake":
        try:
            from . import remake_spec

            spec = remake_spec.build_spec(run, skeleton, script)
            timed = [shot.get("timed_lines") or [] for shot in spec.get("shots") or []]
            for index, seg in enumerate(rows):
                if index < len(timed) and timed[index]:
                    seg["lines"] = timed[index]
        except Exception:  # noqa: BLE001
            pass
    for i, seg in enumerate(rows):
        if final.is_file():
            thumb = store.run_artifact(run_id, f"storyboard/seg_{i}.jpg")
            try:
                ffmpeg.extract_frame(final, (float(seg["start_s"]) + float(seg["end_s"])) / 2, thumb, width=360)
                seg["thumbnail"] = store.rel_to_data(thumb)
            except Exception:
                pass
    payload = {"version": 1, "generation_mode": run.generation_mode, "segments": rows}
    store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "storyboard.json", payload)
    return payload
