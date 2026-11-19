"""Sequential run executor with cancellation and step persistence."""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .. import remake_planner, store
from ..models import RunStep
from . import analyze, generate, post, qa, script, segment

STEPS = [
    ("analyze", "拆解参考片", 0.1),
    ("gag", "抽梗", 0.2),
    ("script", "改编脚本", 0.3),
    ("confirm", "确认提示词", 0.32),
    ("generate", "生成原生对白视频", 0.6),
    ("post", "后期", 0.85),
    ("qa", "检查", 0.95),
]


class Canceled(RuntimeError):
    pass


def _needs_confirmation(run: Any) -> bool:
    """Should the run pause before spending a video generation call?

    The prompt is the most expensive thing to get wrong: a bad one wastes a
    whole generation. The operator confirms it in the task detail, and the run
    waits in `awaiting_confirm` until then.
    """
    advanced = getattr(run, "advanced", None) or {}
    if advanced.get("prompt_confirmed") or advanced.get("prompt_confirm") is False:
        return False
    # Free-create already confirms at the proposal card, and the user wrote the
    # prompt themselves; only the remake renders a prompt on their behalf.
    return str(getattr(run, "scenario", "")) == "viral-remake"


def _park_for_confirmation(run_id: str) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    for step in run.steps:
        if step.name == "confirm":
            step.status = "running"  # type: ignore[assignment]
            step.progress = 0.32
            step.started_at = step.started_at or store.now()
        elif step.name in {"generate", "post", "qa"}:
            step.status = "pending"  # type: ignore[assignment]
    run.status = "awaiting_confirm"  # type: ignore[assignment]
    run.step = "confirm"
    run.progress = 0.32
    store.write_run(run)


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


def _prepare_prompt_scripts(run_id: str, skeleton: dict[str, Any], *, guarded: bool) -> None:
    """gag + script artefacts. H3 tolerates a failed text model, free runs do not."""
    _set_step(run_id, "gag", "running", 0.15)
    run = store.read_run(run_id)
    if guarded:
        try:
            gag = script.build_gag(run, skeleton)
        except Exception as exc:  # noqa: BLE001
            gag = {"version": 2, "mechanism": "none", "must_keep": [], "source": {"degraded": True, "reason": str(exc)[:200]}}
    else:
        gag = script.build_gag(run, skeleton)
    store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "gag.json", gag)
    _set_step(run_id, "gag", "done", 0.2)
    _check_cancel(run_id)

    _set_step(run_id, "script", "running", 0.25)
    run = store.read_run(run_id)
    if guarded:
        try:
            script_doc = script.build_script(run, skeleton, gag)
        except Exception as exc:  # noqa: BLE001
            script_doc = {
                "version": 2,
                "beats": [
                    {"id": beat.get("id"), "function": beat.get("function"), "start_s": beat.get("start_s"), "end_s": beat.get("end_s"), "lines": [], "shot": ""}
                    for beat in skeleton.get("beats") or []
                ],
                "source": {"degraded": True, "reason": str(exc)[:200]},
            }
    else:
        script_doc = script.build_script(run, skeleton, gag)
    store.atomic_write_json(store.run_dir(run_id) / "artifacts" / "script.json", script_doc)
    _set_step(run_id, "script", "done", 0.3)
    _check_cancel(run_id)


def execute(run_id: str, *, resume: bool = False) -> None:
    """Run the pipeline. `resume=True` continues after a confirmed prompt."""
    run = store.read_run(run_id)
    if run is None:
        return
    run.status = "running"
    run.error = None
    if not resume:
        run.steps = [RunStep(name=name, label=label) for name, label, _ in STEPS]
    store.write_run(run)
    try:
        if not resume:
            _check_cancel(run_id)
            _set_step(run_id, "analyze", "running", 0.05)
            skeleton = analyze.analyze(run_id)
            run = store.read_run(run_id)
            if run is not None:
                source = skeleton.get("source") or {}
                run.selection = remake_planner.select(
                    run,
                    source_duration=source.get("duration_s"),
                    source_aspect=str(source.get("aspect") or ""),
                    source_size_bytes=source.get("size_bytes"),
                )
                store.write_run(run)
            _set_step(run_id, "analyze", "done", 0.1)
            _check_cancel(run_id)

            run = store.read_run(run_id)
            selection = (run.selection if run else {}) or {}
            if selection.get("mode") == "analysis_only":
                for name in ("gag", "script", "confirm", "generate", "post", "qa"):
                    _set_step(run_id, name, "skipped", 0.0)
                run = store.read_run(run_id)
                if run:
                    run.status = "succeeded"
                    run.step = "analyze"
                    run.progress = 1.0
                    run.finished_at = store.now()
                    run.result = {"analysis_only": True, "video": None, "srt": None, "duration_s": (skeleton.get("source") or {}).get("duration_s"), "qa": None, "demo": False, "model": ""}
                    store.write_run(run)
                return

            _prepare_prompt_scripts(run_id, skeleton, guarded=selection.get("mode") == "h3_reference")
            run = store.read_run(run_id)
            if run is not None and _needs_confirmation(run):
                _park_for_confirmation(run_id)
                return
        else:
            skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
            _set_step(run_id, "confirm", "done", 0.32)
            _check_cancel(run_id)

        run = store.read_run(run_id)
        selection = (run.selection if run else {}) or {}
        is_h3 = selection.get("mode") == "h3_reference"

        _set_step(run_id, "generate", "running", 0.35)
        generated = generate.generate(run_id)
        run = store.read_run(run_id)
        if run:
            run.demo = bool(generated.get("demo", True))
            if is_h3 and generated.get("audio_mode"):
                run.advanced["audio_mode"] = generated.get("audio_mode")
            # H3's audio-source check reads run.result, so publish the partial
            # result before QA runs.
            if is_h3:
                run.result = {
                    **(run.result or {}),
                    "audio_mode": generated.get("audio_mode"),
                    "audio_source": generated.get("audio_source"),
                    "warnings": list(dict.fromkeys(generated.get("warnings") or [])),
                }
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
            forced = ["替换商品需要新产品名称，已自动改为按新台词生成口播"] if run.advanced.get("audio_mode_forced") else []
            run.status = "succeeded"
            run.progress = 1.0
            run.finished_at = store.now()
            run.demo = bool(generated.get("demo", True))
            run.result = {
                **result,
                "qa": qa_report,
                "remake_score": (qa_report or {}).get("remake_score"),
                "demo": bool(generated.get("demo", True)),
                "model": generated.get("model"),
                "audio_mode": generated.get("audio_mode") or run.advanced.get("audio_mode"),
                "audio_source": result.get("audio_source") or generated.get("audio_source"),
                "attempts": generated.get("attempts") or [],
                "warnings": list(dict.fromkeys((generated.get("warnings") or []) + (result.get("warnings") or []) + forced)),
            }
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


def confirm(run_id: str) -> None:
    """Resume a parked run after the operator approved the prompt."""
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    if run.status != "awaiting_confirm":
        raise ValueError("run is not waiting for confirmation")
    run.advanced["prompt_confirmed"] = True
    run.status = "running"  # type: ignore[assignment]
    run.step = "confirm"
    store.write_run(run)
    manager.start(run_id, resume=True)


class Manager:
    def __init__(self, workers: int = 2) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="adstudio-run")

    def start(self, run_id: str, *, resume: bool = False) -> None:
        self.pool.submit(execute, run_id, resume=resume)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


manager = Manager()
