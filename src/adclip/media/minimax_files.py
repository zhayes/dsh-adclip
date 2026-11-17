"""MiniMax Files API uploads for video generation inputs.

H3 reference material must be reachable by MiniMax. The public API rejects
local paths and recommends public URLs; the Files API is the supported path for
local files: upload with purpose ``video_generation_input`` and reference the
returned id as ``mm_file://{file_id}`` in the generation content.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import threading
from pathlib import Path
from typing import Any

import httpx

CN_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
GLOBAL_BASE = os.environ.get("MINIMAX_GLOBAL_BASE", "https://api.minimax.io").rstrip("/")
PURPOSE = "video_generation_input"
VIDEO_MB = 50
IMAGE_MB = 30
AUDIO_MB = 15
_CACHE: dict[str, str] = {}
_LOCK = threading.RLock()


def _key() -> str:
    value = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not value:
        raise RuntimeError("MINIMAX_API_KEY 未配置")
    return value


def _kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov", ".avi", ".mkv"}:
        return "video"
    if suffix in {".wav", ".mp3", ".m4a", ".aac"}:
        return "audio"
    return "image"


def _limit_mb(kind: str) -> int:
    return {"video": VIDEO_MB, "image": IMAGE_MB, "audio": AUDIO_MB}.get(kind, IMAGE_MB)


def upload_file(path: str | Path, *, purpose: str = PURPOSE) -> str:
    """Upload one local file and return the MiniMax file id.

    Cached by content hash for the process lifetime; MiniMax expires uploaded
    files after seven days, so a long-lived process may need a restart or a
    different file before then. A failed upload is never cached.
    """
    target = Path(path)
    if not target.is_file():
        raise RuntimeError(f"素材不存在：{target}")
    kind = _kind(target)
    if target.stat().st_size > _limit_mb(kind) * 1024 * 1024:
        raise RuntimeError(f"{kind} 超过 MiniMax 单文件上限 {_limit_mb(kind)}MB")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with _LOCK:
        cached = _CACHE.get(digest)
    if cached:
        return cached

    key = _key()
    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    errors: list[str] = []
    for base in (CN_BASE, GLOBAL_BASE):
        try:
            with target.open("rb") as handle:
                files = {"file": (target.name, handle, mime)}
                data = {"purpose": purpose}
                headers = {"Authorization": f"Bearer {key}"}
                with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                    res = client.post(f"{base}/v1/files/upload", headers=headers, data=data, files=files)
            if res.status_code >= 400:
                errors.append(f"{base}: HTTP {res.status_code} {res.text[:240]}")
                continue
            body: Any = res.json()
            file_id = ""
            if isinstance(body, dict):
                file_id = str(body.get("file_id") or (body.get("file") or {}).get("file_id") or (body.get("file") or {}).get("id") or "")
            if not file_id:
                errors.append(f"{base}: 上传成功但没有 file_id {str(body)[:200]}")
                continue
            with _LOCK:
                _CACHE[digest] = file_id
            return file_id
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{base}: {type(exc).__name__}: {exc}")
            continue
    raise RuntimeError("MiniMax Files API 上传失败：" + " | ".join(errors)[:800])


def mm_file(file_id: str) -> str:
    return f"mm_file://{file_id}"
