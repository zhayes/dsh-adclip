"""Post: normalize, SRT, optional loudness, final artifact."""
from __future__ import annotations

import os
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
    warnings: list[str] = []
    # Keep the clip length the model delivered. Product names and prices have
    # different character counts, so the model's pacing drifts from the
    # reference; cutting back to the reference duration is exactly what lopped
    # the end off "现在只要七十多". Only frame size and fps are normalized.
    ffmpeg.normalize(raw, final, width=width, height=height, fps=int(advanced.get("fps") or 30))
    if duration:
        final_s = float(ffmpeg.probe(final).get("duration_s") or 0)
        if abs(final_s - duration) > 0.3:
            warnings.append(
                f"成片 {final_s:.2f}s（参考片 {duration:.2f}s）：按模型实际输出保留，未做时长裁剪"
            )
    audio_source = None
    audio_mode = str(advanced.get("audio_mode") or "regenerate")
    replace_scope = str(advanced.get("replace_scope") or "both")
    if selection.get("mode") == "h3_reference":
        audio_source = "h3"
        if audio_mode == "preserve":
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
    elif run.scenario == "viral-remake" and audio_mode == "preserve" and replace_scope in {"person", "none"}:
        # Only person replacement may keep the original voice: a new product name
        # or price would otherwise survive in the old audio track.
        ref_id = (run.inputs or {}).get("reference_asset_id")
        try:
            reference = store.asset_media_path(str(ref_id)) if ref_id else None
            if reference and ffmpeg.probe(reference).get("has_audio"):
                temp = final.with_suffix(".audio.mp4")
                ffmpeg.replace_audio(final, reference, temp)
                os.replace(temp, final)
                audio_source = "reference"
                warnings.append("已替换回参考片原声；换人后口型可能有轻微偏差，请人工复核")
            else:
                warnings.append("参考片没有可用音轨，保留生成的音频")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"替换参考音轨失败，保留生成音频：{type(exc).__name__}: {exc}"[:240])
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
