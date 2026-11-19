"""Audio policy matrix checks for non-H3 remake rungs.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_audio.py
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-audio-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from adclip import store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import post  # noqa: E402


def _clip(path: Path, *, freq: int, duration: float = 4.0) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=360x640:rate=24",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000",
        "-t", str(duration), "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True)


def _prepare(*, scope: str) -> Run:
    store.ensure_dirs()
    reference = store.ASSETS / "a_audio_ref.mp4"
    if not reference.is_file():
        _clip(reference, freq=440)
    store.atomic_write_json(store.ASSETS / "a_audio_ref.json", {
        "id": "a_audio_ref", "kind": "video", "name": "ref.mp4", "path": "assets/a_audio_ref.mp4",
    })
    run = Run(
        id=store.new_id("run"),
        scenario="viral-remake",
        title="audio",
        inputs={"reference_asset_id": "a_audio_ref", "brief": "换成鱿鱼须"},
        advanced={"audio_mode": "preserve", "replace_scope": scope, "aspect": "9:16", "duration": 4},
        steps=[RunStep(name="post", label="后期")],
        created_at=store.now(),
    )
    store.write_run(run)
    artifacts = store.run_dir(run.id) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    _clip(artifacts / "provider_raw.mp4", freq=880)
    store.atomic_write_json(artifacts / "skeleton.json", {
        "source": {"duration_s": 4.0, "aspect": "9:16", "has_audio": True},
        "remake_plan": {"shots": []},
    })
    store.atomic_write_json(artifacts / "script.json", {"beats": []})
    run.selection = {"mode": "generation", "rung": "generation"}
    store.write_run(run)
    return run


def check_person_preserves_reference_audio() -> None:
    run = _prepare(scope="person")
    result = post.post(run.id)
    assert result["audio_source"] == "reference", result
    assert any("参考片原声" in warning for warning in result["warnings"]), result
    final = store.run_artifact(run.id, "final.mp4")
    assert ffmpeg.probe(final)["has_audio"] is True


def check_product_keeps_generated_audio() -> None:
    run = _prepare(scope="both")
    result = post.post(run.id)
    assert result["audio_source"] is None, result
    final = store.run_artifact(run.id, "final.mp4")
    assert ffmpeg.probe(final)["has_audio"] is True


def main() -> None:
    check_person_preserves_reference_audio()
    check_product_keeps_generated_audio()
    print("adclip remake audio: ok")


if __name__ == "__main__":
    main()
