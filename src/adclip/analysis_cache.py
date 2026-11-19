"""Reference analysis cache.

Vision labels and transcripts depend on the reference asset and on which
analyzers are available, never on the brief. Beats and cuts come from the same
bytes. Caching those facts means derived edits, retries and parameter changes do
not pay for the same frames twice.

The key carries the analyzer version plus the ASR/vision availability, so
installing speech recognition invalidates the old "no transcript" entry instead
of silently reusing it.
"""
from __future__ import annotations

from typing import Any

from . import store

CACHE_VERSION = "4"
CACHE_DIR = store.DATA / "analysis_cache"


def key(asset_id: str, *, asr_available: bool, vision_available: bool) -> str:
    record = store.get_asset(asset_id) or {}
    digest = str(record.get("sha256") or "")[:24] or str(record.get("id") or asset_id)
    return f"{digest}_{CACHE_VERSION}_{int(bool(asr_available))}{int(bool(vision_available))}"


def load(cache_key: str) -> dict[str, Any] | None:
    if not cache_key:
        return None
    data = store.read_json(CACHE_DIR / f"{cache_key}.json", None)
    return data if isinstance(data, dict) and data.get("beats") else None


def save(cache_key: str, payload: dict[str, Any]) -> None:
    if not cache_key or not payload.get("beats"):
        return
    store.atomic_write_json(CACHE_DIR / f"{cache_key}.json", payload)
