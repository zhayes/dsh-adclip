"""Doubao-Seed-2.1 text/vision adapter on Volcengine Ark.

Used by two callers only:

* ``media/vision.py`` — reference keyframe labels, after MiniMax-M3 and before
  the DSH vision bridge.
* ``llm.py`` — structured gag/script generation when the caller explicitly
  selects one of these models.

The account may not have the models activated. ``ModelNotOpen`` is mapped to a
readable error and cached for a day so the vision chain can skip a known-closed
model instead of paying a failed round-trip on every run.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import threading
import time
from typing import Any

import httpx

from .. import store

BASE = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
STATE = store.DATA / "text_models_state.json"
_STATE_LOCK = threading.Lock()
STATE_TTL = 24 * 3600
CLOSED_TTL = 10 * 60
# Right after activation Ark keeps serving a few stale replicas that still answer
# ModelNotOpen (sometimes with an unformatted "%s" template), so a single 404 is
# not proof that the model is closed.
NOT_OPEN_RETRIES = (1.5, 4.0)
LAST_ERROR = ""

ROWS: list[dict[str, Any]] = [
    {
        "id": "ark.doubao-seed-2.1-pro",
        "short": "pro",
        "env": "ARK_MODEL_DOUBAO_PRO",
        "model": "doubao-seed-2-1-pro-260915",
        "label": "Doubao-Seed-2.1-pro（火山方舟）",
        "description": "旗舰：逐帧拆解与复杂脚本，1M 上下文",
    },
    {
        "id": "ark.doubao-seed-2.1-turbo",
        "short": "turbo",
        "env": "ARK_MODEL_DOUBAO_TURBO",
        "model": "doubao-seed-2-1-turbo-260628",
        "label": "Doubao-Seed-2.1-turbo（火山方舟）",
        "description": "速度档：多帧拆解更快",
    },
    {
        "id": "ark.doubao-seed-2.1-lite",
        "short": "lite",
        "env": "ARK_MODEL_DOUBAO_LITE",
        "model": "doubao-seed-2-1-lite-260915",
        "label": "Doubao-Seed-2.1-lite（火山方舟）",
        "description": "低价批量：景别/动作/画面文字够用",
    },
]

CAPABILITIES = ["text", "vision", "thinking"]
TAGS = ["多模态模型", "深度思考", "视觉理解"]
DEFAULT_VISION_ORDER = "pro,turbo,lite"


class ArkTextError(RuntimeError):
    """Provider error with enough detail for the caller to record state."""

    def __init__(self, message: str, *, kind: str = "http", model: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.model = model


def _key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def available() -> bool:
    return bool(_key())


def model_id(row: dict[str, Any]) -> str:
    return (os.environ.get(str(row.get("env") or ""), "").strip() or str(row.get("model") or ""))


def row_for(model: str) -> dict[str, Any] | None:
    value = str(model or "").strip()
    for row in ROWS:
        if value in {str(row["id"]), str(row["short"]), str(row["model"]), model_id(row)}:
            return row
    return None


def _state() -> dict[str, dict[str, Any]]:
    data = store.read_json(STATE, {}) or {}
    return data if isinstance(data, dict) else {}


def record(model: str, status: str, error: str = "") -> None:
    row = row_for(model)
    if row is None:
        return
    with _STATE_LOCK:
        current = status_of(str(row["id"]))
        if status == "ok" and current.get("status") == "ok":
            return
        # Never downgrade a proven-open model because one replica flapped.
        if status == "not_open" and current.get("status") == "ok":
            return
        data = _state()
        data[str(row["id"])] = {
            "status": status,
            "error": str(error)[:300],
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "checked_ts": time.time(),
        }
        try:
            store.ensure_dirs()
            store.atomic_write_json(STATE, data)
        except OSError:
            pass


def status_of(model: str) -> dict[str, Any]:
    row = row_for(model)
    if row is None:
        return {}
    value = _state().get(str(row["id"]))
    if not isinstance(value, dict):
        return {}
    # A closed model is re-checked aggressively: the user may activate it at any
    # moment, and a 24h skip would hide the model for the rest of the day.
    ttl = CLOSED_TTL if str(value.get("status") or "") == "not_open" else STATE_TTL
    if float(value.get("checked_ts") or 0) + ttl < time.time():
        return {}
    return value


def models() -> list[dict[str, Any]]:
    """Model rows with capability tags and cached activation status."""
    key_present = available()
    out = []
    for row in ROWS:
        state = status_of(str(row["id"]))
        status = str(state.get("status") or ("unknown" if key_present else "no_key"))
        out.append({
            "id": row["id"],
            "kind": "text",
            "provider": "ark",
            "label": row["label"],
            "description": row["description"],
            "ark_model": model_id(row),
            "short": row["short"],
            "capabilities": list(CAPABILITIES),
            "tags": list(TAGS),
            "context": "1M",
            "requires": ["ARK_API_KEY"],
            "endpoint": BASE + "/chat/completions",
            "available": key_present and status != "not_open",
            "status": status,
            "reason": str(state.get("error") or "") if status in {"not_open", "error"} else ("" if key_present else "未配置 ARK_API_KEY"),
            "checked_at": str(state.get("checked_at") or ""),
        })
    return out


def vision_models() -> list[dict[str, Any]]:
    """Ark rows in the configured vision order, skipping cached closed models."""
    order = [item.strip() for item in (os.environ.get("ADSTUDIO_VISION_ARK_ORDER") or DEFAULT_VISION_ORDER).split(",") if item.strip()]
    by_short = {row["short"]: row for row in ROWS}
    out = []
    for item in order:
        row = by_short.get(item) or row_for(item)
        if row is None:
            continue
        state = status_of(str(row["id"]))
        if str(state.get("status") or "") == "not_open":
            continue
        out.append(row)
    return out


def _strip(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    return text.strip()


def _classify(status: int, body: str) -> tuple[str, str]:
    code = ""
    try:
        code = str(((json.loads(body or "{}").get("error") or {}).get("code")) or "")
    except (ValueError, AttributeError):
        code = ""
    if code in {"ModelNotOpen", "InvalidEndpointOrModel.NotFound"} or "not activated" in body or "not open" in body.lower():
        return "not_open", "模型未开通：请在火山方舟控制台「开通管理」开通该模型"
    if status in (401, 403):
        return "auth", f"ARK_API_KEY 无效或无权限（HTTP {status}）"
    if status == 429:
        return "rate", "火山方舟限流（429），稍后重试"
    if status == 404:
        return "not_open", "方舟模型不存在或未开通（404）"
    return "http", f"火山方舟 HTTP {status}: {body[:240]}"


def _chat_once(payload: dict[str, Any], *, timeout: float) -> httpx.Response:
    """One request, with retries while Ark's activation propagates."""
    response = _post(payload, timeout=timeout)
    for delay in NOT_OPEN_RETRIES:
        if response.status_code < 400:
            return response
        kind, _ = _classify(response.status_code, response.text)
        if kind != "not_open":
            return response
        time.sleep(delay)
        response = _post(payload, timeout=timeout)
    return response


def _post(payload: dict[str, Any], *, timeout: float = 90.0) -> httpx.Response:
    """Single HTTP hop; tests monkeypatch this."""
    key = _key()
    if not key:
        raise ArkTextError("未配置 ARK_API_KEY", kind="auth")
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=15.0)) as client:
        return client.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )


def chat(
    system: str,
    messages: list[dict[str, Any]],
    *,
    model: str = "ark.doubao-seed-2.1-pro",
    max_tokens: int = 1600,
    temperature: float = 0.3,
    thinking: bool | None = None,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """One Ark chat completion. Returns ``{text, provider, model, usage}``."""
    global LAST_ERROR
    LAST_ERROR = ""
    row = row_for(model)
    if row is None:
        raise ArkTextError(f"未知方舟模型：{model}", kind="config", model=model)
    payload: dict[str, Any] = {
        "model": model_id(row),
        "messages": ([{"role": "system", "content": system}] if system else []) + list(messages),
        "max_tokens": max(16, int(max_tokens)),
        "temperature": float(temperature),
    }
    if thinking is not None:
        payload["thinking"] = {"type": "enabled" if thinking else "disabled"}
    try:
        response = _chat_once(payload, timeout=timeout)
        if response.status_code == 400 and "thinking" in payload and "thinking" in response.text[:400]:
            payload.pop("thinking", None)
            response = _chat_once(payload, timeout=timeout)
    except httpx.HTTPError as exc:
        LAST_ERROR = f"方舟网络错误：{exc}"[:300]
        raise ArkTextError(LAST_ERROR, kind="network", model=model) from exc
    if response.status_code >= 400:
        kind, message = _classify(response.status_code, response.text)
        LAST_ERROR = message
        record(model, "not_open" if kind == "not_open" else ("error" if kind != "rate" else "rate"), message)
        raise ArkTextError(f"{message}（{row['label']}）", kind=kind, model=model)
    data = response.json()
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    text = _strip(str(message.get("content") or ""))
    if not text:
        LAST_ERROR = "方舟返回空内容"
        raise ArkTextError(LAST_ERROR, kind="empty", model=model)
    record(model, "ok")
    return {"text": text, "provider": "ark", "model": model_id(row), "row": row["id"], "usage": data.get("usage") or {}}


def _probe_one(row: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    try:
        chat("", [{"role": "user", "content": "回复 OK"}], model=str(row["id"]), max_tokens=16, temperature=0.0, thinking=False, timeout=timeout)
        return {"id": str(row["id"]), "ok": True, "status": "ok", "error": ""}
    except ArkTextError as exc:
        return {"id": str(row["id"]), "ok": False, "status": exc.kind, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"id": str(row["id"]), "ok": False, "status": "error", "error": f"{type(exc).__name__}: {exc}"[:240]}


def probe(model_ids: list[str] | None = None, *, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Cheap activation probe (1 token, thinking off) for every row in parallel.

    Each model retries on ``ModelNotOpen`` (see ``NOT_OPEN_RETRIES``), so a closed
    row costs a few seconds; probing in parallel keeps the whole check short.
    """
    if not available():
        return [{"id": str(row["id"]), "ok": False, "status": "no_key", "error": "未配置 ARK_API_KEY"} for row in ROWS]
    wanted = [str(item) for item in (model_ids or []) if str(item).strip()] or [str(row["id"]) for row in ROWS]
    rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for item in wanted:
        row = row_for(item)
        if row is None:
            results.append({"id": item, "ok": False, "status": "unknown", "error": "未知模型"})
        else:
            rows.append(row)
    if not rows:
        return results
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(rows))) as pool:
        results.extend(pool.map(lambda row: _probe_one(row, timeout=timeout), rows))
    order = {str(row["id"]): index for index, row in enumerate(rows)}
    results.sort(key=lambda item: order.get(str(item.get("id")), 99))
    return results
