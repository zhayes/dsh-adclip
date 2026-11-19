"""Cheap visual similarity for remake QA.

Two clips are compared by sampling the same timestamps and computing a
difference hash (dhash) for each frame. It is deliberately coarse: the score is
meant to catch "this is a different composition", not to measure perceptual
quality. No new dependencies, no model calls.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from . import ffmpeg


def dhash(path: str | Path, *, size: int = 8) -> int | None:
    """64-bit difference hash of one image, or None when it cannot be read."""
    try:
        with Image.open(path) as image:
            gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
            pixels = gray.tobytes()
    except Exception:
        return None
    bits = 0
    stride = size + 1
    for row in range(size):
        base = row * stride
        for column in range(size):
            bits = (bits << 1) | (1 if pixels[base + column] > pixels[base + column + 1] else 0)
    return bits


def similarity(first: int | None, second: int | None, *, bits: int = 64) -> float | None:
    if first is None or second is None:
        return None
    distance = (first ^ second).bit_count()
    return max(0.0, 1.0 - distance / float(bits))


def frame_similarity(
    source: str | Path,
    target: str | Path,
    times: list[float],
    *,
    width: int = 160,
) -> float | None:
    """Mean dhash similarity at the same timestamps of two clips."""
    scores: list[float] = []
    with tempfile.TemporaryDirectory(prefix="adclip-sim-") as tmp:
        root = Path(tmp)
        for index, at_s in enumerate(times):
            left = root / f"a{index}.jpg"
            right = root / f"b{index}.jpg"
            try:
                ffmpeg.extract_frame(source, at_s, left, width=width)
                ffmpeg.extract_frame(target, at_s, right, width=width)
            except Exception:
                continue
            score = similarity(dhash(left), dhash(right))
            if score is not None:
                scores.append(score)
    if not scores:
        return None
    return sum(scores) / len(scores)
