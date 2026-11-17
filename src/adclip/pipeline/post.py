"""Post: normalize, SRT, optional loudness, final artifact."""
from __future__ import annotations

import os
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
    selection = getattr(run, "selection", None) or {}
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    aspect = str(advanced.get("aspect") or "9:16")
    duration = None
    if run.scenario == "viral-remake":
        source = skeleton.get("source") or {}
        aspect = str(source.get("aspect") or aspect)
        try:
            duration = float(source.get("duration_s") or 0) or None
        except (TypeError, ValueError):
            duration = None
    width, height = params.size_for(aspect, str(advanced.get("resolution") or "720p"))
    final = store.run_artifact(run_id, "final.mp4")
    ffmpeg.normalize(raw, final, width=width, height=height, fps=int(advanced.get("fps") or 30), duration=duration)
    audio_source = None
    warnings: list[str] = []
    if selection.get("mode") == "h3_reference":
        audio_source = "h3"
        if str(advanced.get("audio_mode") or "regenerate") == "preserve":
            ref_id = (run.inputs or {}).get("reference_asset_id")
            try:
                reference = store.asset_media_path(str(ref_id)) if ref_id else None
                if reference and ffmpeg.probe(reference).get("has_audio"):
                    temp = final.with_suffix(".audio.mp4")
                    ffmpeg.replace_audio(final, reference, temp)
                    os.replace(temp, final)
                    audio_source = "reference"
                else:
                    warnings.append("参考片没有可用音轨，保留 H3 生成音频")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"替换参考音轨失败，保留 H3 音频：{type(exc).__name__}: {exc}"[:240])
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
        "audio_source": audio_source,
        "warnings": warnings,
    }
