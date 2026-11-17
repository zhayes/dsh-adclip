"""Local provider key storage for the first slice.

Keys are stored in `data/settings.json` with mode 0600 and mirrored into the
engine process environment. This is a local desktop convenience; the next
hardening step is to move the file to the OS keychain.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from . import store

FILE = store.DATA / "settings.json"
MODEL_PREFS = store.DATA / "model_prefs.json"
MODEL_PARAMS = store.DATA / "model_params.json"
ALLOWED = {
    "ARK_API_KEY",
    "KLING_API_KEY",
    "MINIMAX_API_KEY",
    "DEEPSEEK_API_KEY",
    "FAL_KEY",
}


def _load() -> dict[str, str]:
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items() if str(k) in ALLOWED and str(v).strip()}
    except (OSError, json.JSONDecodeError):
        return {}


def load_into_env() -> None:
    for name, value in _load().items():
        os.environ.setdefault(name, value)


def _write(data: dict[str, str]) -> None:
    store.ensure_dirs()
    tmp = FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, FILE)
    try:
        os.chmod(FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def set_key(name: str, value: str) -> dict[str, Any]:
    name = str(name or "").strip()
    if name not in ALLOWED:
        raise ValueError(f"unsupported key: {name}")
    value = str(value or "").strip()
    data = _load()
    if value:
        data[name] = value
        os.environ[name] = value
    else:
        data.pop(name, None)
        os.environ.pop(name, None)
    _write(data)
    return status()


def status() -> list[dict[str, Any]]:
    data = _load()
    rows = []
    for name in sorted(ALLOWED):
        value = data.get(name) or os.environ.get(name) or ""
        if value:
            masked = (value[:4] + "…" + value[-4:]) if len(value) > 10 else "已配置"
        else:
            masked = ""
        rows.append({"name": name, "present": bool(value), "masked": masked})
    return rows


def enabled_models() -> list[str] | None:
    """Return explicitly enabled model ids, or None before the first save."""
    try:
        data = json.loads(MODEL_PREFS.read_text(encoding="utf-8"))
        rows = data.get("enabled_models") if isinstance(data, dict) else None
        if isinstance(rows, list):
            return [str(x) for x in rows if str(x).strip()]
    except (OSError, json.JSONDecodeError):
        pass
    return None


def model_params() -> dict[str, dict[str, Any]]:
    """Saved per-model default parameters, keyed by model id."""
    try:
        data = json.loads(MODEL_PARAMS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out[str(key)] = value
    return out


def model_params_for(model_id: str) -> dict[str, Any]:
    return dict(model_params().get(str(model_id)) or {})


def set_model_params(model_id: str, values: dict[str, Any]) -> dict[str, Any]:
    store.ensure_dirs()
    data = model_params()
    current = dict(data.get(str(model_id)) or {})
    current.update(dict(values or {}))
    data[str(model_id)] = current
    tmp = MODEL_PARAMS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, MODEL_PARAMS)
    try:
        os.chmod(MODEL_PARAMS, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return model_params_for(model_id)


def set_enabled_models(ids: list[str]) -> list[str]:
    store.ensure_dirs()
    rows = []
    for value in ids:
        value = str(value or "").strip()
        if value and value not in rows:
            rows.append(value)
    tmp = MODEL_PREFS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"enabled_models": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, MODEL_PREFS)
    try:
        os.chmod(MODEL_PREFS, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return rows
