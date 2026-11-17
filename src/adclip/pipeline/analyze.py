"""Reference analysis: probe, cut detection, beat grid, storyboard thumbnails."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import store
from ..media import asr, ffmpeg, vision


def _beats(duration: float, cuts: list[float]) -> list[dict[str, Any]]:
    points = [0.0] + [round(c, 3) for c in cuts if 0.4 < c < duration - 0.4] + [round(duration, 3)]
    if len(points) <= 2:
        step = max(2.0, duration / 4.0)
        points = [0.0]
        t = step
        while t < duration - 1.0:
            points.append(round(t, 3))
            t += step
        points.append(round(duration, 3))
    # merge tiny beats into the next one
    merged: list[float] = [points[0]]
    for value in points[1:]:
        if value - merged[-1] < 0.8 and value != points[-1]:
            continue
        merged.append(value)
    if merged[-1] != points[-1]:
        merged.append(points[-1])
    # cap at 6 readable beats
    while len(merged) > 7:
        idx = min(range(1, len(merged) - 1), key=lambda i: merged[i] - merged[i - 1])
        del merged[idx]
    functions = ["hook", "setup", "escalation", "insult", "cta", "punchline", "beat"]
    rows = []
    for i in range(len(merged) - 1):
        start, end = merged[i], merged[i + 1]
        if end - start < 0.25:
            continue
        rows.append(
            {
                "id": f"b{len(rows)}",
                "start_s": round(start, 3),
                "end_s": round(end, 3),
                "len_s": round(end - start, 2),
                "function": functions[min(len(rows), len(functions) - 1)],
                "function_source": "heuristic",
                "confidence": 0.55,
                "dialogue": [],
                "visual": {"action": "", "shot_size": "中景", "product": {}},
            }
        )
    return rows


def _assign_transcript(beats: list[dict[str, Any]], transcript: list[dict[str, Any]]) -> None:
    """Assign each ASR line to the beat with the largest temporal overlap.

    The old all-overlaps assignment duplicated boundary lines into both
    neighbours. One line belongs to one beat; a weak overlap is dropped.
    """
    for beat in beats:
        beat["dialogue"] = []
        beat["dialogue_source"] = "asr"
    for item in transcript:
        try:
            start = float(item.get("start_s") or 0)
            end = float(item.get("end_s") or 0)
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        best = None
        best_overlap = 0.0
        for beat in beats:
            overlap = max(0.0, min(end, float(beat["end_s"])) - max(start, float(beat["start_s"])))
            if overlap > best_overlap:
                best, best_overlap = beat, overlap
        if best is not None and best_overlap >= max(0.15, 0.2 * (end - start)):
            best["dialogue"].append(str(item.get("text") or "").strip())


def _remake_plan(run: Any, beats: list[dict[str, Any]], facts: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    scope = str((run.advanced or {}).get("replace_scope") or "both")
    replace = ["商品"] if scope == "product" else ["人物"] if scope == "person" else ["人物", "商品"]
    shots = []
    for index, beat in enumerate(beats):
        view = beat.get("visual") or {}
        product_name = ""
        product = view.get("product")
        if isinstance(product, dict):
            product_name = str(product.get("name") or "")
        people = str(view.get("people") or "")
        shots.append({
            "id": f"s{index}",
            "start_s": beat.get("start_s"),
            "end_s": beat.get("end_s"),
            "camera": {
                "shot_size": str(view.get("shot_size") or ""),
                "movement": "",
                "angle": "",
            },
            "scene": str(view.get("scene") or ""),
            "action": str(view.get("action") or ""),
            "cast": [{"role": "A", "description": people}] if people else [],
            "product": {
                "name": product_name,
                "appearance": "",
                "position": "",
            },
            "dialogue": list(beat.get("dialogue") or []),
            "on_screen_text": str(view.get("on_screen_text") or ""),
            "transition_in": "cut" if index else "start",
            "preserve": ["镜头", "景别", "运镜", "场景", "动作", "构图", "节奏", "转场", "原声"],
            "replace": replace,
        })
    return {
        "version": 1,
        "source": {
            "duration_s": facts.get("duration_s"),
            "aspect": facts.get("aspect"),
            "cuts_s": [],
            "asset_id": (run.inputs or {}).get("reference_asset_id"),
        },
        "shots": shots,
        "global": {
            "preserve": ["镜头", "景别", "运镜", "场景", "动作", "构图", "节奏", "转场", "原声"],
            "replace": replace,
            "warnings": [] if visual else ["视觉标签不可用，拆解为启发式结果"],
        },
    }


def analyze(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    root = store.run_dir(run_id)
    root.mkdir(parents=True, exist_ok=True)
    ref_id = (run.inputs or {}).get("reference_asset_id")
    source = store.asset_media_path(ref_id) if ref_id else None
    facts = ffmpeg.probe(source) if source else {
        "duration_s": float((run.advanced or {}).get("duration") or 12),
        "width": 720, "height": 1280, "fps": 30, "aspect": "9:16", "has_audio": False,
    }
    duration = float(facts["duration_s"])
    cuts = ffmpeg.detect_cuts(source, duration) if source else []
    beats = _beats(duration, cuts)
    transcript: list[dict[str, Any]] = []
    if source and facts.get("has_audio") and asr.available():
        try:
            transcript = asr.transcribe(source)
        except Exception:
            transcript = []
    if transcript:
        _assign_transcript(beats, transcript)
    else:
        for beat in beats:
            beat["dialogue"] = []
            beat["dialogue_source"] = "asr"
    if source:
        for beat in beats:
            thumb = store.run_artifact(run_id, f"storyboard/{beat['id']}.jpg")
            try:
                ffmpeg.extract_frame(source, (beat["start_s"] + beat["end_s"]) / 2, thumb, width=360)
                beat["thumbnail"] = store.rel_to_data(thumb)
            except Exception:
                beat["thumbnail"] = None
    visual: dict[str, Any] = {}
    if source and vision.available():
        frames = [
            {"id": beat["id"], "start_s": beat["start_s"], "end_s": beat["end_s"], "path": store.run_artifact(run_id, f"storyboard/{beat['id']}.jpg")}
            for beat in beats
            if store.run_artifact(run_id, f"storyboard/{beat['id']}.jpg").is_file()
        ]
        try:
            visual = vision.analyze_frames(frames)
        except Exception:
            visual = {}
        for beat in beats:
            item = visual.get(beat["id"]) or {}
            if item:
                beat["visual"] = {
                    "action": item.get("action") or "",
                    "shot_size": item.get("shot_size") or "中景",
                    "product": {"name": item.get("product") or ""},
                    "people": item.get("people") or "",
                    "scene": item.get("scene") or "",
                    "on_screen_text": item.get("on_screen_text") or "",
                    "source": "vlm",
                }
    plan = _remake_plan(run, beats, facts, visual)
    plan["source"]["cuts_s"] = cuts
    analysis = {
        "mode": "frames" if visual else "heuristic",
        "provider": "minimax" if visual else "",
        "model": "MiniMax-M3" if visual else "",
        "degraded": not bool(visual),
        "reason": "" if visual else "视觉标签不可用，拆解为启发式结果",
        "warnings": [] if visual else ["视觉标签不可用，拆解为启发式结果"],
    }
    skeleton = {
        "version": 3,
        "partial": False,
        "source": {**facts, "asset_id": ref_id},
        "analysis": analysis,
        "remake_plan": plan,
        "cuts_s": cuts,
        "beats": beats,
        "transcript": transcript,
        "confidence": {"asr": 0.85 if transcript else 0.0, "vision": 0.75 if visual else 0.0, "speakers": 0.0, "structure": 0.6 if visual else 0.3},
        "notes": [
            "ASR transcript attached." if transcript else "No transcript: sound may be absent, ASR disabled, or speech not recognized.",
            "M3 vision tags attached to keyframes." if visual else ("Vision unavailable or disabled." if not vision.available() else "Vision returned no usable tags."),
        ],
    }
    path = root / "artifacts" / "skeleton.json"
    store.atomic_write_json(path, skeleton)
    return skeleton
