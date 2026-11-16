"""Image-generation model catalogue.

Deliberately separate from the video catalogue: video models are not image
models, and image models do not participate in the video model enable list.
"""
from __future__ import annotations

import os
import time
from typing import Any

IMAGE_MODELS: list[dict[str, Any]] = [
    {
        "id": "minimax.h3-image",
        "provider": "minimax",
        "model": "MiniMax-H3-Image",
        "label": "MiniMax H3 Image",
        "aspects": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "areas": ["1K", "2K", "4K"],
        "default_area": "2K",
        "requires": ["MINIMAX_API_KEY"],
        "available": False,
        "reason": "配置 MINIMAX_API_KEY 后可用",
        "tags": ["文生图", "MiniMax"],
    },
    {
        "id": "minimax.h3-image-highspeed",
        "provider": "minimax",
        "model": "MiniMax-H3-Image-Highspeed",
        "label": "MiniMax H3 Image Highspeed",
        "aspects": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "areas": ["1K", "2K", "4K"],
        "default_area": "2K",
        "requires": ["MINIMAX_API_KEY"],
        "available": False,
        "reason": "配置 MINIMAX_API_KEY 后可用",
        "tags": ["文生图", "快速"],
    },
]


def catalog() -> list[dict[str, Any]]:
    available = bool(os.environ.get("MINIMAX_API_KEY", "").strip())
    rows = []
    for row in IMAGE_MODELS:
        item = dict(row)
        item["available"] = available
        if available:
            item["reason"] = "MiniMax key 已配置；生成时按账号权限为准"
        item["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        rows.append(item)
    return rows


def get_model(model_id: str) -> dict[str, Any] | None:
    for row in catalog():
        if row["id"] == model_id:
            return row
    return None


def default_model() -> str:
    rows = [row for row in catalog() if row["available"]]
    return rows[0]["id"] if rows else ""
