"""True single-shot replacement and rollback.

Unlike the older /regenerate endpoint, this keeps the existing final clip and
only regenerates one storyboard slot, then splices it back with ffmpeg. The
previous final is kept under versions/ so the edit can be rolled back.
"""
from __future__ import annotations

import os
import shutil
import threading
import traceback
from pathlib import Path
from typing import Any

from .. import params, store
from ..media import ffmpeg
from ..media import stitch as stitch_mod
from . import generate, qa, script, segment


def _storyboard(run: Any) -> list[dict[str, Any]]:
    data = store.read_json(store.run_dir(run.id) / "artifacts" / "storyboard.json", {}) or {}
    return list(data.get("segments") or run.storyboard or [])


def _find(run: Any, segment_id: str) -> dict[str, Any]:
    for row in _storyboard(run):
        if str(row.get("id")) == segment_id:
            return row
    raise ValueError(f"segment not found: {segment_id}")


def _snapshot(run: Any) -> dict[str, Any]:
    return {
        "status": run.status,
        "step": run.step,
        "progress": run.progress,
        "error": run.error,
        "last_edit_error": run.last_edit_error,
        "result": dict(run.result or {}),
        "storyboard": [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in (run.storyboard or [])],
        "version": run.version,
        "segment_edits": list(run.segment_edits or []),
        "changes": list(run.changes or []),
        "finished_at": run.finished_at,
    }


def _restore_failed_edit(run_id: str, snapshot: dict[str, Any], error: str) -> None:
    """Keep the last deliverable instead of turning a successful run into a failure."""
    run = store.read_run(run_id)
    if run is None:
        return
    for key in ("status", "step", "progress", "result", "version", "segment_edits", "changes", "finished_at"):
        setattr(run, key, snapshot.get(key))
    run.error = snapshot.get("error")
    run.last_edit_error = error[:800]
    store.write_run(run)


def _versions(run_id: str) -> Path:
    path = store.run_dir(run_id) / "versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup(run: Any, final: Path) -> str:
    name = f"v{run.version}_{store.new_id('pre')}.mp4"
    target = _versions(run.id) / name
    shutil.copy2(final, target)
    return f"versions/{name}"


def _refresh(run: Any) -> None:
    final = store.run_artifact(run.id, "final.mp4")
    segment.build_storyboard(run.id)
    qa_report = qa.check(run.id)
    facts = ffmpeg.probe(final)
    result = dict(run.result or {})
    result.update({
        "video": store.rel_to_data(final),
        "srt": store.rel_to_data(store.run_artifact(run.id, "subtitles.srt")) if store.run_artifact(run.id, "subtitles.srt").is_file() else None,
        "width": facts.get("width"),
        "height": facts.get("height"),
        "duration_s": facts.get("duration_s"),
        "qa": qa_report,
        "demo": run.demo,
        "model": result.get("model"),
    })
    run.result = result
    run.status = "succeeded"
    run.step = "qa"
    run.progress = 1.0
    run.error = None
    run.last_edit_error = None
    run.finished_at = store.now()
    store.write_run(run)


def _run_replace(run_id: str, segment_id: str, snapshot: dict[str, Any] | None = None) -> None:
    run = store.read_run(run_id)
    if run is None:
        return
    try:
        seg = _find(run, segment_id)
        final = store.run_artifact(run_id, "final.mp4")
        if not final.is_file():
            raise FileNotFoundError("final video is missing")
        advanced = params.merged_advanced(run.advanced)
        width, height = params.size_for(str(advanced.get("aspect") or "9:16"), str(advanced.get("resolution") or "720p"))
        fps = int(advanced.get("fps") or 30)
        old_facts = ffmpeg.probe(final)
        start = max(0.0, float(seg.get("start_s") or 0))
        end = min(float(old_facts["duration_s"]), float(seg.get("end_s") or old_facts["duration_s"]))
        slot_len = max(0.5, end - start)
        raw = store.run_artifact(run_id, f"segment_replace_{segment_id}_raw.mp4")
        normalized = store.run_artifact(run_id, f"segment_replace_{segment_id}.mp4")
        generated = generate.generate_segment(run, seg, raw)
        run = store.read_run(run_id) or run
        run.progress = 0.65
        run.step = "stitch"
        store.write_run(run)
        ffmpeg.loop_to_duration(raw, normalized, width=width, height=height, fps=fps, duration=slot_len)

        before = start > 0.08
        after = end < float(old_facts["duration_s"]) - 0.08
        clips: list[dict[str, Any]] = []
        if before:
            clips.append({"path": str(final), "in_s": 0.0, "out_s": start})
        clips.append({"path": str(normalized), "in_s": 0.0, "out_s": slot_len})
        if after:
            clips.append({"path": str(final), "in_s": end, "out_s": float(old_facts["duration_s"])})
        target = store.run_artifact(run_id, "final.replace.mp4")
        plan_data = stitch_mod.plan(clips, width=width, height=height, fit="black_pad", transition="cut", audio="keep")
        stitch_mod.execute(plan_data, target)
        run = store.read_run(run_id) or run
        run.progress = 0.9
        run.step = "qa"
        store.write_run(run)
        backup = _backup(run, final)
        os.replace(target, final)
        run = store.read_run(run_id) or run
        run.version = int(run.version or 1) + 1
        run.segment_edits = list(run.segment_edits or [])
        run.segment_edits.append({
            "segment_id": segment_id,
            "index": seg.get("index"),
            "from_version": int(run.version) - 1,
            "to_version": int(run.version),
            "backup": backup,
            "model": generated.get("model"),
            "created_at": store.now(),
        })
        run.changes = list(run.changes or [])
        run.changes.append({
            "field": "segment.replace",
            "from": seg.get("index"),
            "to": segment_id,
            "stage": "generate",
            "requires_regeneration": False,
            "label": "替换分镜 #" + str(int(seg.get("index") or 0) + 1),
        })
        _refresh(run)
    except Exception as exc:  # noqa: BLE001
        if snapshot is not None:
            _restore_failed_edit(run_id, snapshot, f"{type(exc).__name__}: {exc}")
        else:
            run = store.read_run(run_id)
            if run:
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"[:800]
                run.finished_at = store.now()
                store.write_run(run)
        traceback.print_exc()


def _run_edit(run_id: str, segment_id: str, instruction: str, snapshot: dict[str, Any] | None = None) -> None:
    """Rewrite one beat, then regenerate only its slot."""
    try:
        run = store.read_run(run_id)
        if run is None:
            return
        seg = _find(run, segment_id)
        script.rewrite_shot(run, int(seg.get("index") or 0), instruction)
        segment.build_storyboard(run_id)
        _run_replace(run_id, segment_id, snapshot)
    except Exception as exc:  # noqa: BLE001
        if snapshot is not None:
            _restore_failed_edit(run_id, snapshot, f"{type(exc).__name__}: {exc}")
        else:
            run = store.read_run(run_id)
            if run:
                run.status = "failed"
                run.error = f"{type(exc).__name__}: {exc}"[:800]
                run.finished_at = store.now()
                store.write_run(run)
        traceback.print_exc()


def start_edit(run_id: str, segment_id: str, instruction: str) -> Any:
    run = store.read_run(run_id)
    if run is None:
        raise ValueError("run not found")
    if run.status == "running":
        raise ValueError("run is busy")
    _find(run, segment_id)
    if run.status != "succeeded":
        raise ValueError("only a succeeded run can be edited")
    if str((run.selection or {}).get("mode")) == "h3_reference":
        raise ValueError("H3 复刻不支持单镜替换；请使用整条重生成")
    script_path = store.run_dir(run_id) / "artifacts" / "script.json"
    script_doc = store.read_json(script_path, {}) or {}
    if not (script_doc.get("beats") or []):
        raise ValueError("单镜编辑需要 script.json；当前任务没有脚本，请使用整条重生成")
    snapshot = _snapshot(run)
    run.status = "running"
    run.step = "segment"
    run.progress = 0.05
    run.error = None
    store.write_run(run)
    threading.Thread(target=_run_edit, args=(run_id, segment_id, instruction, snapshot), daemon=True, name="adstudio-segment-edit").start()
    return run


def start_replace(run_id: str, segment_id: str) -> Any:
    run = store.read_run(run_id)
    if run is None:
        raise ValueError("run not found")
    if run.status == "running":
        raise ValueError("run is busy")
    _find(run, segment_id)
    if run.status != "succeeded":
        raise ValueError("only a succeeded run can be edited")
    if str((run.selection or {}).get("mode")) == "h3_reference":
        raise ValueError("H3 复刻不支持单镜替换；请使用整条重生成")
    snapshot = _snapshot(run)
    run.status = "running"
    run.step = "segment"
    run.progress = 0.1
    run.error = None
    store.write_run(run)
    threading.Thread(target=_run_replace, args=(run_id, segment_id, snapshot), daemon=True, name="adstudio-segment-replace").start()
    return run


def rollback(run_id: str) -> Any:
    run = store.read_run(run_id)
    if run is None:
        raise ValueError("run not found")
    edits = list(run.segment_edits or [])
    if not edits:
        raise ValueError("no segment edits to roll back")
    entry = edits[-1]
    backup = store.run_dir(run_id) / str(entry.get("backup") or "")
    final = store.run_artifact(run_id, "final.mp4")
    if not backup.is_file():
        raise ValueError("segment backup is missing")
    current = _versions(run_id) / f"v{run.version}_{store.new_id('rollback')}.mp4"
    shutil.copy2(final, current)
    shutil.copy2(backup, final)
    run.segment_edits = edits[:-1]
    run.version = int(run.version or 1) + 1
    run.changes = list(run.changes or [])
    run.changes.append({
        "field": "segment.rollback",
        "from": entry.get("segment_id"),
        "to": None,
        "stage": "generate",
        "requires_regeneration": False,
        "label": "回滚分镜 #" + str(int(entry.get("index") or 0) + 1),
    })
    _refresh(run)
    return run
