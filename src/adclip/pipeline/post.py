"""Post: normalize, SRT, optional loudness, final artifact."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import params, store
from ..media import ffmpeg, subtitles


def post(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    advanced = params.merged_advanced(run.advanced)
    script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    raw = store.run_artifact(run_id, "provider_raw.mp4")
    if not raw.is_file():
        raw = store.run_artifact(run_id, "demo_raw.mp4")
    if not raw.is_file():
        raise FileNotFoundError("generated clip missing")
    width, height = params.size_for(str(advanced.get("aspect") or "9:16"), str(advanced.get("resolution") or "720p"))
    final = store.run_artifact(run_id, "final.mp4")
    ffmpeg.normalize(raw, final, width=width, height=height, fps=int(advanced.get("fps") or 30))
    # Subtitles are a sidecar SRT, never burned in (the ffmpeg build has no
    # libass/drawtext). The run's own setting decides whether we deliver one.
    srt_path = store.run_artifact(run_id, "subtitles.srt")
    if str(advanced.get("subtitle") or "off") == "sidecar":
        subtitles.write_srt(script, srt_path)
        srt_value = store.rel_to_data(srt_path)
    else:
        srt_path.unlink(missing_ok=True)
        srt_value = None
    return {
        "video": store.rel_to_data(final),
        "srt": srt_value,
        "width": width,
        "height": height,
        "duration_s": ffmpeg.probe(final)["duration_s"],
    }
