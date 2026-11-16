"""Small ffmpeg wrapper used by the lean pipeline."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _resolve(name: str) -> str:
    """Absolute path from PATH, else the bare name so exec fails loudly and late."""
    return shutil.which(name) or name


FFMPEG = _resolve("ffmpeg")
FFPROBE = _resolve("ffprobe")


def install_hint() -> str:
    """One platform-appropriate sentence for a missing ffmpeg."""
    if sys.platform == "darwin":
        return "未找到 ffmpeg。安装：brew install ffmpeg（或用 https://evermeet.cx/ffmpeg/ 的静态包）"
    if sys.platform == "win32":
        return "未找到 ffmpeg。安装：winget install Gyan.FFmpeg，或从 https://www.gyan.dev/ffmpeg/builds/ 解压后把 bin 加入 PATH"
    return "未找到 ffmpeg。安装：apt install ffmpeg（Debian/Ubuntu）或 dnf install ffmpeg（Fedora）"


def dependencies() -> dict[str, Any]:
    """What the UI needs to explain a missing media toolchain."""
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    ok = bool(ffmpeg_path and ffprobe_path)
    return {
        "ffmpeg": bool(ffmpeg_path),
        "ffprobe": bool(ffprobe_path),
        "ffmpeg_path": ffmpeg_path or "",
        "ok": ok,
        "hint": "" if ok else install_hint(),
    }


def run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a media command, turning a missing binary into an actionable error."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{Path(str(args[0])).name} 不可用：{install_hint()}") from exc


def probe(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    proc = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(target)], timeout=60)
    if proc.returncode != 0:
        raise ValueError(f"ffprobe failed: {proc.stderr[:300]}")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise ValueError("no video stream")
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    duration = float((data.get("format") or {}).get("duration") or video.get("duration") or 0.0)
    fps = _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    return {
        "path": str(target),
        "duration_s": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "aspect": _aspect(width, height),
        "video_codec": video.get("codec_name"),
        "audio_codec": (audio or {}).get("codec_name"),
        "has_audio": audio is not None,
        "size_bytes": int((data.get("format") or {}).get("size") or target.stat().st_size),
    }


def _fraction(value: Any) -> float:
    try:
        num, den = str(value or "0/1").split("/", 1)
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _aspect(width: int, height: int) -> str:
    if height > width * 1.15:
        return "9:16"
    if width > height * 1.15:
        return "16:9"
    return "1:1"


def detect_cuts(path: str | Path, duration: float, threshold: float = 0.18) -> list[float]:
    proc = run(
        [FFMPEG, "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        timeout=300,
    )
    times = sorted({round(float(x), 3) for x in re.findall(r"pts_time:([0-9.]+)", proc.stderr or "")})
    merged: list[float] = []
    for value in times:
        if 0.2 < value < duration - 0.2 and (not merged or value - merged[-1] >= 0.35):
            merged.append(value)
    return merged


def extract_frame(source: str | Path, at_s: float, target: str | Path, width: int = 360) -> Path:
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run(
        [FFMPEG, "-v", "error", "-y", "-ss", f"{max(0.0, at_s):.3f}", "-i", str(source), "-frames:v", "1",
         "-vf", f"scale={max(80, width)}:-2", "-q:v", "3", str(out)],
        timeout=60,
    )
    if proc.returncode != 0 or not out.is_file():
        raise ValueError(f"frame extraction failed: {proc.stderr[:200]}")
    return out


def make_demo_clip(
    source: str | Path | None,
    target: str | Path,
    *,
    duration: float,
    width: int,
    height: int,
    fps: int = 30,
) -> Path:
    """Create a deterministic demo clip.

    With a reference source, trim/loop it to the requested duration and frame.
    Without a source, render a test pattern so text-to-video can be exercised.
    The clip is explicitly a demo; it is not a paid provider result.
    """
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = max(1.0, float(duration))
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
        f"fps={fps},format=yuv420p"
    )
    if source and Path(source).is_file():
        facts = probe(source)
        if facts.get("has_audio"):
            cmd = [
                FFMPEG, "-v", "error", "-y", "-stream_loop", "-1", "-i", str(source),
                "-t", f"{duration:.3f}", "-vf", vf,
                "-af", "apad,atrim=0:%s,asetpts=N/SR/TB" % f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                "-movflags", "+faststart", str(out),
            ]
        else:
            cmd = [
                FFMPEG, "-v", "error", "-y", "-stream_loop", "-1", "-i", str(source),
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", f"{duration:.3f}", "-vf", vf,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                "-movflags", "+faststart", str(out),
            ]
    else:
        cmd = [
            FFMPEG, "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", f"{duration:.3f}", "-vf", "format=yuv420p",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
            "-movflags", "+faststart", str(out),
        ]
    proc = run(cmd, timeout=300)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"demo clip failed: {proc.stderr[-500:]}")
    return out


def ensure_audio(source: str | Path, target: str | Path) -> Path:
    facts = probe(source)
    if facts.get("has_audio"):
        if Path(target) != Path(source):
            shutil.copy2(source, target)
        return Path(target)
    proc = run(
        [FFMPEG, "-v", "error", "-y", "-i", str(source), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(target)],
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"add audio failed: {proc.stderr[-300:]}")
    return Path(target)


def normalize(source: str | Path, target: str | Path, *, width: int, height: int, fps: int = 30, duration: float | None = None) -> Path:
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
        f"fps={fps},format=yuv420p"
    )
    args = [FFMPEG, "-v", "error", "-y", "-i", str(source)]
    if duration:
        args += ["-t", f"{float(duration):.3f}"]
    args += ["-vf", vf, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(out)]
    proc = run(args, timeout=300)
    if proc.returncode != 0 or not out.is_file():
        # Audio filter may fail on a silent/odd track; retry with a silent bed.
        ensure_audio(source, out.with_suffix(".audio.mp4"))
        proc = run([FFMPEG, "-v", "error", "-y", "-i", str(out.with_suffix(".audio.mp4")), "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", str(out)], timeout=300)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"normalize failed: {proc.stderr[-500:]}")
    return out



def loop_to_duration(source: str | Path, target: str | Path, *, width: int, height: int, fps: int, duration: float) -> Path:
    """Normalize/trim/loop a clip to an exact duration.

    Used by the per-segment replacement path: provider clips may be shorter or
    longer than the storyboard slot. Looping is preferable to a gap; the slot is
    then cut at the exact storyboard boundary.
    """
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    fixed = out.with_suffix(".withaudio.mp4")
    ensure_audio(source, fixed)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x111827,"
        f"fps={fps},format=yuv420p"
    )
    proc = run([
        FFMPEG, "-v", "error", "-y", "-stream_loop", "-1", "-i", str(fixed),
        "-t", f"{float(duration):.3f}", "-vf", vf,
        "-af", "apad", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(out),
    ], timeout=300)
    try:
        fixed.unlink()
    except OSError:
        pass
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"loop_to_duration failed: {proc.stderr[-500:]}")
    return out

def thumbnail(source: str | Path, target: str | Path, at_s: float = 0.5) -> Path:
    return extract_frame(source, at_s, target, width=360)


def transcode(
    source: str | Path,
    target: str | Path,
    *,
    bitrate: str = "8M",
    fps: int = 30,
    trim_start: float | None = None,
    trim_end: float | None = None,
) -> Path:
    """Post-only export: re-encode bitrate/fps and optionally trim.

    No video model is called. Subtitle burn-in is intentionally not attempted:
    the local ffmpeg build has no libass/drawtext, so the SRT stays a sidecar.
    """
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = [FFMPEG, "-v", "error", "-y"]
    if trim_start:
        args += ["-ss", f"{float(trim_start):.3f}"]
    args += ["-i", str(source)]
    if trim_end:
        args += ["-to", f"{float(trim_end):.3f}"]
    args += [
        "-vf", f"fps={int(fps)},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", bitrate,
        "-maxrate", bitrate, "-bufsize", bitrate,
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    proc = run(args, timeout=300)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"transcode failed: {proc.stderr[-500:]}")
    return out
