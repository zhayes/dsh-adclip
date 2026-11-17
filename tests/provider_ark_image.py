"""Ark image adapter: request shape and file write, without a real key.

Run with: PYTHONPATH=src .venv/bin/python tests/provider_ark_image.py
"""
from __future__ import annotations

import base64
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ["ARK_API_KEY"] = "test-key"

from adclip.providers import ark_image  # noqa: E402

PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
).decode("ascii")


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, content: bytes = b"") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, *, payload: dict, image: bytes = b"") -> None:
        self.payload = payload
        self.image = image
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
        self.posts.append((url, json))
        return FakeResponse(200, self.payload)

    def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        return FakeResponse(200, content=self.image)


def with_client(fake: FakeClient):
    return mock.patch.object(ark_image.httpx, "Client", lambda **_: fake)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "image.bin"
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 32
        fake = FakeClient(payload={"data": [{"url": "https://cdn.example/img.png"}]}, image=image_bytes)
        with with_client(fake):
            result = ark_image.generate("一个红色灯泡", model="doubao-seedream-4-0-20260415", aspect="16:9", area="2K", output=output)

        assert output.is_file() and output.read_bytes() == image_bytes
        assert fake.gets == ["https://cdn.example/img.png"]
        url, body = fake.posts[0]
        assert url.endswith("/images/generations"), url
        assert body["model"] == "doubao-seedream-4-0-20260415"
        assert body["size"] == "2048x1152", body["size"]
        assert body["response_format"] == "url"
        assert body["watermark"] is False
        assert body["sequential_image_generation"] == "disabled"
        assert "image" not in body
        assert result["width"] is None or result["width"] > 0

        # A reference image is inlined as a data URI.
        ref = Path(tmp) / "ref.png"
        ref.write_bytes(image_bytes)
        fake2 = FakeClient(payload={"data": [{"b64_json": base64.b64encode(image_bytes).decode("ascii")}]})
        with with_client(fake2):
            ark_image.generate("改成蓝色", aspect="1:1", area="1K", output=Path(tmp) / "out.bin", reference=ref)
        assert fake2.posts[0][1]["image"].startswith("data:image/png;base64,")
        assert fake2.posts[0][1]["size"] == "1024x1024"

        # HTTP errors surface as one readable line.
        class ErrorClient(FakeClient):
            def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
                return FakeResponse(401, {"error": {"message": "invalid api key"}})

        try:
            with with_client(ErrorClient(payload={})):
                ark_image.generate("x", output=Path(tmp) / "err.bin")
        except RuntimeError as exc:
            assert "invalid api key" in str(exc), str(exc)
        else:
            raise AssertionError("expected a RuntimeError for HTTP 401")

    print("ark image adapter: ok")


if __name__ == "__main__":
    main()
