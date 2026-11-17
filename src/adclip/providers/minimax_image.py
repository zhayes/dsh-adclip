"""MiniMax H3 Image text-to-image adapter."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import httpx

CN_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
GLOBAL_BASE = os.environ.get("MINIMAX_GLOBAL_BASE", "https://api.minimax.io").rstrip("/")


def _api_key() -> str:
    return os.environ.get("MINIMAX_API_KEY", "").strip()


def generate(
    prompt: str,
    *,
    model: str = "MiniMax-H3-Image",
    aspect: str = "1:1",
    area: str = "2K",
    output: Path,
    reference: Path | None = None,
) -> dict:
    key = _api_key()
    if not key:
        raise RuntimeError("未配置 MINIMAX_API_KEY")
    # H3 Image is text-to-image only; `reference` exists so the runner can call
    # every adapter with one signature.
    body = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect,
        "area": area,
        "output_format": "jpeg",
        "response_format": "url",
        "n": 1,
    }
    errors = []
    for base in (CN_BASE, GLOBAL_BASE):
        try:
            with httpx.Client(timeout=httpx.Timeout(650.0, connect=15.0)) as client:
                response = client.post(f"{base}/v1/images/generations", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
                if response.status_code >= 400:
                    message = response.text[:400]
                    try:
                        payload = response.json()
                        message = str((payload.get("error") or {}).get("message") or payload)
                    except Exception:
                        pass
                    raise RuntimeError(f"MiniMax 图片生成失败 HTTP {response.status_code}: {message}")
                data = response.json()
                rows = data.get("data") or []
                if not rows:
                    raise RuntimeError("MiniMax 图片接口没有返回 data")
                item = rows[0]
                if item.get("error"):
                    err = item["error"]
                    raise RuntimeError(f"MiniMax 图片生成失败: {err.get('message') or err}")
                output.parent.mkdir(parents=True, exist_ok=True)
                if item.get("b64_json"):
                    output.write_bytes(base64.b64decode(item["b64_json"]))
                elif item.get("url"):
                    with client.stream("GET", item["url"], timeout=180.0) as download:
                        download.raise_for_status()
                        with output.open("wb") as handle:
                            for chunk in download.iter_bytes():
                                handle.write(chunk)
                else:
                    raise RuntimeError("MiniMax 图片结果既没有 url 也没有 b64_json")
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError("MiniMax 图片下载为空")
                size = str(item.get("size") or "")
                width = height = None
                if "x" in size:
                    try:
                        width, height = [int(x) for x in size.lower().split("x", 1)]
                    except ValueError:
                        pass
                return {"model": model, "path": str(output), "size": size, "width": width, "height": height}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")
            if "insufficient" in str(exc).lower() or "1008" in str(exc):
                break
            continue
    raise RuntimeError("MiniMax 图片生成失败：" + " | ".join(errors)[:800])
