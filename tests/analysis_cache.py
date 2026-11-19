"""Analysis cache and cheap-first vision ladder checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/analysis_cache.py
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-cache-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from adclip import analysis_cache, store  # noqa: E402
from adclip.media import ffmpeg, vision  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import analyze  # noqa: E402


def _asset() -> str:
    store.ensure_dirs()
    media = store.ASSETS / "a_cache.mp4"
    if not media.is_file():
        ffmpeg.make_synthetic_clip(None, media, duration=4, width=240, height=426, fps=24)
    digest = hashlib.sha256(media.read_bytes()).hexdigest()
    store.atomic_write_json(store.ASSETS / "a_cache.json", {
        "id": "a_cache",
        "kind": "video",
        "name": "cache.mp4",
        "path": "assets/a_cache.mp4",
        "sha256": digest,
    })
    return "a_cache"


def _run(asset_id: str) -> Run:
    run = Run(
        id=store.new_id("run"),
        scenario="viral-remake",
        title="cache",
        inputs={"reference_asset_id": asset_id, "brief": "活动价 19.9"},
        advanced={"duration": 4, "aspect": "9:16"},
        steps=[RunStep(name="analyze", label="拆解")],
        created_at=store.now(),
    )
    store.write_run(run)
    return run


def check_cache_roundtrip(asset_id: str) -> None:
    first = analyze.analyze(_run(asset_id).id)
    assert not first["analysis"].get("cached"), first["analysis"]
    second_run = _run(asset_id)
    second = analyze.analyze(second_run.id)
    assert second["analysis"].get("cached") is True, second["analysis"]
    assert len(second["beats"]) == len(first["beats"]), (first["beats"], second["beats"])
    for beat in second["beats"]:
        assert (store.run_dir(second_run.id) / "artifacts" / "storyboard" / f"{beat['id']}.jpg").is_file(), beat["id"]


def check_asr_invalidates(asset_id: str) -> None:
    original = analyze.asr

    class Stub:
        LAST_ERROR = ""

        @staticmethod
        def available() -> bool:
            return True

        @staticmethod
        def disabled() -> bool:
            return False

        @staticmethod
        def transcribe(path, *, max_seconds=60.0, prompt_hint=""):
            return []

    analyze.asr = Stub
    try:
        key = analysis_cache.key(asset_id, asr_available=True, vision_available=vision.available())
        plain = analysis_cache.key(
            asset_id, asr_available=False, vision_available=vision.available()
        )
        assert key != plain, (key, plain)
        skeleton = analyze.analyze(_run(asset_id).id)
        assert not skeleton["analysis"].get("cached"), skeleton["analysis"]
        assert skeleton["analysis"]["asr"]["source"] == "failed", skeleton["analysis"]["asr"]
    finally:
        analyze.asr = original


def check_vision_signature_invalidates(asset_id: str) -> None:
    """Switching a vision provider off must not replay its cached analysis."""
    from adclip import settings
    from adclip.providers import ark_text

    sig_all = vision.chain_signature()
    assert "ark:" in sig_all, sig_all
    settings.set_enabled_text_models([])
    try:
        sig_none = vision.chain_signature()
        assert "ark:" not in sig_none, sig_none
        on = analysis_cache.key(asset_id, asr_available=False, vision_available=True, vision=sig_all)
        off = analysis_cache.key(asset_id, asr_available=False, vision_available=True, vision=sig_none)
        assert on != off, (on, off)
    finally:
        settings.set_enabled_text_models([str(row["id"]) for row in ark_text.ROWS])
        try:
            settings.MODEL_PREFS.unlink()
        except OSError:
            pass


def check_vision_order() -> None:
    from adclip.providers import ark_text

    default = vision._ark_order()
    assert default and default[0]["short"] == "lite", [row["short"] for row in default]
    os.environ["ADSTUDIO_VISION_CHEAP_FIRST"] = "0"
    try:
        pinned = vision._ark_order()
        assert [row["short"] for row in pinned] == [row["short"] for row in ark_text.vision_models()], pinned
    finally:
        os.environ.pop("ADSTUDIO_VISION_CHEAP_FIRST", None)
    assert vision._needs_review({"unclear": ["on_screen_text"], "product": "苹果"}) is True
    assert vision._needs_review({"unclear": [], "product": "未识别商品"}) is True
    assert vision._needs_review({"unclear": [], "product": "苹果"}) is False


def main() -> None:
    asset_id = _asset()
    check_cache_roundtrip(asset_id)
    check_asr_invalidates(asset_id)
    check_vision_signature_invalidates(asset_id)
    check_vision_order()
    print("adclip analysis cache: ok")


if __name__ == "__main__":
    main()
