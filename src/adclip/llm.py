"""MiniMax text helper for structured gag/script generation.

This reuses the same MiniMax key as the video adapter; it is not a second
provider configuration. When the key is absent or the call fails, callers fall
back to deterministic demo content rather than blocking generation.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
MODEL = os.environ.get("ADSTUDIO_TEXT_MODEL", "MiniMax-M3")
DSH_URL = (os.environ.get("ADSTUDIO_DSH_CHAT_URL") or (os.environ.get("DSH_WEB_URL", "http://127.0.0.1:63215").rstrip("/") + "/adplus/api/dsh/chat")).strip()
TEXT_PROVIDER = os.environ.get("ADSTUDIO_TEXT_PROVIDER", "auto").strip().lower()
LAST_ERROR = ""
LAST_MODEL = ""


def available() -> bool:
    if TEXT_PROVIDER in {"dsh", "auto"} and DSH_URL:
        return True
    return bool(os.environ.get("MINIMAX_API_KEY", "").strip())


def model_label() -> str:
    return LAST_MODEL or MODEL


def provider_label() -> str:
    if TEXT_PROVIDER in {"dsh", "auto"} and DSH_URL:
        return "dsh"
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        return "minimax"
    return "none"


def _normalize_text_model(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    provider = str(value.get("provider") or "").strip()
    model = str(value.get("model") or "").strip()
    if not provider or not model:
        return None
    return {"provider": provider, "model": model}


def _strip_reasoning(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    return text.strip()


def _chat_dsh(system: str, user: str, *, max_tokens: int, temperature: float, text_model: dict[str, str] | None = None) -> str:
    global LAST_ERROR, LAST_MODEL
    payload = {
        "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        "maxTokens": max_tokens,
    }
    if text_model:
        payload["provider"] = text_model["provider"]
        payload["model"] = text_model["model"]
    with httpx.Client(timeout=httpx.Timeout(45.0, connect=8.0)) as client:
        response = client.post(DSH_URL, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"DSH bridge HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        dsh = data.get("dsh") or {}
        text = _strip_reasoning(str(dsh.get("text") or ""))
        if not text:
            raise RuntimeError("DSH bridge returned empty text")
        LAST_MODEL = str(dsh.get("model") or "dsh")
        return text


def _chat_minimax(system: str, user: str, *, max_tokens: int, temperature: float) -> str:
    global LAST_ERROR, LAST_MODEL
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY 未配置")
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    with httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        response = client.post(f"{BASE}/v1/text/chatcompletion_v2", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax text HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        base = data.get("base_resp") or {}
        if base.get("status_code") not in (0, None):
            raise RuntimeError(f"MiniMax text rejected: {base.get('status_msg')}")
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        text = _strip_reasoning(str(content))
        LAST_MODEL = MODEL
        return text


def chat(system: str, user: str, *, max_tokens: int = 1600, temperature: float = 0.3, text_model: dict[str, str] | None = None) -> str:
    global LAST_ERROR
    LAST_ERROR = ""
    errors = []
    if TEXT_PROVIDER != "minimax" and DSH_URL:
        try:
            return _chat_dsh(system, user, max_tokens=max_tokens, temperature=temperature, text_model=_normalize_text_model(text_model))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"DSH: {type(exc).__name__}: {exc}")
    if TEXT_PROVIDER != "dsh" and os.environ.get("MINIMAX_API_KEY", "").strip():
        try:
            return _chat_minimax(system, user, max_tokens=max_tokens, temperature=temperature)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"MiniMax: {type(exc).__name__}: {exc}")
    LAST_ERROR = " | ".join(errors)[:500] or "no text provider configured"
    raise RuntimeError(LAST_ERROR)


def chat_json(system: str, user: str, *, max_tokens: int = 1600, temperature: float = 0.25, text_model: dict[str, str] | None = None) -> dict[str, Any] | None:
    global LAST_ERROR
    LAST_ERROR = ""
    for attempt in range(2):
        try:
            text = chat(system, user, max_tokens=max_tokens + attempt * 800, temperature=temperature, text_model=text_model)
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                LAST_ERROR = f"attempt {attempt + 1}: no JSON in {len(text)} chars"
                continue
            value = json.loads(text[start:end + 1])
            if isinstance(value, dict):
                return value
            LAST_ERROR = f"attempt {attempt + 1}: JSON root is not an object"
        except Exception as exc:  # noqa: BLE001
            LAST_ERROR = f"attempt {attempt + 1}: {type(exc).__name__}: {exc}"[:300]
    return None
