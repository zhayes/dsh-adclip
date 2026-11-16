"""Persona creation and Tencent-compatible defaults."""
from __future__ import annotations

from typing import Any

from . import store
from .models import Persona


def create(data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": data.get("id") or store.new_id("persona"),
        "name": str(data.get("name") or "未命名角色"),
        "type": data.get("type") or "ai",
        "gender": data.get("gender") or "any",
        "age": data.get("age") or "youth",
        "ethnicity": data.get("ethnicity") or "asian",
        "body_type": data.get("body_type") or "standard",
        "exact_age": data.get("exact_age"),
        "height_cm": data.get("height_cm"),
        "hair": str(data.get("hair") or ""),
        "outfit": str(data.get("outfit") or ""),
        "temperament": str(data.get("temperament") or ""),
        "voice_tone": str(data.get("voice_tone") or ""),
        "reference_audio_asset_id": data.get("reference_audio_asset_id"),
        "reference_images": list(data.get("reference_images") or []),
        "role": data.get("role") or "both",
        "locks": dict(data.get("locks") or {}),
        "consent": dict(data.get("consent") or {"confirmed": False, "note": ""}),
        "created_at": store.now(),
        "used_in_runs": list(data.get("used_in_runs") or []),
    }
    persona = Persona.model_validate(payload)
    if persona.type == "real" and not persona.consent.get("confirmed"):
        raise ValueError("真人角色必须确认授权")
    return store.save_persona(persona).model_dump()


def update(persona_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    current = store.get_persona(persona_id)
    if current is None:
        return None
    merged = {**current, **data, "id": persona_id, "created_at": current.get("created_at") or store.now()}
    persona = Persona.model_validate(merged)
    if persona.type == "real" and not persona.consent.get("confirmed"):
        raise ValueError("真人角色必须确认授权")
    return store.save_persona(persona).model_dump()


def delete(persona_id: str) -> bool:
    return store.delete_persona(persona_id)


def ensure_default() -> None:
    if not store.list_personas():
        store.save_persona(Persona.model_validate(store.default_persona()))


def resolve(persona_id: str) -> dict[str, Any]:
    return store.get_persona(persona_id) or store.default_persona()
