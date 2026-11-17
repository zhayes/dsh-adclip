"""Model fallback checks for image and video generation.

Run with:
  PYTHONPATH=src .venv/bin/python tests/fallback.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-fallback-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from PIL import Image  # noqa: E402

from adclip import image_params, store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import generate, image_runner  # noqa: E402


IMAGE_ROWS = [
    {
        "id": "test.image-a", "provider": "minimax", "model": "image-a", "label": "A",
        "capabilities": ["text_to_image"], "aspects": ["1:1"], "areas": ["2K"],
        "default_area": "2K", "enabled": True, "available": True,
    },
    {
        "id": "test.image-b", "provider": "ark", "model": "image-b", "label": "B",
        "capabilities": ["text_to_image"], "aspects": ["1:1"], "areas": ["2K"],
        "default_area": "2K", "enabled": True, "available": True,
    },
]


def check_image_fallback() -> None:
    original_catalog = image_params.catalog
    original_providers = dict(image_runner.IMAGE_PROVIDERS)

    def fail(*args, **kwargs):
        raise RuntimeError("HTTP 402: insufficient balance (1008)")

    def ok(prompt, *, model, aspect, area, output, reference=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (210, 180, 140)).save(output, format="PNG")
        return {"width": 64, "height": 64}

    image_params.catalog = lambda: IMAGE_ROWS
    image_runner.IMAGE_PROVIDERS = {"minimax": fail, "ark": ok}
    try:
        run = Run(
            id=store.new_id("img"),
            scenario="text-to-image",
            title="fallback image",
            inputs={"prompt": "a coffee poster"},
            advanced={"model": "test.image-a", "aspect": "1:1", "area": "2K"},
            steps=[RunStep(name="image", label="生成图片")],
            created_at=store.now(),
        )
        store.run_dir(run.id).mkdir(parents=True, exist_ok=True)
        (store.run_dir(run.id) / "artifacts").mkdir(parents=True, exist_ok=True)
        store.write_run(run)
        image_runner.execute(run.id)
        saved = store.read_run(run.id)
        assert saved is not None and saved.status == "succeeded", saved
        assert saved.result["model"] == "test.image-b", saved.result
        assert saved.result["attempts"][0]["model"] == "test.image-a", saved.result
        assert saved.result["image"], saved.result
    finally:
        image_params.catalog = original_catalog
        image_runner.IMAGE_PROVIDERS = original_providers


def check_video_fallback() -> None:
    original_candidates = generate._video_candidates
    original_adapter = generate._adapter

    class Fail:
        def generate(self, *args, **kwargs):
            raise RuntimeError("HTTP 402: insufficient balance (1008)")

    class Ok:
        def generate(self, prompt, *, images=None, duration=4, resolution="720p", aspect="9:16", model="", output):
            output.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg.make_synthetic_clip(None, output, duration=2, width=320, height=240)
            return output

    rows = [
        {"id": "test.video-a", "provider": "minimax", "model": "video-a"},
        {"id": "test.video-b", "provider": "ark", "model": "video-b"},
    ]

    def adapter(model_id):
        return Fail() if model_id == "test.video-a" else Ok()

    generate._video_candidates = lambda run: rows
    generate._adapter = adapter
    try:
        run = Run(
            id=store.new_id("run"),
            scenario="text-to-video",
            title="fallback video",
            inputs={"brief": "a coffee video"},
            advanced={"model": "auto", "duration": 4, "aspect": "9:16", "resolution": "720p"},
            steps=[RunStep(name="generate", label="生成")],
            created_at=store.now(),
        )
        store.run_dir(run.id).mkdir(parents=True, exist_ok=True)
        (store.run_dir(run.id) / "artifacts").mkdir(parents=True, exist_ok=True)
        store.atomic_write_json(store.run_dir(run.id) / "artifacts" / "script.json", {"beats": []})
        store.write_run(run)
        result = generate.generate(run.id)
        assert result["model"] == "test.video-b", result
        assert result["attempts"][0]["model"] == "test.video-a", result
        saved = store.read_run(run.id)
        assert saved is not None and saved.advanced["model"] == "test.video-b", saved
    finally:
        generate._video_candidates = original_candidates
        generate._adapter = original_adapter


def main() -> None:
    check_image_fallback()
    check_video_fallback()
    print("adclip fallback: ok")


if __name__ == "__main__":
    main()
