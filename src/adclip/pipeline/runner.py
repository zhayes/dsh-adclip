"""Sequential run executor with cancellation and step persistence."""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .. import store
from ..models import RunStep
from ..media import ffmpeg
from . import analyze, generate, post, qa, script, segment

STEPS = [
    ("analyze", "拆解参考片", 0.1),
    ("gag", "抽梗", 0.2),
    ("script", "改编脚本", 0.3),
    ("generate", "生成原生对白视频", 0.6),
    ("post", "后期", 0.85),
    ("qa", "检查", 0.95),
]


class Canceled(RuntimeError):
    pass


def _set_step(run_id: str, name: str, status: str, progress: float, error: str | None = None) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    for step in run.steps:
        if step.name == name:
            step.status = status  # type: ignore[assignment]
            step.progress = progress
            if status == "running":
                step.started_at = store.now()
            if status in {"done", "failed", "skipped"}:
                step.finished_at = store.now()
            if error:
                step.error = error
            break
    run.step = name
    run.progress = progress
    store.write_run(run)


def _check_cancel(run_id: str) -> None:
    run = store.read_run(run_id)
    if run and run.cancel_requested:
        raise Canceled("canceled by user")


def execute(run_id: str) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    run.status = "running"
    run.error = None
    run.steps = [RunStep(name=name, label=label) for name, label, _ in STEPS]
    store.write_run(run)
    try:
        _check_cancel(run_id)
        _set_step(run_id, "analyze", "running", 0.05)
        skeleton = analyze.analyze(run_id)
        _set_step(run_id, "analyze", "done", 0.1)
        _check_cancel(run_id)

        _set_step(run_id, "gag", "running", 0.15)
        run = store.read_run(run_id)
        gag = script.build_gag(run, skeleton)
        store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "gag.json", gag)
        _set_step(run_id, "gag", "done", 0.2)
        _check_cancel(run_id)

        _set_step(run_id, "script", "running", 0.25)
        run = store.read_run(run_id)
        script_doc = script.build_script(run, skeleton, gag)
        store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "script.json", script_doc)
        _set_step(run_id, "script", "done", 0.3)
        _check_cancel(run_id)

        _set_step(run_id, "generate", "running", 0.35)
        generated = generate.generate(run_id)
        run = store.read_run(run_id)
        if run:
            run.demo = bool(generated.get("demo", True))
            store.write_run(run)
        _set_step(run_id, "generate", "done", 0.6)
        _check_cancel(run_id)

        _set_step(run_id, "post", "running", 0.7)
        result = post.post(run_id)
        _set_step(run_id, "post", "done", 0.85)
        _check_cancel(run_id)

        segment.build_storyboard(run_id)
        _set_step(run_id, "qa", "running", 0.9)
        qa_report = qa.check(run_id)
        _set_step(run_id, "qa", "done", 1.0)

        run = store.read_run(run_id)
        if run:
            run.status = "succeeded"
            run.progress = 1.0
            run.finished_at = store.now()
            run.demo = bool(generated.get("demo", True))
            run.result = {**result, "qa": qa_report, "demo": bool(generated.get("demo", True)), "model": generated.get("model")}
            store.write_run(run)
            store.write_context({"last_run_id": run.id, "last_reference_asset_id": (run.inputs or {}).get("reference_asset_id"), "last_product_ids": (run.inputs or {}).get("product_asset_ids"), "last_params": run.advanced, "last_brief": (run.inputs or {}).get("brief")})
    except Canceled:
        run = store.read_run(run_id)
        if run:
            run.status = "canceled"
            run.error = "已取消"
            run.finished_at = store.now()
            store.write_run(run)
    except Exception as exc:  # noqa: BLE001
        run = store.read_run(run_id)
        if run:
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:800]
            run.finished_at = store.now()
            store.write_run(run)
        traceback.print_exc()


class Manager:
    def __init__(self, workers: int = 2) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="adstudio-run")

    def start(self, run_id: str) -> None:
        self.pool.submit(execute, run_id)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


manager = Manager()
