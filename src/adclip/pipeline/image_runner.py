"""Asynchronous text-to-image run executor."""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .. import image_params, store
from ..models import Run, RunStep
from ..providers import minimax_image


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
    try:
        advanced = run.advanced or {}
        model_id = str(advanced.get("model") or "")
        model = image_params.get_model(model_id)
        if model is None or not model.get("available"):
            raise RuntimeError("图片模型不可用：" + model_id)
        prompt = str((run.inputs or {}).get("prompt") or "").strip()
        if not prompt:
            raise RuntimeError("prompt 不能为空")
        raw = store.run_artifact(run_id, "image.jpg")
        generated = minimax_image.generate(
            prompt,
            model=str(model["model"]),
            aspect=str(advanced.get("aspect") or "1:1"),
            area=str(advanced.get("area") or "2K"),
            output=raw,
        )
        width, height = generated.get("width"), generated.get("height")
        if not width or not height:
            try:
                from PIL import Image
                with Image.open(raw) as image:
                    width, height = image.size
            except Exception:
                width = height = None
        asset = store.create_asset(raw.read_bytes(), f"image-{run_id}.jpg", "image", "image/jpeg")
        run = store.read_run(run_id) or run
        run.status = "succeeded"
        run.step = "done"
        run.progress = 1.0
        run.finished_at = store.now()
        run.demo = False
        run.steps = [RunStep(name="image", label="生成图片", status="done", progress=1.0, started_at=run.created_at, finished_at=store.now())]
        run.result = {
            "image": store.rel_to_data(raw),
            "asset_id": asset.id,
            "width": width,
            "height": height,
            "model": model_id,
            "native_model": model.get("model"),
            "aspect": str(advanced.get("aspect") or "1:1"),
            "area": str(advanced.get("area") or "2K"),
            "prompt": prompt,
        }
        store.write_run(run)
    except Exception as exc:  # noqa: BLE001
        run = store.read_run(run_id)
        if run:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:800]
            run.finished_at = store.now()
            run.steps = [RunStep(name="image", label="生成图片", status="failed", progress=1.0, error=run.error, finished_at=store.now())]
            store.write_run(run)
        traceback.print_exc()


def create(prompt: str, model_id: str = "", aspect: str = "1:1", area: str = "2K", *, parent: Run | None = None) -> Run:
    model = image_params.get_model(model_id or image_params.default_model())
    if model is None:
        raise ValueError("没有可用的图片模型；请配置 MINIMAX_API_KEY")
    if not model.get("available"):
        raise ValueError("图片模型不可用；请配置 MINIMAX_API_KEY")
    aspect = aspect if aspect in (model.get("aspects") or []) else "1:1"
    area = area if area in (model.get("areas") or []) else str(model.get("default_area") or "2K")
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
        inputs={"prompt": prompt},
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
