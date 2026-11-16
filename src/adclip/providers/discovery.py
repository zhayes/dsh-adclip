"""Best-effort vendor model discovery.

Video adapters still own the list of models they can actually call. Vendor APIs
do not consistently expose video models: MiniMax's /v1/models returns its text
models, and Kling has no public model-list endpoint. This module therefore
discovers what the vendor exposes and leaves the adapter catalogue authoritative
for video generation.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from .ark import BASE_URL as ARK_BASE

MINIMAX_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")


def _models_from_payload(payload: Any) -> list[str]:
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or []
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, str):
            out.append(row)
        elif isinstance(row, dict):
            value = row.get("id") or row.get("model") or row.get("name")
            if value:
                out.append(str(value))
    return sorted(set(out))


def _get(url: str, key: str) -> dict[str, Any]:
    if not key:
        return {"ok": False, "models": [], "error": "未配置 API key", "source": url}
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {key}"})
            if response.status_code >= 400:
                return {"ok": False, "models": [], "error": f"HTTP {response.status_code}: {response.text[:180]}", "source": url}
            return {"ok": True, "models": _models_from_payload(response.json()), "error": "", "source": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "models": [], "error": f"{type(exc).__name__}: {exc}"[:240], "source": url}


def discover() -> dict[str, Any]:
    minimax = _get(f"{MINIMAX_BASE}/v1/models", os.environ.get("MINIMAX_API_KEY", "").strip())
    ark = _get(f"{ARK_BASE}/models", os.environ.get("ARK_API_KEY", "").strip())
    # Kling's classic API has no model-list route; adapter remains authoritative.
    kling = {"ok": False, "models": [], "error": "Kling 未提供模型列表接口；使用适配器支持列表", "source": "adapter"}
    return {"minimax": minimax, "ark": ark, "kling": kling}
