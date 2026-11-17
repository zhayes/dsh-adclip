"""Image-model view over the shared catalogue.

Image rows live in `catalog.py` next to the video rows; this module keeps the
image-shaped helpers the image pipeline imports.
"""
from __future__ import annotations

from typing import Any

from . import catalog as model_catalog


def catalog_rows() -> list[dict[str, Any]]:
    return model_catalog.for_kind("image")


def catalog() -> list[dict[str, Any]]:
    return model_catalog.for_kind("image")


def get_model(model_id: str) -> dict[str, Any] | None:
    row = model_catalog.get(model_id)
    return row if row and row["kind"] == "image" else None


def default_model() -> str:
    return model_catalog.default_model("image", "text_to_image")


def size_for(area: str, aspect: str) -> str:
    """Pixel size for providers that take explicit dimensions, not presets.

    The short edge follows the area (1K/2K/4K); the other edge keeps the aspect
    ratio and lands on a multiple of 16, which every image API we target accepts.
    """
    short = {"1K": 1024, "2K": 2048, "4K": 4096}.get(str(area).upper(), 2048)
    ratios = {"1:1": (1, 1), "4:3": (4, 3), "3:4": (3, 4), "16:9": (16, 9), "9:16": (9, 16)}
    width_units, height_units = ratios.get(aspect, (1, 1))
    if width_units >= height_units:
        width = short
        height = round(short * height_units / width_units / 16) * 16
    else:
        height = short
        width = round(short * width_units / height_units / 16) * 16
    return f"{max(16, width)}x{max(16, height)}"
