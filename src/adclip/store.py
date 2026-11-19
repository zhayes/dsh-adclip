"""Filesystem store for AdClip.

`data/runs/<id>/run.json` is the single source of truth. Assets and personas
have sidecar JSON records. No database is used in the first slice.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from .models import Asset, Persona, Run

# `<root>/src/adclip/store.py` -> `<root>`, in this checkout and in the
# published package (`<engine>/src/adclip` -> `<engine>`), so the default data
# directory and the legacy copy stay where they always were.
BASE = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("ADSTUDIO_DATA_DIR", BASE / "data")).resolve()
LEGACY_DATA = (BASE / "data").resolve()
ASSETS = DATA / "assets"
RUNS = DATA / "runs"
PERSONAS = DATA / "personas"
CONTEXT = DATA / "context.json"
LOCK = threading.RLock()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def migrate_legacy() -> dict[str, Any]:
    """One-time copy from the old engineRoot/data into the stable data dir.

    The legacy directory is never deleted; if the target already has content it
    is left alone. This makes plugin/engine upgrades non-destructive.

    Test mode never migrates: the legacy dir can hold the developer's real
    provider keys, and a test run must never pick them up and call a paid API.
    """
    if os.environ.get("ADCLIP_TEST_MODE", "").strip() == "1":
        return {"migrated": False, "reason": "test mode"}
    if DATA == LEGACY_DATA or not LEGACY_DATA.is_dir():
        return {"migrated": False, "reason": "not needed"}
    try:
        has_target = DATA.is_dir() and any(DATA.iterdir())
    except OSError:
        has_target = False
    if has_target:
        return {"migrated": False, "reason": "target already has data"}
    DATA.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LEGACY_DATA, DATA, dirs_exist_ok=True)
    atomic_write_json(DATA / ".migrated_from.json", {"source": str(LEGACY_DATA), "at": now()})
    return {"migrated": True, "source": str(LEGACY_DATA), "target": str(DATA)}


def ensure_dirs() -> None:
    for path in (DATA, ASSETS, RUNS, PERSONAS):
        path.mkdir(parents=True, exist_ok=True)


def new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{secrets.token_hex(3)}"


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def rel_to_data(path: Path) -> str:
    try:
        return path.resolve().relative_to(DATA).as_posix()
    except (ValueError, OSError):
        return str(path)


def path_from_rel(rel: str) -> Path:
    target = (DATA / rel).resolve()
    if DATA not in target.parents and target != DATA:
        raise ValueError("path outside AdClip data")
    return target


def safe_media_path(rel: str) -> Path:
    target = path_from_rel(rel)
    if not target.is_file():
        raise FileNotFoundError(rel)
    if not any(target == root or root in target.parents for root in (ASSETS, RUNS)):
        raise ValueError("path outside media roots")
    return target


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------
def create_asset(raw: bytes, name: str, kind: str, mime: str = "application/octet-stream") -> Asset:
    ensure_dirs()
    if not raw:
        raise ValueError("empty file")
    digest = hashlib.sha256(raw).hexdigest()
    suffix = Path(name or "").suffix.lower()
    if not suffix:
        suffix = {"video": ".mp4", "image": ".png", "audio": ".mp3"}.get(kind, ".bin")
    target = ASSETS / f"{digest[:24]}{suffix}"
    if not target.is_file():
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, target)
    record = Asset(
        id=f"a_{digest[:16]}",
        name=name or target.name,
        original_name=name or target.name,
        kind=kind if kind in {"video", "image", "audio", "file"} else "file",
        path=rel_to_data(target),
        sha256=digest,
        bytes=len(raw),
        mime=mime,
        created_at=now(),
    )
    atomic_write_json(ASSETS / f"{record.id}.json", record.model_dump())
    return record


def update_asset(asset: Asset) -> Asset:
    atomic_write_json(ASSETS / f"{asset.id}.json", asset.model_dump())
    return asset


def list_assets(kind: str = "", query: str = "", limit: int = 300) -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in ASSETS.glob("*.json"):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        if kind and data.get("kind") != kind:
            continue
        if query:
            haystack = f"{data.get('name', '')} {data.get('original_name', '')}".lower()
            if query.lower() not in haystack:
                continue
        rows.append(data)
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return rows[: max(1, min(limit, 1000))]


def list_assets_page(kind: str = "", query: str = "", offset: int = 0, limit: int = 24, date_from: str = "", date_to: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in ASSETS.glob("*.json"):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        if kind and data.get("kind") != kind:
            continue
        if query:
            haystack = f"{data.get('name', '')} {data.get('original_name', '')}".lower()
            if query.lower() not in haystack:
                continue
        created = str(data.get("created_at") or "")
        if date_from and created[:10] < date_from:
            continue
        if date_to and created[:10] > date_to:
            continue
        sha = str(data.get("sha256") or "")
        if sha and sha in seen:
            continue
        if sha:
            seen.add(sha)
        rows.append(data)
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    total = len(rows)
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 200))
    return rows[offset:offset + limit], total


def get_asset(asset_id: str) -> dict[str, Any] | None:
    return read_json(ASSETS / f"{asset_id}.json")


def get_asset_by_sha(sha: str) -> dict[str, Any] | None:
    ensure_dirs()
    for path in ASSETS.glob("*.json"):
        row = read_json(path)
        if isinstance(row, dict) and row.get("sha256") == sha:
            return row
    return None


# ---------------------------------------------------------------------------
# personas
# ---------------------------------------------------------------------------
def save_persona(persona: Persona) -> Persona:
    ensure_dirs()
    atomic_write_json(PERSONAS / f"{persona.id}.json", persona.model_dump())
    return persona


def get_persona(persona_id: str) -> dict[str, Any] | None:
    return read_json(PERSONAS / f"{persona_id}.json")


def list_personas() -> list[dict[str, Any]]:
    ensure_dirs()
    rows = []
    for path in PERSONAS.glob("*.json"):
        data = read_json(path)
        if isinstance(data, dict):
            rows.append(data)
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return rows


def delete_persona(persona_id: str) -> bool:
    path = PERSONAS / f"{persona_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def run_dir(run_id: str) -> Path:
    return RUNS / run_id


def run_path(run_id: str) -> Path:
    return run_dir(run_id) / "run.json"


def write_run(run: Run) -> Run:
    atomic_write_json(run_path(run.id), run.model_dump())
    return run


def repair_segment_edit_failures() -> list[str]:
    """Restore runs that an old failed segment edit wrongly marked failed.

    Only the exact historical signature is repaired: the edit failed with
    ``segment not found`` after the run had already produced a deliverable
    final clip and a shippable QA report. Other failures are left alone.
    """
    repaired: list[str] = []
    for path in RUNS.glob("*/run.json"):
        run = read_run(path.parent.name)
        if run is None or run.status != "failed" or run.step != "segment":
            continue
        if "segment not found" not in str(run.error or ""):
            continue
        result = run.result or {}
        video = str(result.get("video") or "")
        if not video:
            continue
        try:
            target = safe_media_path(video)
        except (ValueError, FileNotFoundError):
            continue
        if not target.is_file():
            continue
        qa = result.get("qa") or {}
        if not (qa.get("summary") or {}).get("shippable"):
            continue
        run.last_edit_error = str(run.error or "")
        run.status = "succeeded"
        run.step = "qa"
        run.progress = 1.0
        run.error = None
        write_run(run)
        repaired.append(run.id)
    return repaired


def read_run(run_id: str) -> Run | None:
    data = read_json(run_path(run_id))
    if not isinstance(data, dict):
        return None
    try:
        return Run.model_validate(data)
    except Exception:
        return None


def run_media_rel(run_id: str, filename: str) -> str:
    return f"runs/{run_id}/artifacts/{filename}"


def run_artifact(run_id: str, filename: str) -> Path:
    path = run_dir(run_id) / "artifacts" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def list_runs(limit: int = 30) -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in RUNS.glob("*/run.json"):
        data = read_json(path)
        if isinstance(data, dict):
            rows.append(data)
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return rows[: max(1, min(limit, 200))]


def list_runs_page(
    *, offset: int = 0, limit: int = 20, query: str = "",
    date_from: str = "", date_to: str = "", status: str = "",
    scenario: str = "", sort: str = "created_desc",
) -> tuple[list[dict[str, Any]], int]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    needle = query.lower().strip()
    for path in RUNS.glob("*/run.json"):
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        if needle and needle not in str(data.get("title") or "").lower() and needle not in str(data.get("id") or "").lower():
            continue
        created = str(data.get("created_at") or "")
        if date_from and created[:10] < date_from:
            continue
        if date_to and created[:10] > date_to:
            continue
        if status and data.get("status") != status:
            continue
        if scenario and data.get("scenario") != scenario:
            continue
        rows.append(data)
    if sort == "created_asc":
        rows.sort(key=lambda item: item.get("created_at") or "")
    elif sort == "finished_desc":
        rows.sort(key=lambda item: item.get("finished_at") or item.get("created_at") or "", reverse=True)
    else:
        rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    total = len(rows)
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 200))
    return rows[offset:offset + limit], total


def update_run(run: Run, **fields: Any) -> Run:
    data = run.model_dump()
    data.update(fields)
    updated = Run.model_validate(data)
    return write_run(updated)


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------
def read_context() -> dict[str, Any]:
    data = read_json(CONTEXT, {})
    return data if isinstance(data, dict) else {}


def write_context(values: dict[str, Any]) -> dict[str, Any]:
    current = read_context()
    current.update(values or {})
    atomic_write_json(CONTEXT, current)
    return current


# ---------------------------------------------------------------------------
# media helpers
# ---------------------------------------------------------------------------
def asset_media_path(asset_id: str) -> Path:
    record = get_asset(asset_id)
    if record is None:
        raise FileNotFoundError(asset_id)
    return safe_media_path(str(record["path"]))


def asset_media_url(asset_id: str) -> str:
    record = get_asset(asset_id)
    if record is None:
        return ""
    return f"/media?path={record['path']}"


def default_persona() -> dict[str, Any]:
    return {
        "id": "persona_auto",
        "name": "自动模特",
        "type": "ai",
        "gender": "any",
        "age": "youth",
        "ethnicity": "asian",
        "body_type": "standard",
        "exact_age": None,
        "height_cm": None,
        "hair": "",
        "outfit": "",
        "temperament": "",
        "voice_tone": "",
        "reference_audio_asset_id": None,
        "reference_images": [],
        "role": "both",
        "locks": {},
        "consent": {"confirmed": True, "note": "自动生成角色，不涉及真人"},
        "created_at": now(),
        "used_in_runs": [],
    }
