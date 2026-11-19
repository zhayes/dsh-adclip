"""Model catalogue views, scenario manifests and video parameter helpers.

The rows live in `catalog.py`, which knows both video and image models. This
module keeps the video-shaped helpers the pipeline already imports, so callers
can keep asking for "the video models" without knowing about kinds.
"""
from __future__ import annotations

from typing import Any

from . import catalog as model_catalog


def catalog_rows() -> list[dict[str, Any]]:
    return model_catalog.for_kind("video")


def catalog() -> list[dict[str, Any]]:
    """Video models with live key presence and availability."""
    return model_catalog.for_kind("video")


def get_model(model_id: str) -> dict[str, Any] | None:
    row = model_catalog.get(model_id)
    return row if row and row["kind"] == "video" else None


def available_models(capability: str | None = None) -> list[dict[str, Any]]:
    rows = [row for row in model_catalog.for_kind("video") if row.get("available")]
    if capability:
        rows = [row for row in rows if capability in (row.get("capabilities") or [])]
    return rows


def default_model() -> str:
    return model_catalog.default_model("video", "text_to_video")


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
    "duration": 12,
    "aspect": "9:16",
    "resolution": "720p",
    "model": "auto",
    "remake_mode": "auto",
    "replace_scope": "both",
    "person_scope": "main",
    "audio_mode": "regenerate",
    "subtitle": "off",
    "prompt_confirm": True,
    "export_bitrate": "8M",
    "fps": 30,
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
            {"key": "duration", "label": "时长", "type": "enum", "options": [5, 8, 10, 12, 15, 30], "default": 12},
            {"key": "aspect", "label": "比例", "type": "enum", "options": ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"], "default": "9:16"},
            {"key": "resolution", "label": "清晰度", "type": "enum", "options": ["480p", "720p", "1080p"], "default": "720p"},
            {"key": "model", "label": "模型", "type": "model", "default": "auto"},
            {"key": "remake_mode", "label": "复刻模式", "type": "enum", "options": ["auto"], "default": "auto"},
            {"key": "replace_scope", "label": "替换内容", "type": "enum", "options": ["both", "product", "person"], "default": "both"},
            {"key": "person_scope", "label": "人物范围", "type": "enum", "options": ["main", "all"], "default": "main"},
            {"key": "audio_mode", "label": "声音", "type": "enum", "options": ["regenerate", "preserve"], "default": "regenerate"},
            {"key": "subtitle", "label": "字幕", "type": "enum", "options": ["off", "sidecar"], "default": "off"},
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
            {"key": "subtitle", "label": "字幕", "type": "enum", "options": ["off", "sidecar"], "default": "off"},
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


def enforce_remake_audio(advanced: dict[str, Any]) -> dict[str, Any]:
    """A changed product needs its own name in the spoken copy.

    Preserving the source track is only valid when the product stays the same.
    The engine coerces the unsafe combination instead of trusting a client.
    """
    out = dict(advanced or {})
    scope = str(out.get("replace_scope") or "both")
    if scope in {"both", "product"} and str(out.get("audio_mode") or "regenerate") == "preserve":
        out["audio_mode"] = "regenerate"
        out["audio_mode_forced"] = True
    return out


def scenario(scenario_id: str) -> dict[str, Any] | None:
    for row in SCENARIOS:
        if row["id"] == scenario_id:
            return row
    return None


def scenario_defaults(scenario_id: str) -> dict[str, Any]:
    """Defaults declared by one scenario, without the global remake defaults."""
    scenario = next((row for row in SCENARIOS if row.get("id") == scenario_id), None)
    if scenario is None:
        return {}
    return {
        str(field.get("key")): field.get("default")
        for field in scenario.get("advanced") or []
        if field.get("key") and "default" in field
    }


def merged_advanced(values: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_ADVANCED)
    out.update(values or {})
    return out
