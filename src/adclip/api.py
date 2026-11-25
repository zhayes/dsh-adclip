"""FastAPI surface for AdClip.

No pricing, quotes or billing endpoints exist. The first slice runs a local
demo pipeline so the DSH UI, storyboard, edits, personas and stitching can be
exercised end to end without paid credentials.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import asynccontextmanager
import mimetypes
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from . import capabilities
from . import catalog as model_catalog
from . import image_params, intents, llm, params, personas, remake_planner, settings, store
from .providers import ark_text, discovery
from .media import asr
from .media import ffmpeg
from .media import stitch as stitch_mod
from .media import subtitles
from .models import AssistantRequest, Run, RunStep, StitchRequest
from .pipeline import image_runner
from .pipeline import remake_spec
from .pipeline import replace as segment_replace
from .pipeline import qa as qa_pipeline
from .pipeline import runner, segment
from .pipeline import generate as generate_pipeline

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    store.migrate_legacy()
    store.ensure_dirs()
    settings.load_into_env()
    personas.ensure_default()
    try:
        repaired = store.repair_segment_edit_failures()
        if repaired:
            print(f"adclip: repaired {len(repaired)} segment-edit failures: {', '.join(repaired)}")
    except Exception as exc:  # noqa: BLE001
        print(f"adclip: segment-edit repair skipped: {type(exc).__name__}: {exc}")
    yield


app = FastAPI(title="AdClip", version="0.1.0", lifespan=_lifespan)
VERSION = "0.1.34"


def _media_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _probe_asset(asset_id: str) -> dict[str, Any]:
    record = store.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="asset not found")
    target = store.safe_media_path(record["path"])
    try:
        if record.get("kind") == "video":
            facts = ffmpeg.probe(target)
            record.update({k: facts[k] for k in ("width", "height", "duration_s", "size_bytes")})
        elif record.get("kind") == "image":
            from PIL import Image

            with Image.open(target) as image:
                record["width"], record["height"] = image.size
    except Exception:
        pass
    return record


@app.get("/health")
def health() -> dict[str, Any]:
    models = params.catalog()
    return {
        "ok": True,
        "service": "adclip",
        "version": VERSION,
        "demo": False,
        "data": str(store.DATA),
        "models": len(models),
        "available_models": [row["id"] for row in models if row.get("available")],
        "text_llm": llm.available(),
        "text_model": llm.model_label(),
        "text_provider": llm.provider_label(),
        "text_llm_last_error": llm.LAST_ERROR,
        "runs": len(store.list_runs(limit=200)),
        "deps": ffmpeg.dependencies(),
    }


@app.get("/scenarios")
def scenarios() -> dict[str, Any]:
    return {"scenarios": params.SCENARIOS}


@app.get("/models")
def models(kind: str = "", capability: str = "") -> dict[str, Any]:
    rows = model_catalog.rows()
    if kind:
        rows = [row for row in rows if row["kind"] == kind]
    if capability:
        rows = [row for row in rows if capability in (row.get("capabilities") or [])]
    return {"models": rows, "kinds": sorted({row["kind"] for row in rows}),
            "capabilities": {kind_name: sorted({cap for row in rows if row["kind"] == kind_name for cap in row["capabilities"]})
                             for kind_name in sorted({row["kind"] for row in rows})}}


@app.post("/assets/upload")
async def upload_asset(request: Request, kind: str = "video", name: str = "") -> dict[str, Any]:
    if kind not in {"image", "video"}:
        raise HTTPException(status_code=400, detail="only image and video assets are supported")
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > 2 * 1024**3:
        raise HTTPException(status_code=413, detail="file too large")
    import hashlib

    mime = request.headers.get("content-type") or "application/octet-stream"
    digest = hashlib.sha256(raw).hexdigest()
    existing = store.get_asset_by_sha(digest)
    if existing is not None:
        return {"ok": True, "asset": existing, "deduplicated": True}
    try:
        asset = store.create_asset(raw, name or f"upload-{store.new_id('file')}", kind, mime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = _probe_asset(asset.id)
    return {"ok": True, "asset": record}


@app.get("/assets")
def list_assets(
    kind: str = "", q: str = "", offset: int = 0, limit: int = 24,
    from_: str = Query("", alias="from"), to: str = "",
) -> dict[str, Any]:
    rows, total = store.list_assets_page(kind=kind, query=q, offset=offset, limit=limit, date_from=from_, date_to=to)
    return {"assets": rows, "total": total, "offset": max(0, offset), "limit": max(1, min(limit, 200)), "has_more": offset + len(rows) < total}


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    record = store.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return {"asset": record}


@app.get("/media")
def media(path: str) -> FileResponse:
    try:
        target = store.safe_media_path(path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(target, media_type=_media_type(target))


# ---------------------------------------------------------------------------
# local provider keys
# ---------------------------------------------------------------------------
@app.get("/settings/models")
def get_settings_models() -> dict[str, Any]:
    return {"enabled": settings.enabled_models(), "models": model_catalog.rows()}


@app.post("/settings/models")
def set_settings_models(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    valid = {str(row["id"]) for row in model_catalog.rows()}
    enabled = []
    for value in payload.get("enabled") or []:
        value = str(value or "").strip()
        if value in valid and value not in enabled:
            enabled.append(value)
    settings.set_enabled_models(enabled)
    return {"enabled": enabled, "models": model_catalog.rows()}


@app.post("/settings/text_models")
def set_settings_text_models(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Enable or disable the Doubao text/vision rows.

    Activation ("已开通") is the provider's switch; this one is ours. A row that
    is activated but switched off here is never handed to the vision ladder or
    the text bridge, and the engine falls back to DSH instead.
    """
    valid = {str(row["id"]) for row in model_catalog.text_rows()}
    enabled: list[str] = []
    for value in payload.get("enabled") or []:
        value = str(value or "").strip()
        if value in valid and value not in enabled:
            enabled.append(value)
    settings.set_enabled_text_models(enabled)
    return {"enabled": enabled, "models": model_catalog.text_rows()}


@app.get("/models/discover")
def discover_models() -> dict[str, Any]:
    return {"providers": discovery.discover()}


@app.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    return capabilities.manifest(
        model_catalog.rows(),
        text_models=model_catalog.text_rows(),
        vision_chain=model_catalog.vision_chain(),
        remake_chain=model_catalog.remake_chain(),
    )


@app.get("/text/models")
def get_text_models() -> dict[str, Any]:
    """Doubao-Seed-2.1 text/vision rows for the picker and Settings."""
    rows = model_catalog.text_rows()
    return {
        "available": ark_text.available(),
        "key_present": ark_text.available(),
        "endpoint": ark_text.BASE + "/chat/completions",
        "models": rows,
    }


@app.post("/text/models/probe")
def probe_text_models(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Cheap activation check (1 token, thinking off) for the Ark rows."""
    ids = payload.get("ids") if isinstance(payload.get("ids"), list) else None
    results = ark_text.probe([str(item) for item in ids] if ids else None)
    return {"results": results, "models": model_catalog.text_rows()}


@app.post("/text/chat")
def text_chat(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    """Free-create chat through Ark. Only the ``ark`` provider is served here."""
    provider = str(payload.get("provider") or "").strip()
    model = str(payload.get("model") or "").strip()
    if provider != "ark" or not model:
        raise HTTPException(status_code=400, detail="provider=ark and model are required; use /dsh/chat for DSH models")
    system = str(payload.get("system") or "")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages are required")
    try:
        result = ark_text.chat(
            system,
            [{"role": str(item.get("role") or "user"), "content": item.get("content")}
             for item in messages if isinstance(item, dict)],
            model=model,
            max_tokens=int(payload.get("maxTokens") or 1200),
            temperature=float(payload.get("temperature") or 0.4),
            thinking=payload.get("thinking") if isinstance(payload.get("thinking"), bool) else False,
            timeout=float(payload.get("timeout") or 90.0),
        )
    except ark_text.ArkTextError as exc:
        return JSONResponse(status_code=502, content={"error": {"code": "ark_text_failed", "kind": exc.kind, "message": str(exc)}})
    return JSONResponse(content={"text": result["text"], "provider": "ark", "model": result["model"], "usage": result.get("usage") or {}})


@app.get("/settings/model_params")
def get_model_params() -> dict[str, Any]:
    rows = []
    for row in model_catalog.rows():
        rows.append({
            "id": row["id"],
            "label": row.get("label"),
            "params": row.get("params") or {},
            "defaults": row.get("default_params") or {},
        })
    return {"models": rows, "saved": settings.model_params()}


@app.post("/settings/model_params")
def set_model_params(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    model_id = str(payload.get("model_id") or "").strip()
    if not model_id or model_catalog.get(model_id) is None:
        raise HTTPException(status_code=400, detail="unknown model")
    try:
        values = capabilities.validate_params(model_id, dict(payload.get("values") or {}))
        saved = settings.set_model_params(model_id, values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "model_id": model_id, "saved": saved, "models": model_catalog.rows()}


@app.get("/settings/keys")
def get_settings_keys() -> dict[str, Any]:
    return {"keys": settings.status()}


@app.post("/settings/keys")
def set_settings_key(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        rows = settings.set_key(str(payload.get("name") or ""), str(payload.get("value") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"keys": rows, "models": params.catalog()}


# ---------------------------------------------------------------------------
# personas
# ---------------------------------------------------------------------------
@app.get("/personas")
def list_personas() -> dict[str, Any]:
    return {"personas": store.list_personas()}


@app.post("/personas")
def create_persona(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"persona": personas.create(payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/personas/{persona_id}")
def patch_persona(persona_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    result = personas.update(persona_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="persona not found")
    return {"persona": result}


@app.delete("/personas/{persona_id}")
def remove_persona(persona_id: str) -> dict[str, Any]:
    return {"removed": personas.delete(persona_id)}


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def _scenario_or_404(scenario_id: str) -> dict[str, Any]:
    scenario = params.scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=400, detail=f"unknown scenario: {scenario_id}")
    if scenario.get("status") != "ready":
        raise HTTPException(status_code=409, detail="scenario is not ready")
    return scenario


def _validate_inputs(scenario: dict[str, Any], inputs: dict[str, Any]) -> None:
    if scenario["id"] == "viral-remake":
        ref = inputs.get("reference_asset_id")
        if not ref or store.get_asset(ref) is None:
            raise HTTPException(status_code=400, detail="reference video is required")
    if scenario["id"] == "text-to-video" and not str(inputs.get("brief") or "").strip():
        raise HTTPException(status_code=400, detail="brief is required")


def _new_run(scenario_id: str, inputs: dict[str, Any], advanced: dict[str, Any], *, title: str = "", parent: Run | None = None, changes: list[dict[str, Any]] | None = None) -> Run:
    if scenario_id == "viral-remake":
        advanced = params.enforce_remake_audio(advanced)
    # A confirmation belongs to one run: a derived or retried run renders its own
    # prompt and must be confirmed again (unless the operator opted out).
    advanced = {key: value for key, value in (advanced or {}).items() if key != "prompt_confirmed"}
    run_id = store.new_id("run")
    store.run_dir(run_id).mkdir(parents=True, exist_ok=True)
    (store.run_dir(run_id) / "artifacts").mkdir(parents=True, exist_ok=True)
    persona_map = dict((advanced or {}).get("persona_map") or {})
    persona_snapshot = {}
    persona_obj = (advanced or {}).get("persona")
    if isinstance(persona_obj, dict):
        persona_snapshot = persona_obj
    if not title:
        brief = str(inputs.get("brief") or "").strip()
        head = (brief.split("。")[0].split("，")[0] or "").strip()[:26]
        label = params.scenario(scenario_id)["label"]
        title = f"{label} · {head}" if head else label
    run = Run(
        id=run_id,
        scenario=scenario_id,
        title=title[:60],
        status="queued",
        step="queued",
        generation_mode="fast",
        inputs=inputs,
        advanced=advanced,
        persona_map=persona_map,
        persona_snapshot=persona_snapshot,
        selection=remake_planner.selection_for(scenario_id, inputs, advanced),
        steps=[RunStep(name=name, label=label) for name, label, _ in runner.STEPS],
        created_at=store.now(),
        parent_run_id=parent.id if parent else None,
        version=(parent.version + 1) if parent else 1,
        changes=changes or [],
        demo=False,
    )
    store.write_run(run)
    runner.manager.start(run.id)
    return run


@app.post("/runs")
def create_run(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    scenario_id = str(payload.get("scenario") or "viral-remake")
    scenario = _scenario_or_404(scenario_id)
    inputs = dict(payload.get("inputs") or {})
    raw_advanced = dict(payload.get("advanced") or {})
    if scenario_id == "text-to-video":
        advanced = {**params.DEFAULT_ADVANCED, **params.scenario_defaults(scenario_id), **raw_advanced}
    else:
        advanced = params.merged_advanced(raw_advanced)
    if scenario_id == "viral-remake":
        advanced["model"] = "auto"
        advanced["remake_mode"] = "auto"
        advanced = params.enforce_remake_audio(advanced)
    _validate_inputs(scenario, inputs)
    run = _new_run(scenario_id, inputs, advanced, title=str(payload.get("title") or ""))
    return JSONResponse(status_code=202, content={"run": run.model_dump()})


@app.get("/image/models")
def get_image_models() -> dict[str, Any]:
    rows = image_params.catalog()
    return {"models": rows, "available": any(row.get("available") for row in rows)}


@app.post("/images")
def create_image(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        run = image_runner.create(
            prompt,
            model_id=str(payload.get("model") or ""),
            aspect=str(payload.get("aspect") or "1:1"),
            area=str(payload.get("area") or "2K"),
            reference_asset_id=str(payload.get("reference_asset_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(status_code=202, content={"run": run.model_dump()})


@app.post("/images/{run_id}/retry")
def retry_image(run_id: str) -> JSONResponse:
    parent = store.read_run(run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="run not found")
    if parent.scenario != "text-to-image":
        raise HTTPException(status_code=409, detail="not an image run")
    advanced = parent.advanced or {}
    try:
        run = image_runner.create(
            str((parent.inputs or {}).get("prompt") or ""),
            model_id=str(advanced.get("model") or ""),
            aspect=str(advanced.get("aspect") or "1:1"),
            area=str(advanced.get("area") or "2K"),
            parent=parent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(status_code=202, content={"run": run.model_dump()})


@app.get("/runs")
def list_runs(
    offset: int = 0, limit: int = 20, q: str = "",
    from_: str = Query("", alias="from"), to: str = "", status: str = "",
    scenario: str = "", sort: str = "created_desc",
) -> dict[str, Any]:
    rows, total = store.list_runs_page(
        offset=offset, limit=limit, query=q, date_from=from_, date_to=to,
        status=status, scenario=scenario, sort=sort,
    )
    return {"runs": rows, "total": total, "offset": max(0, offset), "limit": max(1, min(limit, 200)), "has_more": offset + len(rows) < total}


@app.post("/runs/export")
def export_runs(payload: dict[str, Any] = Body(...)) -> FileResponse:
    ids = [str(x) for x in (payload.get("run_ids") or []) if str(x).strip()]
    ids = list(dict.fromkeys(ids))[:50]
    if not ids:
        raise HTTPException(status_code=400, detail="run_ids is required")
    export_dir = store.DATA / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / f"adplus-export-{int(time.time())}.zip"
    included = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for run_id in ids:
            run = store.read_run(run_id)
            if run is None or run.status != "succeeded":
                continue
            root = store.run_dir(run_id)
            folder = run_id
            zf.write(root / "run.json", arcname=f"{folder}/run.json")
            for name in ("final.mp4", "image.jpg", "subtitles.srt", "qa.json", "script.json", "skeleton.json", "storyboard.json"):
                path = root / "artifacts" / name
                if path.is_file():
                    zf.write(path, arcname=f"{folder}/artifacts/{name}")
            included.append(run_id)
    if not included:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="no succeeded runs to export")
    return FileResponse(target, media_type="application/zip", filename=target.name)


@app.patch("/runs/{run_id}")
def rename_run(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    run.title = title[:120]
    store.write_run(run)
    return {"run": run.model_dump()}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    data = run.model_dump()
    storyboard = store.read_json(store.run_dir(run_id) / "artifacts" / "storyboard.json")
    if storyboard:
        data["storyboard"] = storyboard.get("segments") or []
    return {"run": data}


@app.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    run.cancel_requested = True
    if run.status in {"queued", "running", "awaiting_confirm"}:
        run.status = "canceled"
        run.error = "已取消"
        run.finished_at = store.now()
    store.write_run(run)
    return {"ok": True, "run": run.model_dump()}


@app.post("/runs/{run_id}/confirm")
def confirm_run(run_id: str) -> dict[str, Any]:
    """Approve the rendered prompt and let the generation step spend tokens."""
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status != "awaiting_confirm":
        raise HTTPException(status_code=409, detail="run is not waiting for confirmation")
    try:
        runner.confirm(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run": (store.read_run(run_id) or run).model_dump()}


@app.post("/runs/{run_id}/retry")
def retry_run(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    new_run = _new_run(run.scenario, copy.deepcopy(run.inputs), copy.deepcopy(run.advanced), title=run.title, parent=run, changes=[])
    return {"run": new_run.model_dump()}


@app.get("/runs/{run_id}/analysis")
def analysis(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    if not skeleton:
        return {"available": False, "analysis": None, "remake_plan": None, "beats": [], "transcript": [], "confidence": {}, "notes": []}
    return {
        "available": True,
        "analysis": skeleton.get("analysis") or {"mode": "legacy", "degraded": False, "reason": ""},
        "remake_plan": skeleton.get("remake_plan") or {},
        "beats": skeleton.get("beats") or [],
        "transcript": skeleton.get("transcript") or [],
        "confidence": skeleton.get("confidence") or {},
        "notes": skeleton.get("notes") or [],
    }


@app.get("/asr/status")
def asr_status() -> dict[str, Any]:
    """Whether speech recognition can run, and why not when it cannot."""
    return asr.status()


@app.post("/transcribe")
def transcribe(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Transcribe one asset (or a run's reference video). Never 500s on ASR errors."""
    asset_id = str(payload.get("asset_id") or "")
    run_id = str(payload.get("run_id") or "")
    if not asset_id and run_id:
        run = store.read_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        asset_id = str((run.inputs or {}).get("reference_asset_id") or "")
    if not asset_id:
        raise HTTPException(status_code=400, detail="asset_id or run_id is required")
    try:
        path = store.asset_media_path(asset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="asset not found") from exc
    word_level = bool(payload.get("word_level"))
    try:
        limit = max(5.0, min(300.0, float(payload.get("max_seconds") or 60)))
    except (TypeError, ValueError):
        limit = 60.0
    lines = asr.transcribe_words(path, max_seconds=limit) if word_level else asr.transcribe(path, max_seconds=limit)
    return {
        "available": asr.available(),
        "status": asr.status(),
        "asset_id": asset_id,
        "word_level": word_level,
        "model": str(getattr(asr, "LAST_MODEL", "") or ""),
        "lines": lines,
        "text": "".join(str(row.get("text") or "") for row in lines) if word_level else "\n".join(str(row.get("text") or "") for row in lines),
        "error": str(getattr(asr, "LAST_ERROR", "") or ""),
    }


@app.get("/runs/{run_id}/storyboard")
def storyboard(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    data = store.read_json(store.run_dir(run_id) / "artifacts" / "storyboard.json")
    if not data:
        data = segment.build_storyboard(run_id)
    return data


@app.get("/runs/{run_id}/prompt")
def prompt_preview(run_id: str) -> dict[str, Any]:
    """The exact prompt a generation step would send, without spending a call."""
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    if not skeleton:
        raise HTTPException(status_code=409, detail="run has no analysis yet")
    script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    selection = getattr(run, "selection", None) or {}
    mode = str(selection.get("mode") or "generation")
    spec = remake_spec.build_spec(run, skeleton, script)
    # The generator's own path, so this panel cannot drift from what is sent.
    auto = generate_pipeline.preview_prompt(run, script, skeleton, selection)
    override = str((run.inputs or {}).get("prompt_override") or "")
    text = override or auto
    return {
        "mode": mode,
        "model": str(selection.get("model") or ""),
        "chars": len(text),
        "auto_chars": len(auto),
        "text": text,
        "override": override,
        "shots": len(spec.get("shots") or []),
        "lines": sum(len(shot.get("timed_lines") or []) for shot in spec.get("shots") or []),
        "requirements": spec.get("requirements") or {},
    }


@app.post("/runs/{run_id}/prompt-override")
def prompt_override(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Store an edited prompt on the run; the next generation uses it verbatim."""
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    inputs = dict(run.inputs or {})
    text = str(payload.get("text") or "").strip()
    if text:
        inputs["prompt_override"] = text[:4000]
    else:
        inputs.pop("prompt_override", None)
    run.inputs = inputs
    store.write_run(run)
    return {"ok": True, "chars": len(str(inputs.get("prompt_override") or ""))}


def _apply_changes(advanced: dict[str, Any], inputs: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    for change in changes:
        field = str(change.get("field") or "")
        value = change.get("to")
        if field.startswith("advanced."):
            advanced[field.split(".", 1)[1]] = value
        elif field.startswith("post."):
            advanced[field.split(".", 1)[1]] = value
        elif field.startswith("persona."):
            persona = dict(advanced.get("persona") or {})
            persona[field.split(".", 1)[1]] = value
            advanced["persona"] = persona
        elif field == "inputs.brief":
            inputs["brief"] = value


def _post_derive(parent: Run, changes: list[dict[str, Any]]) -> Run:
    """Apply post-only changes without calling any video model."""
    run_id = store.new_id("run")
    root = store.run_dir(run_id) / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    src = store.run_dir(parent.id) / "artifacts"
    for name in ("script.json", "skeleton.json", "storyboard.json", "qa.json"):
        source = src / name
        if source.is_file():
            shutil.copy2(source, root / name)
    advanced = copy.deepcopy(parent.advanced)
    inputs = copy.deepcopy(parent.inputs)
    _apply_changes(advanced, inputs, changes)
    # The SRT follows the post-processed run's own setting, regenerated from the
    # script that came over with the parent.
    script = store.read_json(store.run_dir(parent.id) / "artifacts" / "script.json", {}) or {}
    srt_target = root / "subtitles.srt"
    if str(advanced.get("subtitle") or "off") == "sidecar":
        subtitles.write_srt(script, srt_target)
    else:
        srt_target.unlink(missing_ok=True)
    bitrate = str(advanced.get("export_bitrate") or "8M")
    fps = int(advanced.get("fps") or 30)
    source_video = src / "final.mp4"
    if not source_video.is_file():
        raise HTTPException(status_code=409, detail="run has no final video to post-process")
    target = root / "final.mp4"
    ffmpeg.transcode(
        source_video,
        target,
        bitrate=bitrate,
        fps=fps,
        trim_start=advanced.get("trim_start"),
        trim_end=advanced.get("trim_end"),
    )
    notes = []
    if any(str(c.get("field") or "").startswith("post.subtitle") for c in changes):
        if str(advanced.get("subtitle") or "off") == "sidecar":
            notes.append("字幕已改为 SRT 旁挂文件（画面不烧录）")
        else:
            notes.append("字幕已关闭，本次不生成 SRT")
    run = Run(
        id=run_id,
        scenario=parent.scenario,
        title=parent.title,
        status="succeeded",
        step="post",
        progress=1.0,
        generation_mode=parent.generation_mode,
        inputs=inputs,
        advanced=advanced,
        persona_map=copy.deepcopy(parent.persona_map),
        persona_snapshot=copy.deepcopy(parent.persona_snapshot),
        selection=remake_planner.selection_for(parent.scenario, inputs, advanced),
        steps=[RunStep(name="post", label="后期", status="done", progress=1.0, started_at=store.now(), finished_at=store.now())],
        storyboard=copy.deepcopy(parent.storyboard),
        result={
            "video": store.rel_to_data(target),
            "srt": store.rel_to_data(root / "subtitles.srt") if (root / "subtitles.srt").is_file() else None,
            "width": (parent.result or {}).get("width"),
            "height": (parent.result or {}).get("height"),
            "duration_s": ffmpeg.probe(target)["duration_s"],
            "qa": (parent.result or {}).get("qa"),
            "demo": parent.demo,
            "model": (parent.result or {}).get("model"),
            "post_notes": notes,
            "post_only": True,
        },
        demo=parent.demo,
        created_at=store.now(),
        finished_at=store.now(),
        parent_run_id=parent.id,
        version=parent.version + 1,
        changes=changes,
    )
    store.write_run(run)
    # The copied QA report described the parent's artifact set; re-check so a
    # subtitle toggle shows up as the new run's own verdict.
    report = qa_pipeline.check(run_id)
    reloaded = store.read_run(run_id) or run
    reloaded.result = {**(reloaded.result or {}), "qa": report}
    store.write_run(reloaded)
    return reloaded


@app.post("/runs/{run_id}/derive")
def derive_run(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    parent = store.read_run(run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="run not found")
    changes = list(payload.get("changes") or [])
    if changes and all(str(change.get("stage") or "") == "post" for change in changes):
        return {"run": _post_derive(parent, changes).model_dump()}
    advanced = copy.deepcopy(parent.advanced)
    inputs = copy.deepcopy(parent.inputs)
    _apply_changes(advanced, inputs, changes)
    title = str(payload.get("title") or parent.title)
    new_run = _new_run(parent.scenario, inputs, advanced, title=title, parent=parent, changes=changes)
    return {"run": new_run.model_dump()}



def _segment_for(run_id: str, segment_id: str) -> tuple[Any, dict[str, Any]]:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    data = store.read_json(store.run_dir(run_id) / "artifacts" / "storyboard.json", {}) or {}
    rows = list(data.get("segments") or run.storyboard or [])
    for row in rows:
        item = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        if str(item.get("id")) == str(segment_id):
            return run, item
    raise HTTPException(status_code=404, detail=f"segment not found: {segment_id}")


def _h3_derived_edit(parent: Any, segment: dict[str, Any], instruction: str, label: str) -> Any:
    if parent.status == "running":
        raise HTTPException(status_code=409, detail="run is busy")
    if parent.status != "succeeded":
        raise HTTPException(status_code=409, detail="only a succeeded run can be edited")
    inputs = copy.deepcopy(parent.inputs or {})
    advanced = copy.deepcopy(parent.advanced or {})
    start = float(segment.get("start_s") or 0)
    end = float(segment.get("end_s") or 0)
    action = str(segment.get("action") or "").strip()
    scope = (
        f"只改镜头 #{int(segment.get('index') or 0) + 1}（{start:.2f}–{end:.2f}s"
        + (f"，原画面：{action[:120]}" if action else "")
        + f"）：{instruction}；其余镜头、场景、动作、构图、节奏和原声按默认契约保持不变。"
    )
    existing = str(inputs.get("explicit_overrides") or "").strip()
    inputs["explicit_overrides"] = (existing + "\n" + scope).strip()[:2400]
    brief = str(inputs.get("brief") or "").strip()
    inputs["brief"] = (brief + "\n本次修改：" + scope).strip()[:2000]
    advanced["model"] = "auto"
    advanced["remake_mode"] = "auto"
    advanced.setdefault("audio_mode", "regenerate")
    change = {
        "field": "segment.edit",
        "from": segment.get("id"),
        "to": instruction[:200],
        "stage": "generate",
        "requires_regeneration": True,
        "label": label,
    }
    return _new_run(parent.scenario, inputs, advanced, title=parent.title, parent=parent, changes=[change])


@app.post("/runs/{run_id}/segments/{segment_id}/regenerate")
def regenerate_segment(run_id: str, segment_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    parent = store.read_run(run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="run not found")
    advanced = copy.deepcopy(parent.advanced)
    inputs = copy.deepcopy(parent.inputs)
    changes = list(payload.get("changes") or [])
    _apply_changes(advanced, inputs, changes)
    new_run = _new_run(parent.scenario, inputs, advanced, title=parent.title, parent=parent, changes=[{"field": "selected_segment_id", "from": None, "to": segment_id, "stage": "generate", "requires_regeneration": True}] + changes)
    return {"run": new_run.model_dump()}


@app.post("/runs/{run_id}/segments/{segment_id}/replace")
def replace_segment(run_id: str, segment_id: str) -> JSONResponse:
    parent, segment = _segment_for(run_id, segment_id)
    if str((parent.selection or {}).get("mode")) == "h3_reference":
        new_run = _h3_derived_edit(
            parent,
            segment,
            "按原参考契约重做这一镜，只替换人物/商品，镜头/场景/动作/构图/节奏保持原样",
            "整条重生成镜头 #" + str(int(segment.get("index") or 0) + 1),
        )
        return JSONResponse(status_code=202, content={"run": new_run.model_dump()})
    try:
        run = segment_replace.start_replace(run_id, segment_id)
    except ValueError as exc:
        message = str(exc)
        code = 404 if "not found" in message else 409
        raise HTTPException(status_code=code, detail=message) from exc
    return JSONResponse(status_code=202, content={"run": run.model_dump()})


@app.post("/runs/{run_id}/segments/{segment_id}/edit")
def edit_segment(run_id: str, segment_id: str, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    """H3 edits rerun the whole clip; other modes rewrite one shot in place."""
    instruction = str(payload.get("instruction") or "").strip()
    if len(instruction) < 2:
        raise HTTPException(status_code=400, detail="instruction is required")
    parent, segment = _segment_for(run_id, segment_id)
    if str((parent.selection or {}).get("mode")) == "h3_reference":
        new_run = _h3_derived_edit(
            parent,
            segment,
            instruction,
            "整条重生成镜头 #" + str(int(segment.get("index") or 0) + 1),
        )
        return JSONResponse(status_code=202, content={"run": new_run.model_dump()})
    try:
        run = segment_replace.start_edit(run_id, segment_id, instruction)
    except ValueError as exc:
        message = str(exc)
        code = 404 if "not found" in message else 409
        raise HTTPException(status_code=code, detail=message) from exc
    return JSONResponse(status_code=202, content={"run": run.model_dump()})


@app.post("/runs/{run_id}/rollback")
def rollback_segment(run_id: str) -> dict[str, Any]:
    try:
        run = segment_replace.rollback(run_id)
    except ValueError as exc:
        message = str(exc)
        code = 404 if "not found" in message else 409
        raise HTTPException(status_code=code, detail=message) from exc
    return {"run": run.model_dump()}


@app.get("/runs/{run_id}/export")
def export_run(run_id: str) -> FileResponse:
    run = store.read_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    root = store.run_dir(run_id)
    target = root / "artifacts" / "export.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in ("final.mp4", "subtitles.srt", "qa.json", "script.json", "skeleton.json", "storyboard.json"):
            path = root / "artifacts" / name
            if path.is_file():
                zf.write(path, arcname=name)
    return FileResponse(target, media_type="application/zip", filename=f"{run_id}.zip")


# ---------------------------------------------------------------------------
# stitch
# ---------------------------------------------------------------------------
def _resolve_clips(payload: StitchRequest) -> list[dict[str, Any]]:
    rows = []
    for clip in payload.clips:
        record = store.get_asset(clip.asset_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"asset not found: {clip.asset_id}")
        rows.append({"path": str(store.safe_media_path(record["path"])), "in_s": clip.in_s, "out_s": clip.out_s})
    return rows


@app.post("/stitch/plan")
def stitch_plan(payload: StitchRequest) -> dict[str, Any]:
    rows = _resolve_clips(payload)
    output = payload.output or {}
    width, height = params.size_for(str(output.get("aspect") or "9:16"), str(output.get("resolution") or "720p"))
    try:
        plan = stitch_mod.plan(rows, width=width, height=height, fit=payload.fit, transition=payload.transition, audio=payload.audio)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"plan": plan, "output": output}


@app.post("/stitch")
def stitch(payload: StitchRequest) -> dict[str, Any]:
    rows = _resolve_clips(payload)
    output = payload.output or {}
    width, height = params.size_for(str(output.get("aspect") or "9:16"), str(output.get("resolution") or "720p"))
    try:
        plan = stitch_mod.plan(rows, width=width, height=height, fit=payload.fit, transition=payload.transition, audio=payload.audio)
        run_id = store.new_id("stitch")
        target = store.run_dir(run_id) / "artifacts" / "final.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        stitch_mod.execute(plan, target)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"stitch failed: {exc}") from exc
    asset = store.create_asset(target.read_bytes(), f"stitch-{run_id}.mp4", "video", "video/mp4")
    record = _probe_asset(asset.id)
    run = Run(
        id=run_id,
        scenario="stitch",
        title="拼接结果",
        status="succeeded",
        step="done",
        progress=1.0,
        inputs={"asset_ids": [clip.asset_id for clip in payload.clips]},
        advanced={"stitch": payload.model_dump()},
        steps=[],
        result={"video": record["path"], "asset_id": record["id"], "duration_s": record.get("duration_s"), "warnings": plan.get("warnings") or []},
        demo=False,
        created_at=store.now(),
        finished_at=store.now(),
    )
    store.write_run(run)
    return {"run": run.model_dump(), "asset": record, "plan": plan}


# ---------------------------------------------------------------------------
# context / assistant
# ---------------------------------------------------------------------------
@app.get("/context")
def get_context() -> dict[str, Any]:
    return {"context": store.read_context()}


@app.post("/context")
def set_context(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {"context": store.write_context(payload)}


@app.post("/assistant")
def assistant(req: AssistantRequest) -> dict[str, Any]:
    return intents.analyze(req)


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--graceful-timeout", type=int, default=5)
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
        timeout_graceful_shutdown=max(1, args.graceful_timeout),
    )


if __name__ == "__main__":
    main()
