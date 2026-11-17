"""MiniMax H3 reference payload and prompt checks (no network).

Run with:
  PYTHONPATH=src .venv/bin/python tests/minimax_h3.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-h3-")

from adclip.media import minimax_files  # noqa: E402
from adclip.pipeline import remake  # noqa: E402
from adclip.providers import minimax  # noqa: E402


def make_file(path: Path) -> Path:
    path.write_bytes(b"test")
    return path


def check_payload() -> None:
    work = Path(tempfile.mkdtemp())
    video = make_file(work / "ref.mp4")
    image = make_file(work / "product.jpg")
    person = make_file(work / "person.png")
    calls = []

    def fake_upload(path, purpose="video_generation_input"):
        calls.append((Path(path).name, purpose))
        return "file_" + Path(path).stem

    original = minimax_files.upload_file
    minimax_files.upload_file = fake_upload
    try:
        payload = minimax._h3_payload(
            "参考视频1，只换商品",
            images=[image, person],
            reference_video=video,
            duration=11,
            resolution="720p",
        )
        hd = minimax._h3_payload("x", reference_video=video, resolution="1080p", duration=20)
    finally:
        minimax_files.upload_file = original

    assert payload["model"] == "MiniMax-H3"
    assert payload["duration"] == 11
    assert payload["resolution"] == "768P"
    assert payload["ratio"] == "adaptive"
    assert calls and calls[-1][1] == "video_generation_input"
    types = [item["type"] for item in payload["content"]]
    assert types == ["text", "image_url", "image_url", "video_url"], types
    assert payload["content"][1]["role"] == "reference_image"
    assert payload["content"][3]["role"] == "reference_video"
    assert payload["content"][3]["video_url"]["url"].startswith("mm_file://"), payload

    assert hd["resolution"] == "2K"
    assert hd["duration"] == 15
    assert hd["ratio"] == "adaptive"


def check_upload() -> None:
    work = Path(tempfile.mkdtemp())
    target = make_file(work / "upload.jpg")
    import httpx
    class Response:
        status_code = 200
        text = "{}"
        def json(self):
            return {"file_id": "file_uploaded"}
    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): return Response()
    original_client = httpx.Client
    original_key = os.environ.get("MINIMAX_API_KEY")
    os.environ["MINIMAX_API_KEY"] = "test-key"
    httpx.Client = Client
    try:
        assert minimax_files.upload_file(target) == "file_uploaded"
    finally:
        httpx.Client = original_client
        if original_key is None:
            os.environ.pop("MINIMAX_API_KEY", None)
        else:
            os.environ["MINIMAX_API_KEY"] = original_key


def check_prompt() -> None:
    skeleton = {
        "remake_plan": {
            "shots": [{"product": {"name": "原味瓜子"}, "cast": [{"description": "蓝衬衫男"}]}],
            "global": {"preserve": ["镜头", "场景", "动作", "原声"]},
        }
    }
    run = SimpleNamespace(
        inputs={"brief": "换成鹰嘴豆，活动价 9.9", "explicit_overrides": "把背景换成厨房"},
        advanced={"replace_scope": "both", "person_scope": "all", "persona": {}},
    )
    text = remake.build_h3_replace_prompt(run, skeleton, product_count=2, person_count=1)
    assert "图片1" in text and "图片3" in text, text
    assert "所有人物" in text, text
    assert "厨房" in text and "9.9" in text, text
    assert len(text) <= 7000, len(text)

    product_only = remake.build_h3_replace_prompt(
        SimpleNamespace(inputs={}, advanced={"replace_scope": "product"}),
        skeleton,
        product_count=1,
    )
    assert "将视频1中的商品" in product_only, product_only
    assert "替换为图片" in product_only, product_only

    script_doc = {"beats": [{"start_s": 0, "end_s": 2, "lines": [{"text": "豆豆云朵被七十多"}]}]}
    spoken = remake.build_h3_replace_prompt(
        SimpleNamespace(inputs={"brief": "豆豆云朵被七十多"}, advanced={"replace_scope": "product", "audio_mode": "regenerate"}),
        skeleton,
        product_count=1,
        script_doc=script_doc,
        audio_mode="regenerate",
    )
    assert "只念以下句子" in spoken and "豆豆云朵被七十多" in spoken, spoken
    preserved = remake.build_h3_replace_prompt(
        SimpleNamespace(inputs={}, advanced={"replace_scope": "product", "audio_mode": "preserve"}),
        skeleton,
        product_count=1,
        script_doc=script_doc,
        audio_mode="preserve",
    )
    assert "保留参考视频1的原声" in preserved, preserved


def main() -> None:
    check_payload()
    check_upload()
    check_prompt()
    print("adclip minimax h3: ok")


if __name__ == "__main__":
    main()
