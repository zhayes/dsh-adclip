"""Post checks: the final keeps the clip length the model delivered.

Products and prices have different character counts, so the model's pacing
drifts from the reference. Trimming back to the reference duration cut the end
of "现在只要七十多"; post must not shorten (or pad) the generated clip.

Run with:
  PYTHONPATH=src .venv/bin/python tests/post_trim.py
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-trim-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from adclip import store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import post  # noqa: E402

REFERENCE_S = 11.067


def _clip(path: Path, *, total_s: float, freq: int = 880) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=24",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000",
        "-t", f"{total_s}", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True)


def _prepare(*, raw_s: float) -> Run:
    store.ensure_dirs()
    run = Run(
        id=store.new_id("run"),
        scenario="viral-remake",
        title="trim",
        inputs={},
        advanced={"audio_mode": "regenerate", "replace_scope": "both", "aspect": "9:16"},
        steps=[RunStep(name="post", label="后期")],
        created_at=store.now(),
    )
    run.selection = {"mode": "generation", "rung": "generation"}
    store.write_run(run)
    artifacts = store.run_dir(run.id) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    _clip(artifacts / "provider_raw.mp4", total_s=raw_s)
    store.atomic_write_json(artifacts / "skeleton.json", {
        "source": {"duration_s": REFERENCE_S, "aspect": "9:16", "has_audio": True},
        "remake_plan": {"shots": []},
    })
    store.atomic_write_json(artifacts / "script.json", {"beats": []})
    return run


def check_keeps_longer_clip() -> None:
    """Raw runs past the reference: keep it, do not cut the last sentence."""
    run = _prepare(raw_s=12.096)
    result = post.post(run.id)
    final_s = float(ffmpeg.probe(store.run_artifact(run.id, "final.mp4"))["duration_s"])
    assert final_s > REFERENCE_S + 0.5, final_s
    assert any("未做时长裁剪" in warning for warning in result["warnings"]), result["warnings"]


def check_keeps_shorter_clip() -> None:
    """Raw is shorter than the reference: keep it as-is instead of padding."""
    run = _prepare(raw_s=9.0)
    result = post.post(run.id)
    final_s = float(ffmpeg.probe(store.run_artifact(run.id, "final.mp4"))["duration_s"])
    assert abs(final_s - 9.0) <= 0.2, final_s
    assert any("未做时长裁剪" in warning for warning in result["warnings"]), result["warnings"]


def main() -> None:
    check_keeps_longer_clip()
    check_keeps_shorter_clip()
    print("adclip post trim: ok")


if __name__ == "__main__":
    main()
