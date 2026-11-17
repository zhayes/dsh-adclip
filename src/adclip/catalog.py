"""One catalogue for every model the plugin can drive.

Each row declares what it is (`kind`), what it can do (`capabilities`), what it
costs to be usable (`requires`), and how it is parameterised. Generation pages
filter on `capabilities`; nothing in the UI or the pipeline matches model ids.

Capability vocabulary (fixed):
  video: text_to_video, image_to_video, reference_to_video
  image: text_to_image, image_to_image
"""
from __future__ import annotations

import os
import time
from typing import Any

from . import capabilities, settings

VIDEO_CAPABILITIES = ("text_to_video", "image_to_video", "reference_to_video")
IMAGE_CAPABILITIES = ("text_to_image", "image_to_image")

VIDEO_ROWS: list[dict[str, Any]] = [
    {
        "id": "ark.seedance-2.5",
        "kind": "video",
        "provider": "ark",
        "model": "doubao-seedance-2-5-260628",
        "label": "Seedance 2.5（火山方舟）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [4, 5, 8, 10, 12, 15, 30],
        "resolutions": ["480p", "720p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 30,
        "requires": ["ARK_API_KEY"],
        "adapter_ready": True,
        "tags": ["中文对白首选", "原生音频"],
        "reason": "未配置 ARK_API_KEY",
    },
    {
        "id": "ark.seedance-2.0",
        "kind": "video",
        "provider": "ark",
        "model": "doubao-seedance-2-0-260128",
        "label": "Seedance 2.0（火山方舟）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "adapter_ready": True,
        "tags": ["原生音频", "中文"],
        "reason": "未配置 ARK_API_KEY",
    },
    {
        "id": "ark.seedance-2.0-mini",
        "kind": "video",
        "provider": "ark",
        "model": "doubao-seedance-2-0-mini-260615",
        "label": "Seedance 2.0 Mini（火山方舟）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "adapter_ready": True,
        "tags": ["Mini", "原生音频", "最高 720p", "已实测"],
        "reason": "未配置 ARK_API_KEY",
    },
    {
        "id": "ark.seedance-2.0-fast",
        "kind": "video",
        "provider": "ark",
        "model": "doubao-seedance-2-0-fast-260128",
        "label": "Seedance 2.0 Fast（火山方舟）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "adapter_ready": True,
        "tags": ["Fast", "原生音频", "最高 720p", "已实测"],
        "reason": "未配置 ARK_API_KEY",
    },
    {
        "id": "kling.v3",
        "kind": "video",
        "provider": "kling",
        "model": "kling-v3",
        "label": "Kling v3（可灵）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [3, 5, 8, 10, 12, 15],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1"],
        "max_duration_s": 15,
        "requires": ["KLING_API_KEY"],
        "adapter_ready": True,
        "tags": ["1080p 候选", "原生音频"],
        "reason": "未配置 KLING_API_KEY",
    },
    {
        "id": "minimax.hailuo-2.3-fast",
        "kind": "video",
        "provider": "minimax",
        "model": "MiniMax-Hailuo-2.3-Fast",
        "label": "MiniMax Hailuo 2.3 Fast（图生视频）",
        "capabilities": ["image_to_video"],
        "native_audio": False,
        "durations": [6, 10],
        "resolutions": ["768P", "1080P"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 10,
        "requires": ["MINIMAX_API_KEY"],
        "adapter_ready": True,
        "tags": ["图生视频已验证", "无原生音频"],
        "reason": "未配置 MINIMAX_API_KEY",
    },
    {
        "id": "minimax.h3",
        "kind": "video",
        "provider": "minimax",
        "model": "MiniMax-H3",
        "label": "MiniMax H3（参考复刻 · 原生对白）",
        "capabilities": ["text_to_video", "image_to_video", "reference_to_video"],
        "native_audio": True,
        "durations": [4, 5, 6, 8, 10, 12, 15],
        "resolutions": ["768P", "2K"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["MINIMAX_API_KEY"],
        "adapter_ready": True,
        "tags": ["768P/2K", "中文原生对白已验证", "完整复刻首选"],
        "reason": "未配置 MINIMAX_API_KEY",
    },
    {
        "id": "volcengine.jimeng-3.0",
        "kind": "video",
        "provider": "volcengine",
        "model": "jimeng_ti2v_v30_pro",
        "label": "火山引擎即梦 3.0 Pro",
        "capabilities": ["text_to_video", "image_to_video"],
        "native_audio": False,
        "durations": [5, 10],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 10,
        "requires": ["VOLC_ACCESSKEY", "VOLC_SECRETKEY"],
        "adapter_ready": False,
        "tags": ["无原生对白"],
        "reason": "适配器未接入",
    },
    {
        "id": "veo.3.1",
        "kind": "video",
        "provider": "fal",
        "model": "veo-3.1-generate-001",
        "label": "Veo 3.1（可选）",
        "capabilities": ["text_to_video", "image_to_video"],
        "native_audio": True,
        "durations": [8],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9"],
        "max_duration_s": 8,
        "requires": ["FAL_KEY"],
        "adapter_ready": False,
        "tags": ["海外", "原生音频"],
        "reason": "适配器未接入",
    },
    {
        "id": "sora.2",
        "kind": "video",
        "provider": "fal",
        "model": "sora-2",
        "label": "Sora 2（可选）",
        "capabilities": ["text_to_video", "image_to_video"],
        "native_audio": True,
        "durations": [10, 15],
        "resolutions": ["720p"],
        "aspects": ["9:16", "16:9"],
        "max_duration_s": 15,
        "requires": ["FAL_KEY", "OPENAI_API_KEY"],
        "adapter_ready": False,
        "tags": ["海外", "原生音频"],
        "reason": "适配器未接入",
    },
]

IMAGE_ROWS: list[dict[str, Any]] = [
    {
        "id": "minimax.h3-image",
        "kind": "image",
        "provider": "minimax",
        "model": "MiniMax-H3-Image",
        "label": "MiniMax H3 Image",
        "capabilities": ["text_to_image"],
        "aspects": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "areas": ["1K", "2K", "4K"],
        "default_area": "2K",
        "requires": ["MINIMAX_API_KEY"],
        "adapter_ready": True,
        "tags": ["文生图"],
        "reason": "未配置 MINIMAX_API_KEY",
    },
    {
        "id": "minimax.h3-image-highspeed",
        "kind": "image",
        "provider": "minimax",
        "model": "MiniMax-H3-Image-Highspeed",
        "label": "MiniMax H3 Image Highspeed",
        "capabilities": ["text_to_image"],
        "aspects": ["1:1", "3:4", "4:3", "9:16", "16:9"],
        "areas": ["1K", "2K", "4K"],
        "default_area": "2K",
        "requires": ["MINIMAX_API_KEY"],
        "adapter_ready": True,
        "tags": ["文生图", "快速"],
        "reason": "未配置 MINIMAX_API_KEY",
    },
    {
        "id": "ark.seedream-4.0",
        "kind": "image",
        "provider": "ark",
        "model": "doubao-seedream-4-0-20260415",
        "label": "Doubao-Seedream 4.0（火山方舟）",
        "capabilities": ["text_to_image", "image_to_image"],
        "aspects": ["1:1", "4:3", "3:4", "16:9", "9:16"],
        "areas": ["1K", "2K", "4K"],
        "default_area": "2K",
        "requires": ["ARK_API_KEY"],
        "adapter_ready": True,
        "tags": ["4K", "参考图生图已验证", "中文提示"],
        "reason": "未配置 ARK_API_KEY",
    },
]

TEST_ROW: dict[str, Any] = {
    "id": "test.synthetic",
    "kind": "video",
    "provider": "synthetic",
    "model": "synthetic",
    "label": "Synthetic（测试）",
    "capabilities": list(VIDEO_CAPABILITIES),
    "native_audio": True,
    "durations": [4, 5, 6, 8, 10, 12, 15, 30],
    "resolutions": ["480p", "720p", "1080p"],
    "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
    "max_duration_s": 30,
    "requires": [],
    "adapter_ready": True,
    "tags": ["测试"],
    "reason": "",
}


def test_mode() -> bool:
    return os.environ.get("ADCLIP_TEST_MODE", "").strip() == "1"


def base_rows() -> list[dict[str, Any]]:
    rows = [*VIDEO_ROWS, *IMAGE_ROWS]
    if test_mode():
        rows.append(TEST_ROW)
    return rows


def evaluate(row: dict[str, Any], enabled_ids: list[str] | None = None, kind_has_ids: dict[str, bool] | None = None) -> dict[str, Any]:
    """Live view of one row: keys present, usable, enabled, short reason.

    `enabled_ids` is the saved preference list; `None` means "no preference file
    yet". A kind with no saved ids at all stays enabled, so a prefs file written
    before that kind existed does not hide it.
    """
    item = capabilities.merge(dict(row))
    item.setdefault("capabilities", [])
    if item["kind"] == "video":
        item["modes"] = list(item["capabilities"])
    requires = [str(name) for name in item.get("requires") or []]
    item["key_present"] = all(bool(os.environ.get(name, "").strip()) for name in requires)
    item["available"] = bool(item.get("adapter_ready", True)) and (not requires or item["key_present"])
    if not item.get("adapter_ready", True):
        item["reason"] = "适配器未接入"
    elif requires and not item["key_present"]:
        item["reason"] = "未配置 " + " / ".join(requires)
    else:
        item["reason"] = str(item.get("reason") or "")
    if enabled_ids is None:
        item["enabled"] = True
    elif kind_has_ids is not None and not kind_has_ids.get(item["kind"], False):
        item["enabled"] = True
    else:
        item["enabled"] = item["id"] in enabled_ids
    try:
        item["default_params"] = {**item.get("default_params", {}), **settings.model_params_for(item["id"])}
    except Exception:
        pass
    item["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return item


def rows() -> list[dict[str, Any]]:
    """Every model with live availability and enablement."""
    enabled_ids = settings.enabled_models()
    base = base_rows()
    kind_has_ids = {
        kind: any(row["id"] in (enabled_ids or []) for row in base if row["kind"] == kind)
        for kind in {row["kind"] for row in base}
    }
    return [evaluate(row, enabled_ids, kind_has_ids) for row in base]


def for_kind(kind: str) -> list[dict[str, Any]]:
    return [row for row in rows() if row["kind"] == kind]


def get(model_id: str) -> dict[str, Any] | None:
    for row in rows():
        if row["id"] == model_id:
            return row
    return None


def with_capability(capability: str, *, kind: str = "", usable: bool = False) -> list[dict[str, Any]]:
    rows_ = [row for row in rows() if capability in row["capabilities"]]
    if kind:
        rows_ = [row for row in rows_ if row["kind"] == kind]
    if usable:
        rows_ = [row for row in rows_ if row["available"] and row["enabled"]]
    return rows_


def default_model(kind: str, capability: str = "") -> str:
    for row in rows():
        if row["kind"] != kind or not row["available"] or not row["enabled"]:
            continue
        if capability and capability not in row["capabilities"]:
            continue
        return row["id"]
    return ""
