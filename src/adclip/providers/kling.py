"""Minimal Kling official video adapter.

Uses the classic `/v1/videos/text2video` or `/v1/videos/image2video` task API,
with `sound=on` for native dialogue/audio on supported models. Local images are
sent as raw base64, matching the official classic API shape.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import httpx

from .base import Provider, ProviderError, ProviderNotConfigured

BASE_URL = os.environ.get("KLING_API_BASE_URL", "https://api-singapore.klingai.com").rstrip("/")
MODELS = {"kling.v3": "kling-v3", "kling.v2.6": "kling-v2-6"}


def _api_key() -> str:
    return os.environ.get("KLING_API_KEY", "").strip()


def _raw_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


class KlingProvider(Provider):
    id = "kling"

    def generate(
        self,
        prompt: str,
        *,
        images: list[Path] | None = None,
        duration: int = 8,
        resolution: str = "720p",
        aspect: str = "9:16",
        model: str = "kling.v3",
        output: Path,
    ) -> Path:
        key = _api_key()
        if not key:
            raise ProviderNotConfigured("未配置 KLING_API_KEY")
        model_name = MODELS.get(model)
        if not model_name:
            raise ProviderError(f"未知 Kling 模型：{model}")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        duration_s = str(5 if duration <= 5 else 10)
        mode = "pro" if resolution == "1080p" else "std"
        payload = {
            "model_name": model_name,
            "prompt": prompt,
            "duration": duration_s,
            "mode": mode,
            "sound": "on",
            "aspect_ratio": aspect,
            "negative_prompt": "字幕, 水印, logo, 文字",
        }
        if images:
            payload["image"] = _raw_base64(images[0])
            path = "/v1/videos/image2video"
        else:
            path = "/v1/videos/text2video"
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                created = client.post(f"{BASE_URL}{path}", headers=headers, json=payload)
                if created.status_code >= 400:
                    raise ProviderError(f"Kling 创建任务失败 HTTP {created.status_code}: {created.text[:300]}")
                body = created.json()
                task_id = ((body.get("data") or {}).get("task_id"))
                if not task_id:
                    raise ProviderError(f"Kling 没有返回 task_id: {body}")
                deadline = time.monotonic() + 1500
                while time.monotonic() < deadline:
                    time.sleep(4)
                    status_res = client.get(f"{BASE_URL}{path}/{task_id}", headers=headers)
                    if status_res.status_code >= 400:
                        raise ProviderError(f"Kling 查询失败 HTTP {status_res.status_code}: {status_res.text[:300]}")
                    task = (status_res.json().get("data") or {})
                    status = str(task.get("task_status") or task.get("status") or "").lower()
                    if status in {"failed", "failure"}:
                        raise ProviderError(f"Kling 任务失败: {task.get('task_status_msg') or task}")
                    if status in {"succeed", "succeeded", "success"}:
                        videos = ((task.get("task_result") or {}).get("videos") or [])
                        if not videos or not videos[0].get("url"):
                            raise ProviderError("Kling 成功但没有视频 URL")
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with client.stream("GET", videos[0]["url"], timeout=180.0) as download:
                            download.raise_for_status()
                            with output.open("wb") as handle:
                                for chunk in download.iter_bytes():
                                    handle.write(chunk)
                        if not output.is_file() or output.stat().st_size == 0:
                            raise ProviderError("Kling 下载结果为空")
                        return output
                raise ProviderError("Kling 任务超时")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Kling 网络错误：{exc}") from exc
