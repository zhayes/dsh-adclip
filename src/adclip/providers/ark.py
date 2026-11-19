"""Minimal Volcengine Ark Seedance adapter (native audio).

This is intentionally small: create a content-generation task, poll it, download
the result. It is implemented against the official Ark REST shape used by the
existing tooling, but is marked unverified until a real key is available.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path

import httpx

from .base import Provider, ProviderError, ProviderNotConfigured

BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODELS = {
    "ark.seedance-2.5": "doubao-seedance-2-5-260628",
    "ark.seedance-2.0": "doubao-seedance-2-0-260128",
    "ark.seedance-2.0-mini": "doubao-seedance-2-0-mini-260615",
    "ark.seedance-2.0-fast": "doubao-seedance-2-0-fast-260128",
}
MODEL_ENV = {
    "ark.seedance-2.5": "ARK_MODEL_SEEDANCE_2_5",
    "ark.seedance-2.0": "ARK_MODEL_SEEDANCE_2_0",
    "ark.seedance-2.0-mini": "ARK_MODEL_SEEDANCE_2_0_MINI",
    "ark.seedance-2.0-fast": "ARK_MODEL_SEEDANCE_2_0_FAST",
}


def _model_id(model: str) -> str:
    env_name = MODEL_ENV.get(model)
    return (os.environ.get(env_name, "").strip() if env_name else "") or MODELS.get(model, "")


def _api_key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _payload(
    model_id: str,
    prompt: str,
    *,
    images: list[Path] | None = None,
    duration: int = 8,
    resolution: str = "720p",
    aspect: str = "9:16",
) -> dict:
    """Ark request body. `watermark: false` is the only thing that removes the
    provider's overlay; prompt text cannot, and naming it there can leak the
    word into the picture."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in (images or [])[:9]:
        content.append({
            "type": "image_url",
            "image_url": {"url": _data_uri(path)},
            "role": "reference_image",
        })
    return {
        "model": model_id,
        "content": content,
        "duration": max(4, min(30, int(duration))),
        "resolution": resolution,
        "ratio": aspect,
        "generate_audio": True,
        "watermark": False,
        "return_last_frame": False,
    }


class ArkProvider(Provider):
    id = "ark"

    def generate(
        self,
        prompt: str,
        *,
        images: list[Path] | None = None,
        duration: int = 8,
        resolution: str = "720p",
        aspect: str = "9:16",
        model: str = "ark.seedance-2.5",
        output: Path,
    ) -> Path:
        key = _api_key()
        if not key:
            raise ProviderNotConfigured("未配置 ARK_API_KEY")
        model_id = _model_id(model)
        if model_id is None:
            raise ProviderError(f"未知 Ark 模型：{model}")
        payload = _payload(
            model_id,
            prompt,
            images=images,
            duration=duration,
            resolution=resolution,
            aspect=aspect,
        )
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                created = client.post(f"{BASE_URL}/contents/generations/tasks", headers=headers, json=payload)
                if created.status_code >= 400:
                    raise ProviderError(f"Ark 创建任务失败 HTTP {created.status_code}: {created.text[:300]}")
                task_id = created.json().get("id")
                if not task_id:
                    raise ProviderError("Ark 没有返回 task id")
                deadline = time.monotonic() + 1500
                while time.monotonic() < deadline:
                    time.sleep(3)
                    status_res = client.get(f"{BASE_URL}/contents/generations/tasks/{task_id}", headers=headers)
                    if status_res.status_code >= 400:
                        raise ProviderError(f"Ark 查询失败 HTTP {status_res.status_code}: {status_res.text[:300]}")
                    task = status_res.json()
                    status = str(task.get("status") or "").lower()
                    if status in {"failed", "cancelled", "expired"}:
                        raise ProviderError(f"Ark 任务 {status}: {task.get('error') or task}")
                    if status == "succeeded":
                        url = ((task.get("content") or {}).get("video_url"))
                        if not url:
                            raise ProviderError("Ark 成功但没有 video_url")
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with client.stream("GET", url, timeout=120.0) as download:
                            download.raise_for_status()
                            with output.open("wb") as handle:
                                for chunk in download.iter_bytes():
                                    handle.write(chunk)
                        if not output.is_file() or output.stat().st_size == 0:
                            raise ProviderError("Ark 下载结果为空")
                        return output
                raise ProviderError("Ark 任务超时")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ark 网络错误：{exc}") from exc
