"""Model catalogue, scenario manifests and video parameter helpers.

No prices are exposed anywhere. The catalogue only answers: can this model be
used, which modes/durations/aspects does it support, and is native audio on.
"""
from __future__ import annotations

import os
import time
from typing import Any

from . import settings


def _has(*names: str) -> bool:
    return all(bool(os.environ.get(name)) for name in names)


# The first slice ships with a local demo provider. Real adapters are wired in
# the next step; their entries stay unavailable until the adapter exists.
MODELS: list[dict[str, Any]] = [
    {
        "id": "demo",
        "provider": "demo",
        "model": "local-demo",
        "label": "Demo（本地占位）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [5, 8, 10, 12, 15, 30],
        "resolutions": ["480p", "720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 30,
        "requires": [],
        "available": True,
        "adapter_ready": True,
        "reason": "本地占位，不调用模型",
        "tags": ["本地", "无模型调用"],
    },
    {
        "id": "ark.seedance-2.5",
        "provider": "ark",
        "model": "doubao-seedance-2-5-260628",
        "label": "Seedance 2.5（火山方舟）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [4, 5, 8, 10, 12, 15, 30],
        "resolutions": ["480p", "720p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 30,
        "requires": ["ARK_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "适配器已实现；配置 ARK_API_KEY 后待真实账号实测",
        "tags": ["中文对白首选", "原生音频"],
    },
    {
        "id": "ark.seedance-2.0",
        "provider": "ark",
        "model": "doubao-seedance-2-0-260128",
        "label": "Seedance 2.0（火山方舟）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "适配器已实现；配置 ARK_API_KEY 后待真实账号实测",
        "tags": ["原生音频", "中文"],
    },
    {
        "id": "ark.seedance-2.0-mini",
        "provider": "ark",
        "model": "doubao-seedance-2-0-mini-260615",
        "label": "Seedance 2.0 Mini（火山方舟）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "真实账号已实测：720p 原生中文对白可用",
        "tags": ["Mini", "原生音频", "已实测"],
    },
    {
        "id": "ark.seedance-2.0-fast",
        "provider": "ark",
        "model": "doubao-seedance-2-0-fast-260128",
        "label": "Seedance 2.0 Fast（火山方舟）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [4, 5, 8, 10, 12, 15],
        "resolutions": ["480p", "720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["ARK_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "真实账号已实测：720p 原生中文对白可用",
        "tags": ["Fast", "原生音频", "已实测"],
    },
    {
        "id": "kling.v3",
        "provider": "kling",
        "model": "kling-v3",
        "label": "Kling v3（可灵）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video", "reference_to_video"],
        "durations": [3, 5, 8, 10, 12, 15],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1"],
        "max_duration_s": 15,
        "requires": ["KLING_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "适配器已实现；配置 KLING_API_KEY 后待真实账号实测",
        "tags": ["1080p 候选", "原生音频"],
    },
    {
        "id": "minimax.hailuo-2.3-fast",
        "provider": "minimax",
        "model": "MiniMax-Hailuo-2.3-Fast",
        "label": "MiniMax Hailuo 2.3 Fast（图生视频）",
        "native_audio": False,
        "modes": ["image_to_video"],
        "durations": [6, 10],
        "resolutions": ["768P", "1080P"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 10,
        "requires": ["MINIMAX_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "图生视频已实测；无原生音频，只适合纯画面/后期配乐",
        "tags": ["图生视频已验证", "无原生音频"],
    },
    {
        "id": "minimax.h3",
        "provider": "minimax",
        "model": "MiniMax-H3",
        "label": "MiniMax H3（2K · 原生对白）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video"],
        "durations": [4, 5, 6, 8, 10, 12, 15],
        "resolutions": ["2K"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 15,
        "requires": ["MINIMAX_API_KEY"],
        "available": False,
        "adapter_ready": True,
        "reason": "2K 适配器已实测：中文原生对白可用",
        "tags": ["2K", "中文原生对白已验证"],
    },
    {
        "id": "volcengine.jimeng-3.0",
        "provider": "volcengine",
        "model": "jimeng_ti2v_v30_pro",
        "label": "火山引擎即梦 3.0 Pro",
        "native_audio": False,
        "modes": ["text_to_video", "image_to_video"],
        "durations": [5, 10],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"],
        "max_duration_s": 10,
        "requires": ["VOLC_ACCESSKEY", "VOLC_SECRETKEY"],
        "available": False,
        "reason": "无原生对白；只做无对白 B-roll",
        "tags": ["无原生对白"],
    },
    {
        "id": "veo.3.1",
        "provider": "fal",
        "model": "veo-3.1-generate-001",
        "label": "Veo 3.1（可选）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video"],
        "durations": [8],
        "resolutions": ["720p", "1080p"],
        "aspects": ["9:16", "16:9"],
        "max_duration_s": 8,
        "requires": ["FAL_KEY"],
        "available": False,
        "reason": "可选海外通道，未接入",
        "tags": ["海外", "原生音频"],
    },
    {
        "id": "sora.2",
        "provider": "fal",
        "model": "sora-2",
        "label": "Sora 2（可选）",
        "native_audio": True,
        "modes": ["text_to_video", "image_to_video"],
        "durations": [10, 15],
        "resolutions": ["720p"],
        "aspects": ["9:16", "16:9"],
        "max_duration_s": 15,
        "requires": ["FAL_KEY", "OPENAI_API_KEY"],
        "available": False,
        "reason": "可选海外通道，未接入",
        "tags": ["海外", "原生音频"],
    },
]


def catalog() -> list[dict[str, Any]]:
    """Return the catalogue with live key presence and availability."""
    rows: list[dict[str, Any]] = []
    enabled = settings.enabled_models()
    for row in MODELS:
        item = dict(row)
        # No preference file means all models are enabled by default. Once the
        # operator saves checkboxes, only the listed ids appear in generation.
        item["enabled"] = True if enabled is None else item["id"] in enabled
        item["key_present"] = all(_has(name) for name in item.get("requires", []))
        if item.get("adapter_ready") and item["id"] != "demo":
            item["available"] = bool(item["key_present"])
            if not item["key_present"]:
                item["reason"] = "未配置 " + " / ".join(item.get("requires", []))
        item["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        rows.append(item)
    return rows


def get_model(model_id: str) -> dict[str, Any] | None:
    for row in catalog():
        if row["id"] == model_id:
            return row
    return None


def available_models(mode: str | None = None) -> list[dict[str, Any]]:
    rows = [row for row in catalog() if row.get("available")]
    if mode:
        rows = [row for row in rows if mode in (row.get("modes") or [])]
    return rows


def default_model() -> str:
    return "demo"


def supports(model_id: str, key: str, value: Any) -> bool:
    model = get_model(model_id)
    if model is None:
        return False
    if key == "duration":
        return any(float(value) <= float(item) for item in model.get("durations", []))
    if key == "resolution":
        return value in (model.get("resolutions") or [])
    if key == "aspect":
        return value in (model.get("aspects") or [])
    if key == "native_audio":
        return bool(model.get("native_audio")) or not value
    return True


ASPECT_SIZES = {
    "480p": {
        "9:16": (480, 854), "16:9": (854, 480), "1:1": (480, 480),
        "4:3": (640, 480), "3:4": (480, 640), "21:9": (896, 384),
    },
    "720p": {
        "9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720),
        "4:3": (960, 720), "3:4": (720, 960), "21:9": (1280, 548),
    },
    "1080p": {
        "9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080),
        "4:3": (1440, 1080), "3:4": (1080, 1440), "21:9": (1920, 822),
    },
    "4k": {
        "9:16": (2160, 3840), "16:9": (3840, 2160), "1:1": (2160, 2160),
        "4:3": (2880, 2160), "3:4": (2160, 2880), "21:9": (3840, 1644),
    },
}


def size_for(aspect: str, resolution: str) -> tuple[int, int]:
    bucket = ASPECT_SIZES.get(resolution) or ASPECT_SIZES["720p"]
    return bucket.get(aspect) or bucket["9:16"]


DEFAULT_ADVANCED = {
    "generation_mode": "fast",
    "duration": 12,
    "aspect": "9:16",
    "resolution": "720p",
    "model": "auto",
    "fidelity": "balanced",
    "language": "zh",
    "native_audio": True,
    "subtitle": "sidecar",
    "subtitle_size": 32,
    "music": "off",
    "export_bitrate": "8M",
    "fps": 30,
    "aigc_label": True,
}


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "viral-remake",
        "label": "爆款复刻",
        "status": "ready",
        "description": "学习参考片的结构和节奏，换成你的商品重拍",
        "inputs": [
            {"key": "reference", "type": "video", "label": "参考视频", "required": True, "max_duration_s": 30},
            {"key": "product_images", "type": "image[]", "label": "商品图", "required": False, "max_items": 9},
            {"key": "brief", "type": "text", "label": "产品信息、卖点、价格及修改要求", "max_length": 2000},
        ],
        "advanced": [
            {"key": "generation_mode", "label": "生成模式", "type": "enum", "options": ["fast", "fine"], "default": "fast"},
            {"key": "duration", "label": "时长", "type": "enum", "options": [5, 8, 10, 12, 15, 30], "default": 12},
            {"key": "aspect", "label": "比例", "type": "enum", "options": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"], "default": "9:16"},
            {"key": "resolution", "label": "清晰度", "type": "enum", "options": ["480p", "720p", "1080p"], "default": "720p"},
            {"key": "model", "label": "模型", "type": "model", "default": "auto"},
        ],
        "examples": [],
    },
    {
        "id": "text-to-video",
        "label": "文生视频",
        "status": "ready",
        "description": "一句描述生成一段视频",
        "inputs": [
            {"key": "brief", "type": "text", "label": "描述产品、场景、动作、镜头和氛围", "required": True, "max_length": 1000},
            {"key": "reference_image", "type": "image", "label": "参考图（可选）", "required": False},
        ],
        "advanced": [
            {"key": "duration", "label": "时长", "type": "enum", "options": [5, 8, 10, 12, 15, 30], "default": 8},
            {"key": "aspect", "label": "比例", "type": "enum", "options": ["9:16", "16:9", "1:1"], "default": "9:16"},
            {"key": "resolution", "label": "清晰度", "type": "enum", "options": ["480p", "720p", "1080p"], "default": "720p"},
            {"key": "model", "label": "模型", "type": "model", "default": "auto"},
        ],
        "examples": [],
    },
    {
        "id": "video-fission",
        "label": "视频裂变",
        "status": "coming_soon",
        "description": "一条模板出多组变体",
        "inputs": [],
        "advanced": [],
        "examples": [],
    },
]


def scenario(scenario_id: str) -> dict[str, Any] | None:
    for row in SCENARIOS:
        if row["id"] == scenario_id:
            return row
    return None


def merged_advanced(values: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_ADVANCED)
    out.update(values or {})
    return out
