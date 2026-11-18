"""Text helpers for structured gag/script generation.

Order of preference: the DSH bridge (the Host's own LLM) first, then MiniMax,
then Doubao-Seed-2.1 on Volcengine Ark. An explicit ``text_model`` selection
(local UI / run.advanced.text_model) wins over the default order, and any
failure falls through to the next provider instead of blocking the run.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .providers import ark_text

BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
MODEL = os.environ.get("ADSTUDIO_TEXT_MODEL", "MiniMax-M3")
DSH_URL = (os.environ.get("ADSTUDIO_DSH_CHAT_URL") or (os.environ.get("DSH_WEB_URL", "http://127.0.0.1:63215").rstrip("/") + "/adplus/api/dsh/chat")).strip()
TEXT_PROVIDER = os.environ.get("ADSTUDIO_TEXT_PROVIDER", "auto").strip().lower()
LAST_ERROR = ""
LAST_MODEL = ""


def available() -> bool:
    if TEXT_PROVIDER in {"dsh", "auto"} and DSH_URL:
        return True
    if TEXT_PROVIDER in {"ark", "auto"} and ark_text.available():
        return True
    return bool(os.environ.get("MINIMAX_API_KEY", "").strip())


def model_label() -> str:
    return LAST_MODEL or MODEL


def provider_label() -> str:
    if TEXT_PROVIDER in {"dsh", "auto"} and DSH_URL:
        return "dsh"
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        return "minimax"
    if TEXT_PROVIDER in {"ark", "auto"} and ark_text.available():
        return "ark"
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


def _chat_ark(system: str, user: str, *, max_tokens: int, temperature: float, model: str) -> str:
    global LAST_ERROR, LAST_MODEL
    result = ark_text.chat(
        system,
        [{"role": "user", "content": user}],
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=90.0,
    )
    LAST_MODEL = str(result.get("model") or model)
    return str(result.get("text") or "")


def _missing_ark_key() -> str:
    raise RuntimeError("未配置 ARK_API_KEY")


def chat(system: str, user: str, *, max_tokens: int = 1600, temperature: float = 0.3, text_model: dict[str, str] | None = None) -> str:
    global LAST_ERROR, LAST_MODEL
    LAST_ERROR = ""
    selected = _normalize_text_model(text_model)
    ark_row = ark_text.row_for(selected["model"]) if selected and selected.get("provider") == "ark" else None
    steps: list[tuple[str, Any]] = []
    if TEXT_PROVIDER == "ark" or ark_row is not None:
        if ark_text.available():
            row = ark_row or ark_text.row_for("pro")
            steps.append(("Ark", lambda row=row: _chat_ark(system, user, max_tokens=max_tokens, temperature=temperature, model=str(row["id"]))))
        else:
            steps.append(("Ark", _missing_ark_key))
    if TEXT_PROVIDER in {"auto", "dsh"} or (selected and selected.get("provider") not in {None, "ark"}):
        if DSH_URL:
            steps.append(("DSH", lambda: _chat_dsh(system, user, max_tokens=max_tokens, temperature=temperature, text_model=selected)))
    if TEXT_PROVIDER in {"auto", "minimax"} and os.environ.get("MINIMAX_API_KEY", "").strip():
        steps.append(("MiniMax", lambda: _chat_minimax(system, user, max_tokens=max_tokens, temperature=temperature)))
    if TEXT_PROVIDER == "auto" and ark_row is None and ark_text.available():
        steps.append(("Ark", lambda: _chat_ark(system, user, max_tokens=max_tokens, temperature=temperature, model=str(ark_text.row_for("pro")["id"]))))
    errors: list[str] = []
    for label, step in steps:
        try:
            return step()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {type(exc).__name__}: {exc}"[:240])
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
