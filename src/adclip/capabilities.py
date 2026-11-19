"""Per-model capability and parameter definitions.

The catalogue owns the model rows; this module adds the machine-readable
contract around them: what goes in, what comes out, which parameters the
adapter accepts, what the model can do for a viral remake, and an internal
cost/quality weight the planner uses. It deliberately carries no currency or
billing numbers: AdClip has no pricing surface.
"""
from __future__ import annotations

import copy
from typing import Any

TIER_RANK = {
    "full": 3,
    "reference": 2,
    "generation": 1,
    "image_only": 0,
}

_RATIOS = ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9", "adaptive"]
_REFERENCE_VIDEO = {
    "max": 3,
    "roles": ["reference_video"],
    "min_s": 2,
    "max_s": 15,
    "total_s": 15,
    "max_mb": 50,
}
_REFERENCE_IMAGE = {
    "max": 9,
    "roles": ["reference_image", "first_frame", "last_frame"],
    "max_mb": 30,
}
_REFERENCE_AUDIO = {
    "max": 3,
    "roles": ["reference_audio"],
    "min_s": 2,
    "max_s": 15,
    "total_s": 15,
    "max_mb": 15,
}


def _video_io(*, videos: bool = True, audio: bool = True) -> dict[str, Any]:
    io: dict[str, Any] = {
        "text": {"required": True},
        "images": copy.deepcopy(_REFERENCE_IMAGE),
    }
    if videos:
        io["videos"] = copy.deepcopy(_REFERENCE_VIDEO)
    if audio:
        io["audio"] = copy.deepcopy(_REFERENCE_AUDIO)
    return io


def _video_params(
    *,
    duration_max: int,
    resolutions: list[str],
    default_resolution: str,
    task_type: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "duration": {"type": "integer", "min": 4, "max": duration_max, "follow_reference": True},
        "resolution": {"type": "string", "enum": resolutions, "default": default_resolution},
        "ratio": {"type": "string", "enum": _RATIOS, "default": "adaptive"},
        "generate_audio": {"type": "boolean", "default": True},
        "watermark": {"type": "boolean", "default": False},
        "return_last_frame": {"type": "boolean", "default": False},
    }
    if task_type:
        params["task_type"] = {"type": "string", "enum": ["reference", "edit", "extend"], "default": "reference"}
    return params


SEEDANCE_IO = _video_io()


# `remake.reference_video_ready` says whether the adapter can actually send the
# reference video to that model. A `reference` tier row without it is only
# usable as a plain generation model, and the rung is skipped with a reason.
SPECS: dict[str, dict[str, Any]] = {
    "minimax.h3": {
        "io": _video_io(),
        "params": {
            "duration": {"type": "integer", "min": 4, "max": 15, "follow_reference": True},
            "resolution": {"type": "string", "enum": ["768P", "2K"], "default": "768P"},
            "ratio": {"type": "string", "enum": ["adaptive"], "default": "adaptive"},
            "audio": {"type": "string", "enum": ["preserve", "generate"], "default": "preserve"},
        },
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "full",
            "supports": [
                "reference_video",
                "reference_image",
                "person_replace",
                "product_replace",
                "structure_preserve",
                "audio_preserve",
            ],
            "real_person_reference": "allowed",
            "priority": 100,
            "cost_weight": 0.35,
            "reference_video_ready": True,
        },
        "quality": {"structure": 0.95, "identity": 0.9, "product": 0.9},
        "default_params": {"resolution": "768P", "duration": "reference", "audio": "preserve"},
    },
    "ark.seedance-2.5": {
        "io": SEEDANCE_IO,
        "params": _video_params(duration_max=30, resolutions=["480p", "720p"], default_resolution="720p", task_type=True),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "reference",
            "supports": ["reference_video", "reference_image", "video_edit", "video_extend", "native_audio"],
            "real_person_reference": "restricted",
            "priority": 90,
            "cost_weight": 0.6,
            "reference_video_ready": False,
        },
        "quality": {"structure": 0.85, "identity": 0.8, "product": 0.8},
        "default_params": {"resolution": "720p", "generate_audio": True, "watermark": False},
    },
    "ark.seedance-2.0": {
        "io": SEEDANCE_IO,
        "params": _video_params(
            duration_max=15,
            resolutions=["480p", "720p", "1080p", "4k"],
            default_resolution="1080p",
            task_type=True,
        ),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "reference",
            "supports": ["reference_video", "reference_image", "video_edit", "video_extend", "native_audio"],
            "real_person_reference": "restricted",
            "priority": 80,
            "cost_weight": 0.7,
            "reference_video_ready": False,
        },
        "quality": {"structure": 0.85, "identity": 0.8, "product": 0.8},
        "default_params": {"resolution": "1080p", "generate_audio": True, "watermark": False},
    },
    "ark.seedance-2.0-fast": {
        "io": SEEDANCE_IO,
        "params": _video_params(
            duration_max=15,
            resolutions=["480p", "720p"],
            default_resolution="720p",
            task_type=True,
        ),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "generation",
            "supports": ["reference_video", "reference_image", "video_edit", "video_extend", "native_audio"],
            "real_person_reference": "restricted",
            "priority": 60,
            "cost_weight": 0.3,
        },
        "quality": {"structure": 0.75, "identity": 0.7, "product": 0.7},
        "default_params": {"resolution": "720p", "generate_audio": True, "watermark": False},
    },
    "ark.seedance-2.0-mini": {
        "io": SEEDANCE_IO,
        "params": _video_params(
            duration_max=15,
            resolutions=["480p", "720p"],
            default_resolution="720p",
            task_type=True,
        ),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "generation",
            "supports": ["reference_video", "reference_image", "video_edit", "video_extend", "native_audio"],
            "real_person_reference": "restricted",
            "priority": 55,
            "cost_weight": 0.25,
        },
        "quality": {"structure": 0.72, "identity": 0.68, "product": 0.68},
        "default_params": {"resolution": "720p", "generate_audio": True, "watermark": False},
    },
    "kling.v3": {
        "io": _video_io(),
        "params": _video_params(duration_max=10, resolutions=["720p", "1080p"], default_resolution="1080p"),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "reference",
            "supports": ["reference_video", "reference_image", "native_audio"],
            "real_person_reference": "unknown",
            "priority": 70,
            "cost_weight": 0.6,
            "reference_video_ready": False,
            "keyframe_ready": True,
        },
        "quality": {"structure": 0.8, "identity": 0.78, "product": 0.78},
        "default_params": {"resolution": "1080p"},
    },
    "minimax.hailuo-2.3-fast": {
        "io": {
            "text": {"required": True},
            "images": {"max": 1, "roles": ["first_frame"], "max_mb": 30},
        },
        "params": {
            "duration": {"type": "integer", "enum": [6, 10], "default": 6},
            "resolution": {"type": "string", "enum": ["768P", "1080P"], "default": "768P"},
        },
        "output": {"video": True, "audio": False},
        "remake": {
            "tier": "image_only",
            "supports": ["image_to_video"],
            "real_person_reference": "unknown",
            "priority": 20,
            "cost_weight": 0.3,
            "keyframe_ready": True,
        },
        "quality": {"structure": 0.5, "identity": 0.5, "product": 0.5},
        "default_params": {"resolution": "768P", "duration": 6},
    },
    "volcengine.jimeng-3.0": {
        "io": _video_io(videos=False, audio=False),
        "params": _video_params(duration_max=10, resolutions=["720p", "1080p"], default_resolution="720p"),
        "output": {"video": True, "audio": False},
        "remake": {
            "tier": "generation",
            "supports": ["text_to_video", "image_to_video"],
            "real_person_reference": "unknown",
            "priority": 40,
            "cost_weight": 0.4,
        },
        "quality": {"structure": 0.65, "identity": 0.6, "product": 0.6},
        "default_params": {"resolution": "720p"},
    },
    "veo.3.1": {
        "io": _video_io(videos=False, audio=False),
        "params": _video_params(duration_max=8, resolutions=["720p", "1080p"], default_resolution="720p"),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "generation",
            "supports": ["text_to_video", "image_to_video", "native_audio"],
            "real_person_reference": "unknown",
            "priority": 50,
            "cost_weight": 0.8,
        },
        "quality": {"structure": 0.7, "identity": 0.65, "product": 0.65},
        "default_params": {"resolution": "720p"},
    },
    "sora.2": {
        "io": _video_io(videos=False, audio=False),
        "params": _video_params(duration_max=15, resolutions=["720p"], default_resolution="720p"),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "generation",
            "supports": ["text_to_video", "image_to_video", "native_audio"],
            "real_person_reference": "unknown",
            "priority": 45,
            "cost_weight": 0.8,
        },
        "quality": {"structure": 0.7, "identity": 0.65, "product": 0.65},
        "default_params": {"resolution": "720p"},
    },
    "minimax.h3-image": {
        "io": {"text": {"required": True}},
        "params": {
            "aspect": {"type": "string", "enum": ["1:1", "3:4", "4:3", "9:16", "16:9"], "default": "1:1"},
            "area": {"type": "string", "enum": ["1K", "2K", "4K"], "default": "2K"},
        },
        "output": {"image": True},
        "remake": {"tier": "image_only", "supports": ["text_to_image"], "priority": 0, "cost_weight": 0.4},
        "quality": {},
        "default_params": {"aspect": "1:1", "area": "2K"},
    },
    "minimax.h3-image-highspeed": {
        "io": {"text": {"required": True}},
        "params": {
            "aspect": {"type": "string", "enum": ["1:1", "3:4", "4:3", "9:16", "16:9"], "default": "1:1"},
            "area": {"type": "string", "enum": ["1K", "2K", "4K"], "default": "2K"},
        },
        "output": {"image": True},
        "remake": {"tier": "image_only", "supports": ["text_to_image"], "priority": 0, "cost_weight": 0.3},
        "quality": {},
        "default_params": {"aspect": "1:1", "area": "2K"},
    },
    "ark.seedream-4.0": {
        "io": {"text": {"required": True}, "images": {"max": 1, "roles": ["reference_image"], "max_mb": 30}},
        "params": {
            "aspect": {"type": "string", "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"], "default": "1:1"},
            "area": {"type": "string", "enum": ["1K", "2K", "4K"], "default": "4K"},
        },
        "output": {"image": True},
        "remake": {"tier": "image_only", "supports": ["text_to_image", "image_to_image"], "priority": 0, "cost_weight": 0.5},
        "quality": {},
        "default_params": {"aspect": "1:1", "area": "4K"},
    },
    "test.synthetic": {
        "io": _video_io(),
        "params": _video_params(duration_max=30, resolutions=["480p", "720p", "1080p"], default_resolution="720p"),
        "output": {"video": True, "audio": True},
        "remake": {
            "tier": "generation",
            "supports": ["text_to_video", "image_to_video"],
            "real_person_reference": "unknown",
            "priority": 999,
            "cost_weight": 0.01,
        },
        "quality": {"structure": 0.5, "identity": 0.5, "product": 0.5},
        "default_params": {"resolution": "720p", "generate_audio": True},
    },
}


def spec(model_id: str) -> dict[str, Any]:
    """Static capability spec for one model, or an empty safe default."""
    value = SPECS.get(model_id)
    if value is None:
        return {
            "io": {"text": {"required": True}},
            "params": {},
            "output": {"video": False},
            "remake": {"tier": "generation", "supports": [], "priority": 0, "cost_weight": 1.0},
            "quality": {},
            "default_params": {},
        }
    return copy.deepcopy(value)


def merge(row: dict[str, Any]) -> dict[str, Any]:
    """Return a model row with its capability fields attached."""
    item = dict(row)
    value = spec(str(row.get("id") or ""))
    for key in ("io", "params", "output", "remake", "quality", "default_params"):
        item[key] = copy.deepcopy(value[key])
    return item


def validate_params(model_id: str, values: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize saved default parameters for one model.

    Raises ``ValueError`` with a user-readable reason; callers return HTTP 400.
    """
    allowed = spec(model_id)["params"]
    clean: dict[str, Any] = {}
    for key, value in (values or {}).items():
        rule = allowed.get(str(key))
        if rule is None:
            raise ValueError(f"{model_id} 不支持参数 {key}")
        kind = rule.get("type")
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{key} 必须是布尔值")
            clean[key] = value
            continue
        if kind == "integer":
            if value == "reference" and rule.get("follow_reference"):
                clean[key] = "reference"
                continue
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} 必须是整数") from exc
            low, high = int(rule.get("min", 0)), int(rule.get("max", 1000))
            if number < low or number > high:
                raise ValueError(f"{key} 必须在 {low}–{high} 之间")
            if "enum" in rule and number not in rule["enum"]:
                raise ValueError(f"{key} 取值必须是 {rule['enum']}")
            clean[key] = number
            continue
        text = str(value)
        if "enum" in rule and text not in rule["enum"]:
            raise ValueError(f"{key} 取值必须是 {rule['enum']}")
        clean[key] = text
    return clean


def tier_rank(tier: str) -> int:
    return TIER_RANK.get(str(tier), -1)


def default_params(model_id: str) -> dict[str, Any]:
    return copy.deepcopy(spec(model_id).get("default_params") or {})


def manifest(
    rows: list[dict[str, Any]],
    *,
    text_models: list[dict[str, Any]] | None = None,
    vision_chain: list[dict[str, Any]] | None = None,
    remake_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Machine-readable capability manifest for Settings and DSH tools.

    ``text_models`` and ``vision_chain`` carry the Ark Doubao text/vision rows
    and the ordered reference-frame fallback ladder; they stay out of
    ``models`` so the video/image registry keeps its shape.
    """
    models = []
    for row in rows:
        models.append({
            "id": row.get("id"),
            "label": row.get("label"),
            "provider": row.get("provider"),
            "kind": row.get("kind"),
            "capabilities": row.get("capabilities") or [],
            "available": bool(row.get("available")),
            "enabled": bool(row.get("enabled", True)),
            "native_audio": bool(row.get("native_audio")),
            "io": row.get("io") or {},
            "params": row.get("params") or {},
            "output": row.get("output") or {},
            "remake": row.get("remake") or {},
            "quality": row.get("quality") or {},
            "default_params": row.get("default_params") or {},
        })
    payload: dict[str, Any] = {"version": 1, "models": models}
    if text_models is not None:
        payload["text_models"] = [{
            "id": row.get("id"),
            "label": row.get("label"),
            "provider": row.get("provider"),
            "kind": row.get("kind") or "text",
            "ark_model": row.get("ark_model") or "",
            "tags": row.get("tags") or [],
            "capabilities": row.get("capabilities") or [],
            "context": row.get("context") or "",
            "endpoint": row.get("endpoint") or "",
            "available": bool(row.get("available")),
            "status": row.get("status") or "",
            "reason": row.get("reason") or "",
            "checked_at": row.get("checked_at") or "",
        } for row in text_models]
    scheduling: dict[str, Any] = {}
    if vision_chain is not None:
        scheduling["vision"] = [{
            "id": row.get("id"),
            "label": row.get("label"),
            "provider": row.get("provider"),
            "available": bool(row.get("available")),
            "reason": row.get("reason") or "",
            "status": row.get("status") or "",
        } for row in vision_chain]
    if remake_chain is not None:
        scheduling["remake"] = [{
            "rung": row.get("rung"),
            "mode": row.get("mode"),
            "label": row.get("label"),
            "model": row.get("model") or "",
            "model_label": row.get("model_label") or "",
            "provider": row.get("provider") or "",
            "available": bool(row.get("available")),
            "reason": row.get("reason") or "",
        } for row in remake_chain]
    if scheduling:
        payload["scheduling"] = scheduling
    return payload
