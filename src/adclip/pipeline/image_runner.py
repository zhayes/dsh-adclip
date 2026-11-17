"""Asynchronous text-to-image run executor."""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .. import image_params, store
from ..models import Run, RunStep
from ..providers import ark_image, minimax_image

IMAGE_PROVIDERS = {"minimax": minimax_image.generate, "ark": ark_image.generate}


def _provider_fatal(message: str) -> bool:
    text = str(message or "").lower()
    return any(token in text for token in ("insufficient balance", "余额", "quota", "unauthorized", "invalid api key", "401", "402", "403", "429", "rate limit"))


def _candidates(run: Run) -> tuple[list[dict[str, Any]], str]:
    advanced = run.advanced or {}
    requested = str(advanced.get("model") or "")
    has_reference = bool(str((run.inputs or {}).get("reference_asset_id") or ""))
    rows = [
        row for row in image_params.catalog()
        if row.get("available") and row.get("enabled", True)
        and ("image_to_image" in (row.get("capabilities") or []) if has_reference else "text_to_image" in (row.get("capabilities") or []))
    ]
    ordered: list[dict[str, Any]] = []
    if requested:
        ordered.extend(row for row in rows if row.get("id") == requested)
    ordered.extend(row for row in rows if row.get("id") != requested)
    return ordered, requested


def _fit_aspect(model: dict[str, Any], value: str) -> str:
    return value if value in (model.get("aspects") or []) else str((model.get("aspects") or ["1:1"])[0])


def _fit_area(model: dict[str, Any], value: str) -> str:
    return value if value in (model.get("areas") or []) else str(model.get("default_area") or (model.get("areas") or ["2K"])[0])


class Manager:
    def __init__(self, workers: int = 2) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="adstudio-image")

    def start(self, run_id: str) -> None:
        self.pool.submit(execute, run_id)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


manager = Manager()


def _update(run_id: str, **fields: Any) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    for key, value in fields.items():
        setattr(run, key, value)
    store.write_run(run)


def execute(run_id: str) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    run.status = "running"
    run.step = "image"
    run.progress = 0.2
    run.error = None
    run.steps = [RunStep(name="image", label="生成图片", status="running", progress=0.2)]
    store.write_run(run)
    attempts: list[dict[str, Any]] = []
    warnings: list[str] = []
    requested = str((run.advanced or {}).get("model") or "")
    try:
        prompt = str((run.inputs or {}).get("prompt") or "").strip()
        if not prompt:
            raise RuntimeError("prompt 不能为空")
        candidates, requested = _candidates(run)
        if not candidates:
            raise RuntimeError("没有可用的图片模型；请在设置里启用对应厂商 key")
        ref_id = str((run.inputs or {}).get("reference_asset_id") or "")
        reference = store.asset_media_path(ref_id) if ref_id else None
        requested_aspect = str((run.advanced or {}).get("aspect") or "1:1")
        requested_area = str((run.advanced or {}).get("area") or "2K")
        skipped_providers: set[str] = set()
        last_error = ""
        for model in candidates:
            model_id = str(model.get("id") or "")
            provider_name = str(model.get("provider") or "")
            if provider_name in skipped_providers:
                attempts.append({"model": model_id, "error": "skipped: same provider failed"})
                continue
            provider = IMAGE_PROVIDERS.get(provider_name)
            if provider is None:
                attempts.append({"model": model_id, "error": "no adapter"})
                continue
            try:
                aspect = _fit_aspect(model, requested_aspect)
                area = _fit_area(model, requested_area)
                if aspect != requested_aspect:
                    warnings.append(f"{model_id} 不支持 {requested_aspect}，改用 {aspect}")
                if area != requested_area:
                    warnings.append(f"{model_id} 不支持 {requested_area}，改用 {area}")
                safe_model = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in model_id)
                raw = store.run_artifact(run_id, f"image-{safe_model}.bin")
                generated = provider(
                    prompt,
                    model=str(model["model"]),
                    aspect=aspect,
                    area=area,
                    output=raw,
                    reference=reference,
                )
                suffix = ".png" if raw.read_bytes()[:4] == b"\x89PNG" else ".jpg"
                image_path = raw.with_suffix(suffix)
                raw.replace(image_path)
                raw = image_path
                width, height = generated.get("width"), generated.get("height")
                if not width or not height:
                    try:
                        from PIL import Image
                        with Image.open(raw) as image:
                            width, height = image.size
                    except Exception:
                        width = height = None
                mime = "image/png" if raw.suffix == ".png" else "image/jpeg"
                asset = store.create_asset(raw.read_bytes(), f"image-{run_id}{raw.suffix}", "image", mime)
                run = store.read_run(run_id) or run
                run.status = "succeeded"
                run.step = "done"
                run.progress = 1.0
                run.finished_at = store.now()
                run.demo = False
                run.advanced["model"] = model_id
                run.steps = [RunStep(name="image", label="生成图片", status="done", progress=1.0, started_at=run.created_at, finished_at=store.now())]
                if attempts:
                    warnings.append("已从 " + "、".join(str(item.get("model") or "") for item in attempts) + " 切换到 " + model_id)
                run.result = {
                    "image": store.rel_to_data(raw),
                    "asset_id": asset.id,
                    "width": width,
                    "height": height,
                    "model": model_id,
                    "native_model": model.get("model"),
                    "aspect": aspect,
                    "area": area,
                    "prompt": prompt,
                    "requested_model": requested,
                    "attempts": attempts,
                    "warnings": warnings,
                }
                store.write_run(run)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"[:500]
                attempts.append({"model": model_id, "error": last_error})
                if _provider_fatal(last_error):
                    skipped_providers.add(provider_name)
        raise RuntimeError("所有图片模型均失败：" + " | ".join(f"{item['model']}: {item['error']}" for item in attempts)[:900])
    except Exception as exc:  # noqa: BLE001
        run = store.read_run(run_id)
        if run:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:900]
            run.finished_at = store.now()
            run.result = {"requested_model": requested, "attempts": attempts, "warnings": warnings}
            run.steps = [RunStep(name="image", label="生成图片", status="failed", progress=1.0, error=run.error, finished_at=store.now())]
            store.write_run(run)
        traceback.print_exc()

def create(prompt: str, model_id: str = "", aspect: str = "1:1", area: str = "2K", *, parent: Run | None = None, reference_asset_id: str = "") -> Run:
    requested = model_id or image_params.default_model()
    model = image_params.get_model(requested)
    if model is None:
        raise ValueError("没有可用的图片模型；请在设置里配置对应厂商 key")
    usable = [row for row in image_params.catalog() if row.get("available") and row.get("enabled", True)]
    if not usable:
        raise ValueError("没有可用的图片模型；请在设置里启用对应厂商 key")
    aspect = aspect or str(model.get("aspects") or ["1:1"])[0]
    area = area or str(model.get("default_area") or "2K")
    run_id = store.new_id("img")
    store.run_dir(run_id).mkdir(parents=True, exist_ok=True)
    (store.run_dir(run_id) / "artifacts").mkdir(parents=True, exist_ok=True)
    head = prompt.strip().split("。")[0][:26]
    run = Run(
        id=run_id,
        scenario="text-to-image",
        title=("文生图片 · " + head) if head else "文生图片",
        status="queued",
        step="queued",
        progress=0.0,
        inputs={"prompt": prompt, **({"reference_asset_id": reference_asset_id} if reference_asset_id else {})},
        advanced={"model": model["id"], "aspect": aspect, "area": area},
        steps=[RunStep(name="image", label="生成图片")],
        demo=False,
        created_at=store.now(),
        parent_run_id=parent.id if parent else None,
        version=(parent.version + 1) if parent else 1,
    )
    store.write_run(run)
    manager.start(run.id)
    return run
