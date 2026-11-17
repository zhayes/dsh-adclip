"""Volcengine Ark image generation (Seedream 4.x).

One POST to `/images/generations`, then the returned URL (or inline base64) is
written to the run's artifact path. The request shape follows Ark's image API:
`size` takes explicit pixel dimensions computed from the UI's area + aspect, and
`watermark` is off because the output is a product image.
"""
from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

import httpx

BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
MODEL_ENV = "ARK_MODEL_SEEDREAM_4_0"
DEFAULT_MODEL = "doubao-seedream-4-0-20260415"


def _api_key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def _model_id(model: str) -> str:
    return os.environ.get(MODEL_ENV, "").strip() or model or DEFAULT_MODEL


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _error_message(response: httpx.Response) -> str:
    message = response.text[:400]
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or message)
        elif isinstance(payload, dict) and payload.get("message"):
            message = str(payload["message"])
    except Exception:
        pass
    return message


def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    aspect: str = "1:1",
    area: str = "2K",
    output: Path,
    reference: Path | None = None,
) -> dict:
    """Generate one image; returns its pixel size."""
    from .. import image_params

    key = _api_key()
    if not key:
        raise RuntimeError("未配置 ARK_API_KEY")
    body: dict = {
        "model": _model_id(model),
        "prompt": prompt,
        "size": image_params.size_for(area, aspect),
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled",
    }
    if reference is not None and reference.is_file():
        body["image"] = _data_uri(reference)
    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=15.0)) as client:
            response = client.post(
                f"{BASE_URL}/images/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Ark 图片生成失败 HTTP {response.status_code}: {_error_message(response)}")
            payload = response.json()
            rows = payload.get("data") or []
            if not rows:
                raise RuntimeError("Ark 图片接口没有返回 data")
            item = rows[0]
            if item.get("error"):
                error = item["error"]
                raise RuntimeError(f"Ark 图片生成失败：{error.get('message') if isinstance(error, dict) else error}")
            output.parent.mkdir(parents=True, exist_ok=True)
            if item.get("b64_json"):
                output.write_bytes(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                download = client.get(str(item["url"]))
                if download.status_code >= 400:
                    raise RuntimeError(f"Ark 图片下载失败 HTTP {download.status_code}")
                output.write_bytes(download.content)
            else:
                raise RuntimeError("Ark 图片接口没有返回 url 或 b64_json")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ark 图片请求失败：{exc}") from exc
    result: dict = {}
    try:
        from PIL import Image

        with Image.open(output) as image:
            result["width"], result["height"] = image.size
    except Exception:
        result["width"] = result["height"] = None
    return result
