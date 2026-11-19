"""Provider request bodies: overlays are switched off by parameter.

A prompt that says "不要水印" neither removes a provider watermark nor stops a
model from painting one; the request body is the only reliable switch.

Run with:
  PYTHONPATH=src .venv/bin/python tests/provider_payloads.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-payload-")
os.environ["ADCLIP_TEST_MODE"] = "1"

from adclip.providers import ark  # noqa: E402


def check_ark_payload() -> None:
    body = ark._payload("doubao-seedance-2-0-mini", "竖屏短视频，拿起商品", duration=99, resolution="720p", aspect="9:16")
    assert body["watermark"] is False, body
    assert body["duration"] == 30, body
    assert body["generate_audio"] is True, body
    assert body["content"][0]["type"] == "text", body


def check_ark_images() -> None:
    # Reference images are attached as data URIs; no upload channel exists.
    paths = []
    base = tempfile.mkdtemp(prefix="adclip-frames-")
    for index in range(12):
        path = os.path.join(base, f"f{index}.png")
        with open(path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n")
        paths.append(path)
    from pathlib import Path

    body = ark._payload("m", "prompt", images=[Path(p) for p in paths])
    images = [item for item in body["content"] if item["type"] == "image_url"]
    assert len(images) == 9, len(images)
    assert images[0]["role"] == "reference_image", images[0]
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,"), images[0]


def main() -> None:
    check_ark_payload()
    check_ark_images()
    print("adclip provider payloads: ok")


if __name__ == "__main__":
    main()
