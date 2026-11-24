"""Reference-frame face masking for models that refuse photoreal faces.

Ark rejects any reference image or video that "may contain real person", and it
judges the picture rather than its provenance: an AI-generated photoreal face is
rejected exactly like a filmed one, and a face that survives our own re-encode
loses the "original artifact" trust that would otherwise let it through. A remake
that keeps the source cast is therefore impossible through Ark, so the pipeline
always replaces the person and the frame handed to the model never needs a face.

Masking escalates instead of detecting. Ark bills nothing for a 400, so the
smallest mask that gets a frame accepted wins: send it untouched, then with a
head band, then a wider band, then the whole upper frame. No face model is
bundled (OpenCV 5 ships no cascades) and none is worth adding just to guess a box
the provider will answer for free. Product-only footage is accepted at step 0 and
therefore never pays for the escalation at all.
"""
from __future__ import annotations

from pathlib import Path

from .ffmpeg import FFMPEG, run

# (x, y, w, h) as fractions of the frame. Index 0 is "as shot": correct whenever
# there is no face to hide, which is the whole product-only rung.
STEPS: tuple[tuple[float, float, float, float] | None, ...] = (
    None,
    (0.18, 0.04, 0.64, 0.32),
    (0.06, 0.00, 0.88, 0.48),
    (0.00, 0.00, 1.00, 0.62),
)


def last_step() -> int:
    return len(STEPS) - 1


def steps() -> tuple[int, ...]:
    return tuple(range(len(STEPS)))


def is_privacy_error(message: object) -> bool:
    """Whether a provider error is the real-person rejection."""
    text = str(message or "")
    return "PrivacyInformation" in text or "may contain real person" in text


def mask_step(source: str | Path, target: str | Path, step: int) -> Path:
    """One frame with mask `step` applied; step 0 hands the source back untouched."""
    if step <= 0:
        return Path(source)
    box = STEPS[min(step, last_step())]
    assert box is not None  # step > 0 always has a box
    x, y, w, h = box
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    draw = f"drawbox=x=iw*{x}:y=ih*{y}:w=iw*{w}:h=ih*{h}:color=black@1:t=fill"
    proc = run(
        [FFMPEG, "-v", "error", "-y", "-i", str(source), "-vf", draw, "-q:v", "3", str(out)],
        timeout=60,
    )
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"face mask failed: {proc.stderr[:200]}")
    return out
