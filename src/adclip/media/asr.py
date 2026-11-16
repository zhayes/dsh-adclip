"""Lightweight Chinese ASR for reference clips.

faster-whisper is optional: if it is not installed (or ADSTUDIO_ASR=0), the
analysis pipeline falls back to the heuristic transcript-free path. Audio is
decoded by ffmpeg to PCM first because the installed PyAV/Python combination
does not accept faster-whisper's container options directly.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any

from .ffmpeg import FFMPEG

_MODEL = None
_MODEL_NAME = ""


def available() -> bool:
    if os.environ.get("ADSTUDIO_ASR", "1") == "0":
        return False
    return importlib.util.find_spec("faster_whisper") is not None


def _load_model():
    global _MODEL, _MODEL_NAME
    name = os.environ.get("ADSTUDIO_ASR_MODEL", "small")
    if _MODEL is not None and _MODEL_NAME == name:
        return _MODEL
    from faster_whisper import WhisperModel

    _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
    _MODEL_NAME = name
    return _MODEL


def _pcm(path: str | Path) -> bytes:
    proc = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"audio decode failed: {proc.stderr[-300:]!r}")
    return proc.stdout


def transcribe(path: str | Path, *, max_seconds: float = 60.0) -> list[dict[str, Any]]:
    if not available() or not Path(path).is_file():
        return []
    try:
        import numpy as np

        audio = np.frombuffer(_pcm(path), dtype=np.float32)
        if audio.size < 1600:
            return []
        max_samples = int(max_seconds * 16000)
        if audio.size > max_samples:
            audio = audio[:max_samples]
        model = _load_model()
        segments, _info = model.transcribe(
            audio,
            language=os.environ.get("ADSTUDIO_ASR_LANGUAGE", "zh"),
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        rows = []
        for seg in segments:
            text = str(seg.text or "").strip()
            if not text:
                continue
            rows.append({"start_s": round(float(seg.start), 3), "end_s": round(float(seg.end), 3), "text": text})
        return rows
    except Exception:
        return []
