"""MiniMax video adapter (Hailuo v1 + H3 v2).

The v1 Hailuo path is the low-cost smoke-test path. H3 uses the v2
content-generation task API. Native dialogue is not claimed until a real
bake-off confirms it; the catalogue marks the current Hailuo entry accordingly.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path

import httpx

from .base import Provider, ProviderError, ProviderNotConfigured

CN_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
GLOBAL_BASE = os.environ.get("MINIMAX_GLOBAL_BASE", "https://api.minimax.io").rstrip("/")
MODELS = {
    "minimax.hailuo-2.3-fast": ("MiniMax-Hailuo-2.3-Fast", "v1"),
    "minimax.h3": ("MiniMax-H3", "v2"),
}


def _api_key() -> str:
    return os.environ.get("MINIMAX_API_KEY", "").strip()


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _error_message(payload: dict) -> str:
    base = payload.get("base_resp") or {}
    return str(base.get("status_msg") or payload.get("message") or payload.get("error") or payload)


class MiniMaxProvider(Provider):
    id = "minimax"

    def generate(
        self,
        prompt: str,
        *,
        images: list[Path] | None = None,
        duration: int = 6,
        resolution: str = "768P",
        aspect: str = "9:16",
        model: str = "minimax.hailuo-2.3-fast",
        output: Path,
    ) -> Path:
        key = _api_key()
        if not key:
            raise ProviderNotConfigured("未配置 MINIMAX_API_KEY")
        if model not in MODELS:
            raise ProviderError(f"未知 MiniMax 模型：{model}")
        model_name, api = MODELS[model]
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        errors = []
        for base in (CN_BASE, GLOBAL_BASE):
            try:
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                    if api == "v2":
                        payload = {
                            "model": model_name,
                            "content": [{"type": "text", "text": prompt}],
                            "resolution": "2K",
                            "duration": max(4, min(15, int(duration))),
                            "ratio": aspect,
                        }
                        created = client.post(f"{base}/v2/video_generation", headers=headers, json=payload)
                        if created.status_code >= 400:
                            raise ProviderError(f"MiniMax 创建失败 HTTP {created.status_code}: {created.text[:300]}")
                        task_id = created.json().get("task_id")
                        if not task_id:
                            raise ProviderError(f"MiniMax 没有返回 task_id: {created.text[:300]}")
                        deadline = time.monotonic() + 1500
                        while time.monotonic() < deadline:
                            time.sleep(4)
                            status_res = client.get(f"{base}/v2/query/video_generation/{task_id}", headers=headers)
                            if status_res.status_code >= 400:
                                raise ProviderError(f"MiniMax 查询失败 HTTP {status_res.status_code}: {status_res.text[:300]}")
                            task = status_res.json().get("task") or {}
                            status = str(task.get("status") or "").lower()
                            if status in {"failed", "cancelled"}:
                                raise ProviderError(f"MiniMax 任务 {status}: {task.get('error') or task}")
                            if status == "succeeded":
                                url = (task.get("content") or {}).get("url")
                                if not url:
                                    raise ProviderError("MiniMax 成功但没有视频 URL")
                                return self._download(client, url, output)
                        raise ProviderError("MiniMax 任务超时")
                    payload = {
                        "model": model_name,
                        "prompt": prompt,
                        "duration": 6 if int(duration) <= 6 else 10,
                        "resolution": "768P" if resolution not in {"1080P", "2K"} else "1080P",
                    }
                    if images:
                        payload["first_frame_image"] = _data_uri(images[0])
                    created = client.post(f"{base}/v1/video_generation", headers=headers, json=payload)
                    if created.status_code >= 400:
                        raise ProviderError(f"MiniMax 创建失败 HTTP {created.status_code}: {created.text[:300]}")
                    body = created.json()
                    base_err = body.get("base_resp") or {}
                    if base_err.get("status_code") not in (0, None):
                        raise ProviderError(f"MiniMax 拒绝：{_error_message(body)}")
                    task_id = body.get("task_id")
                    if not task_id:
                        raise ProviderError(f"MiniMax 没有返回 task_id: {created.text[:300]}")
                    deadline = time.monotonic() + 1500
                    file_id = None
                    while time.monotonic() < deadline:
                        time.sleep(4)
                        status_res = client.get(f"{base}/v1/query/video_generation", headers=headers, params={"task_id": task_id})
                        if status_res.status_code >= 400:
                            raise ProviderError(f"MiniMax 查询失败 HTTP {status_res.status_code}: {status_res.text[:300]}")
                        task = status_res.json()
                        status = str(task.get("status") or "")
                        if status.lower() in {"fail", "failed"}:
                            raise ProviderError(f"MiniMax 任务失败：{_error_message(task)}")
                        if status == "Success":
                            file_id = task.get("file_id")
                            break
                    if not file_id:
                        raise ProviderError("MiniMax 任务超时或没有 file_id")
                    file_res = client.get(f"{base}/v1/files/retrieve", headers=headers, params={"file_id": file_id})
                    if file_res.status_code >= 400:
                        raise ProviderError(f"MiniMax 文件查询失败 HTTP {file_res.status_code}: {file_res.text[:300]}")
                    file_data = file_res.json()
                    url = ((file_data.get("file") or {}).get("download_url"))
                    if not url:
                        raise ProviderError("MiniMax 文件没有 download_url")
                    return self._download(client, url, output)
            except (httpx.HTTPError, ProviderError) as exc:
                errors.append(f"{base}: {exc}")
                if isinstance(exc, ProviderError) and ("余额" in str(exc) or "insufficient" in str(exc) or "1008" in str(exc)):
                    break
                continue
        raise ProviderError("MiniMax 请求失败：" + " | ".join(errors)[:800])

    @staticmethod
    def _download(client: httpx.Client, url: str, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        with client.stream("GET", url, timeout=180.0) as response:
            response.raise_for_status()
            with output.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        if not output.is_file() or output.stat().st_size == 0:
            raise ProviderError("MiniMax 下载结果为空")
        return output
