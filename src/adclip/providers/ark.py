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


# Ark answers 400 with an English code; each hint below names the action the
# operator actually has to take, so a failed run is readable from the UI instead
# of a wall of provider JSON. Measured against the live API, not guessed.
_ERROR_HINTS: tuple[tuple[str, str], ...] = (
    ("PrivacyInformation", "参考素材含真人：Seedance 不接收含真人的参考图/视频；先抹脸，或改用模型尾帧 / 虚拟人像"),
    ("pixel count", "参考素材像素不足：总像素需 ≥ 407696（约 640×640）"),
    ("Asset Service", "方舟素材服务未开通：asset:// 需要先在控制台开通"),
    ("resource not found", "参考素材无法访问：方舟取不到该链接"),
    ("invalid url scheme", "参考素材地址不合法：只接受公网 URL 或 asset:// 素材 ID"),
    ("invalid url", "参考素材地址不合法：裸 file id 不行，需公网 URL 或 asset:// 素材 ID"),
)


def _readable(text: str) -> str:
    lowered = text.lower()
    for needle, hint in _ERROR_HINTS:
        if needle.lower() in lowered:
            return f"{hint}｜{text[:200]}"
    return text[:300]


def _image_url(item: Path | str) -> str:
    """Local files become data URIs; URLs and `asset://` ids pass through.

    Ark takes a public URL or an `asset://<id>` 素材 ID in `image_url.url` and
    nothing else: a raw file id is `invalid url` and `file://` is an invalid
    scheme. Model-returned last frames arrive as presigned URLs and stay
    trustworthy only while unmodified, so they must be forwarded verbatim.
    """
    if isinstance(item, Path):
        return _data_uri(item)
    text = str(item or "").strip()
    if not text:
        raise ProviderError("参考图为空")
    return text


def _payload(
    model_id: str,
    prompt: str,
    *,
    images: list[Path | str] | None = None,
    duration: int = 8,
    resolution: str = "720p",
    aspect: str = "9:16",
    return_last_frame: bool = False,
) -> dict:
    """Ark request body. `watermark: false` is the only thing that removes the
    provider's overlay; prompt text cannot, and naming it there can leak the
    word into the picture."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for item in (images or [])[:9]:
        content.append({
            "type": "image_url",
            "image_url": {"url": _image_url(item)},
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
        "return_last_frame": bool(return_last_frame),
    }


def _capture_last_frame(
    client: httpx.Client,
    url: str,
    output: Path,
    meta: dict | None,
) -> None:
    """Keep the returned last frame while its presigned URL is still alive.

    Ark trusts a model's own face-containing output as input only while it is
    the *original* artifact, and the URL expires in about 24 hours. Re-encoding a
    frame locally loses that trust, so the only way to carry one character from
    shot to shot is to hand the provider its own last frame, unmodified.
    """
    if not url:
        return
    if meta is not None:
        meta["last_frame_url"] = url
    target = output.with_name("last_frame.jpg")
    try:
        with client.stream("GET", url, timeout=120.0) as download:
            download.raise_for_status()
            with target.open("wb") as handle:
                for chunk in download.iter_bytes():
                    handle.write(chunk)
    except httpx.HTTPError:
        return
    if target.is_file() and target.stat().st_size:
        if meta is not None:
            meta["last_frame_path"] = str(target)


class ArkProvider(Provider):
    id = "ark"

    def generate(
        self,
        prompt: str,
        *,
        images: list[Path | str] | None = None,
        duration: int = 8,
        resolution: str = "720p",
        aspect: str = "9:16",
        model: str = "ark.seedance-2.5",
        output: Path,
        return_last_frame: bool = False,
        meta: dict | None = None,
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
            return_last_frame=return_last_frame,
        )
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                created = client.post(f"{BASE_URL}/contents/generations/tasks", headers=headers, json=payload)
                if created.status_code >= 400:
                    raise ProviderError(f"Ark 创建任务失败 HTTP {created.status_code}: {_readable(created.text)}")
                task_id = created.json().get("id")
                if not task_id:
                    raise ProviderError("Ark 没有返回 task id")
                deadline = time.monotonic() + 1500
                while time.monotonic() < deadline:
                    time.sleep(3)
                    status_res = client.get(f"{BASE_URL}/contents/generations/tasks/{task_id}", headers=headers)
                    if status_res.status_code >= 400:
                        raise ProviderError(f"Ark 查询失败 HTTP {status_res.status_code}: {_readable(status_res.text)}")
                    task = status_res.json()
                    status = str(task.get("status") or "").lower()
                    if status in {"failed", "cancelled", "expired"}:
                        raise ProviderError(f"Ark 任务 {status}: {task.get('error') or task}")
                    if status == "succeeded":
                        body = task.get("content") or {}
                        url = body.get("video_url")
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
                        _capture_last_frame(client, str(body.get("last_frame_url") or ""), output, meta)
                        return output
                raise ProviderError("Ark 任务超时")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ark 网络错误：{exc}") from exc
