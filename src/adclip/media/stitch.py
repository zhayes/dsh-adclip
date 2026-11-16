"""FFmpeg stitching: normalize clips, concat, optional insert plan.

The first slice supports hard cuts, audio keep/mute, and black/crop/blur fit.
Crossfade is reported as unsupported rather than silently ignored.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from . import ffmpeg


def _fit_filter(index: int, width: int, height: int, fit: str) -> tuple[str, str]:
    """Return (filter start, output label) for one video stream."""
    src = f"[{index}:v]"
    if fit == "crop":
        return (
            f"{src}trim=start={{start}}:end={{end}},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"fps=30,format=yuv420p",
            f"[v{index}]",
        )
    if fit == "blur_pad":
        return (
            f"{src}trim=start={{start}}:end={{end}},setpts=PTS-STARTPTS,split=2[bg{index}][fg{index}];"
            f"[bg{index}]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:2[bgf{index}];"
            f"[fg{index}]scale={width}:{height}:force_original_aspect_ratio=decrease[fgf{index}];"
            f"[bgf{index}][fgf{index}]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p",
            f"[v{index}]",
        )
    return (
        f"{src}trim=start={{start}}:end={{end}},setpts=PTS-STARTPTS,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x111827,fps=30,format=yuv420p",
        f"[v{index}]",
    )


def plan(clips: list[dict[str, Any]], *, width: int, height: int, fit: str = "blur_pad", transition: str = "cut", audio: str = "keep") -> dict[str, Any]:
    rows = []
    total = 0.0
    warnings: list[str] = []
    for i, clip in enumerate(clips):
        facts = ffmpeg.probe(clip["path"])
        start = max(0.0, float(clip.get("in_s") or 0.0))
        end = float(clip.get("out_s") or facts["duration_s"])
        end = min(end, facts["duration_s"])
        if end <= start:
            raise ValueError(f"clip {i} has no duration")
        length = end - start
        total += length
        rows.append({"index": i, "path": clip["path"], "in_s": start, "out_s": end, "len_s": round(length, 3), "has_audio": facts.get("has_audio")})
    if transition not in {"cut"}:
        warnings.append(f"转场 {transition} 暂未实现，已按硬切输出")
    if audio not in {"keep", "mute"}:
        warnings.append(f"音频策略 {audio} 暂未实现，已按 keep 输出")
    return {"clips": rows, "duration_s": round(total, 3), "width": width, "height": height, "fit": fit, "transition": "cut", "audio": audio if audio in {"keep", "mute"} else "keep", "warnings": warnings}


def execute(plan_data: dict[str, Any], target: str | Path) -> Path:
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    clips = plan_data["clips"]
    width, height = int(plan_data["width"]), int(plan_data["height"])
    fit = plan_data.get("fit") or "black_pad"
    audio_mode = plan_data.get("audio") or "keep"
    if not clips:
        raise ValueError("no clips")
    tmpdir = Path(tempfile.mkdtemp(prefix="adstudio-stitch-"))
    inputs: list[str] = []
    with_audio: list[Path] = []
    try:
        for i, clip in enumerate(clips):
            src = Path(clip["path"])
            if clip.get("has_audio"):
                with_audio.append(src)
            else:
                fixed = tmpdir / f"clip_{i}.mp4"
                ffmpeg.ensure_audio(src, fixed)
                with_audio.append(fixed)
            inputs.extend(["-i", str(with_audio[-1])])

        filters: list[str] = []
        labels: list[str] = []
        for i, clip in enumerate(clips):
            start, end = float(clip["in_s"]), float(clip["out_s"])
            vfilter, vlabel = _fit_filter(i, width, height, fit)
            vfilter = vfilter.format(start=f"{start:.3f}", end=f"{end:.3f}")
            filters.append(f"{vfilter}{vlabel}")
            if audio_mode == "keep":
                filters.append(
                    f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                    f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
                )
                labels.append(f"[v{i}][a{i}]")
            else:
                labels.append(f"[v{i}]")
        if audio_mode == "keep":
            filters.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=1[outv][outa]")
            map_args = ["-map", "[outv]", "-map", "[outa]"]
        else:
            filters.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=0[outv]")
            map_args = ["-map", "[outv]", "-an"]
        cmd = [ffmpeg.FFMPEG, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters), *map_args,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-movflags", "+faststart"]
        if audio_mode == "keep":
            cmd += ["-c:a", "aac", "-ar", "48000", "-ac", "2"]
        cmd.append(str(out))
        proc = ffmpeg.run(cmd, timeout=600)
        if proc.returncode != 0 or not out.is_file():
            raise RuntimeError(f"stitch failed: {proc.stderr[-800:]}")
        return out
    finally:
        for path in tmpdir.glob("*"):
            try:
                path.unlink()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass
