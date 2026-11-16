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
    for beat in beats:
        if transcript:
            texts = [
                item["text"]
                for item in transcript
                if float(item["start_s"]) < float(beat["end_s"]) and float(item["end_s"]) > float(beat["start_s"])
            ]
            beat["dialogue"] = texts
            beat["dialogue_source"] = "asr"
        else:
            beat["dialogue"] = []
        if source:
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
    skeleton = {
        "version": 2,
        "partial": False,
        "source": {**facts, "asset_id": ref_id},
        "cuts_s": cuts,
        "beats": beats,
        "transcript": transcript,
        "confidence": {"asr": 0.85 if transcript else 0.0, "vision": 0.75 if visual else 0.0, "speakers": 0.0},
        "notes": [
            "ASR transcript attached." if transcript else "No transcript: sound may be absent, ASR disabled, or speech not recognized.",
            "M3 vision tags attached to keyframes." if visual else ("Vision unavailable or disabled." if not vision.available() else "Vision returned no usable tags."),
        ],
    }
    path = root / "artifacts" / "skeleton.json"
    store.atomic_write_json(path, skeleton)
    return skeleton
