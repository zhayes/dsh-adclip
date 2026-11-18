"""Reference analysis: probe, cut detection, beat grid, storyboard thumbnails."""
from __future__ import annotations

import json
import math
import os
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
                "movement": str(view.get("camera_movement") or ""),
                "angle": str(view.get("camera_angle") or ""),
            },
            "composition": str(view.get("composition") or ""),
            "continuity": str(view.get("continuity") or ""),
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


def _vision_max_frames() -> int:
    try:
        maximum = int(os.environ.get("ADSTUDIO_VISION_MAX_FRAMES", "12"))
    except (TypeError, ValueError):
        maximum = 12
    return max(4, min(16, maximum))


def _vision_budget(duration: float) -> int:
    """Initial frames worth spending: roughly one every 2.5s, with a floor/ceiling."""
    try:
        minimum = int(os.environ.get("ADSTUDIO_VISION_MIN_FRAMES", "4"))
    except (TypeError, ValueError):
        minimum = 4
    maximum = _vision_max_frames()
    target = int(math.ceil(max(0.1, float(duration)) / 2.5)) + 1
    return max(minimum, min(maximum, target))


def _frame_times(start: float, end: float, count: int) -> list[float]:
    count = max(1, int(count))
    span = max(0.0, float(end) - float(start))
    return [round(float(start) + span * (index + 0.5) / count, 3) for index in range(count)]


def _plan_analysis_frames(
    run_id: str,
    source: Path,
    beats: list[dict[str, Any]],
    duration: float,
    *,
    max_frames: int | None = None,
) -> list[dict[str, Any]]:
    """Distribute analysis frames across beats without crossing cut boundaries."""
    if not beats:
        return []
    budget = max(1, int(max_frames or _vision_budget(duration)))
    counts = [1 for _ in beats]
    while sum(counts) < budget:
        # Put the next frame in the beat with the coarsest current interval.
        index = max(range(len(beats)), key=lambda i: (float(beats[i]["end_s"]) - float(beats[i]["start_s"])) / counts[i])
        length = float(beats[index]["end_s"]) - float(beats[index]["start_s"])
        if length < 0.8 or counts[index] >= max(1, int(math.ceil(length / 1.5))):
            # All remaining beats are too short or already at their local cap.
            if all((float(b["end_s"]) - float(b["start_s"])) < 0.8 for b in beats):
                break
            # Allow one more pass rather than looping forever.
            if min((float(beats[i]["end_s"]) - float(beats[i]["start_s"])) / counts[i] for i in range(len(beats))) < 1.0:
                break
        counts[index] += 1
    frames: list[dict[str, Any]] = []
    for beat_index, (beat, count) in enumerate(zip(beats, counts)):
        start, end = float(beat["start_s"]), float(beat["end_s"])
        for frame_index, time_s in enumerate(_frame_times(start, end, count)):
            frame_id = f"{beat['id']}_f{frame_index}"
            thumb = store.run_artifact(run_id, f"storyboard/analysis_{frame_id}.jpg")
            try:
                ffmpeg.extract_frame(source, time_s, thumb, width=360)
            except Exception:
                continue
            frames.append({
                "id": frame_id,
                "beat_id": beat["id"],
                "start_s": start,
                "end_s": end,
                "time_s": time_s,
                "path": thumb,
            })
    return frames


def _aggregate_visual(
    visual_frames: dict[str, dict[str, Any]],
    frames: list[dict[str, Any]],
    beats: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Collapse one-or-more keyframe labels back onto each beat."""
    by_beat: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        item = visual_frames.get(str(frame.get("id"))) or {}
        if item:
            by_beat.setdefault(str(frame.get("beat_id")), []).append(item)
    aggregated: dict[str, dict[str, Any]] = {}
    scalar_fields = (
        "shot_size", "camera_angle", "camera_movement", "action", "product",
        "product_visibility", "scene", "composition", "on_screen_text", "continuity",
    )
    for beat in beats:
        items = by_beat.get(str(beat.get("id"))) or []
        if not items:
            continue
        best = max(items, key=lambda item: float(item.get("confidence") or 0.0))
        merged: dict[str, Any] = {}
        for field in scalar_fields:
            merged[field] = next((str(item.get(field)) for item in [best, *items] if item.get(field)), "")
        merged["people"] = next((str(item.get("people")) for item in [best, *items] if item.get("people")), "")
        merged["confidence"] = max((float(item.get("confidence") or 0.0) for item in items), default=0.0) or None
        merged["unclear"] = sorted({str(value) for item in items for value in (item.get("unclear") or []) if str(value).strip()})
        merged["frame_ids"] = [str(frame.get("id")) for frame in frames if str(frame.get("beat_id")) == str(beat.get("id")) and visual_frames.get(str(frame.get("id")))]
        aggregated[str(beat.get("id"))] = merged
    return aggregated

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
    analysis_frames: list[dict[str, Any]] = []
    refine_rounds = 0
    vision_budget = _vision_budget(duration) if vision.available() else 0
    vision_max_frames = _vision_max_frames() if vision.available() else 0
    if source and vision.available():
        analysis_frames = _plan_analysis_frames(run_id, source, beats, duration, max_frames=vision_budget)
        if analysis_frames:
            visual_frames = vision.analyze_frames(analysis_frames, max_frames=vision_budget)
            first_provider = str(getattr(vision, "LAST_PROVIDER", "") or "")
            first_model = str(getattr(vision, "LAST_MODEL", "") or "")
            if visual_frames:
                aggregate = _aggregate_visual(visual_frames, analysis_frames, beats)
                extra_frames: list[dict[str, Any]] = []
                remaining = max(0, min(4, vision_max_frames - len(analysis_frames)))
                for beat in beats:
                    if len(extra_frames) >= remaining:
                        break
                    item = aggregate.get(str(beat.get("id"))) or {}
                    confidence = float(item.get("confidence") or 0.0)
                    unclear = {str(value) for value in (item.get("unclear") or [])}
                    needed = (
                        not item
                        or confidence < 0.60
                        or bool(unclear & {"product", "action", "scene", "on_screen_text"})
                        or not any(item.get(field) for field in ("product", "action", "scene"))
                        or (float(beat["end_s"]) - float(beat["start_s"]) > 4.0 and len(item.get("frame_ids") or []) < 2)
                    )
                    if not needed:
                        continue
                    start_s, end_s = float(beat["start_s"]), float(beat["end_s"])
                    used = [float(frame["time_s"]) for frame in analysis_frames if frame.get("beat_id") == beat.get("id")]
                    candidate = None
                    for fraction in (0.25, 0.75, 0.5, 0.1, 0.9):
                        value = round(start_s + (end_s - start_s) * fraction, 3)
                        if all(abs(value - previous) > 0.35 for previous in used):
                            candidate = value
                            break
                    if candidate is None:
                        continue
                    frame_id = f"{beat['id']}_r{len(extra_frames)}"
                    thumb = store.run_artifact(run_id, f"storyboard/analysis_{frame_id}.jpg")
                    try:
                        ffmpeg.extract_frame(source, candidate, thumb, width=360)
                    except Exception:
                        continue
                    extra_frames.append({
                        "id": frame_id,
                        "beat_id": beat["id"],
                        "start_s": start_s,
                        "end_s": end_s,
                        "time_s": candidate,
                        "path": thumb,
                    })
                if extra_frames:
                    extra_visual = vision.analyze_frames(extra_frames, max_frames=len(extra_frames))
                    if extra_visual:
                        visual_frames.update(extra_visual)
                        analysis_frames.extend(extra_frames)
                        refine_rounds = 1
                    else:
                        # Keep the first pass's provider metadata if refinement failed.
                        vision.LAST_PROVIDER = first_provider
                        vision.LAST_MODEL = first_model
                        vision.LAST_ERROR = ""
                visual = _aggregate_visual(visual_frames, analysis_frames, beats)
            if not visual and first_provider:
                # Preserve the first provider's failure information for QA.
                vision.LAST_PROVIDER = first_provider
                vision.LAST_MODEL = first_model
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
                    "camera_angle": item.get("camera_angle") or "",
                    "camera_movement": item.get("camera_movement") or "",
                    "composition": item.get("composition") or "",
                    "continuity": item.get("continuity") or "",
                    "product_visibility": item.get("product_visibility") or "",
                    "confidence": item.get("confidence"),
                    "unclear": item.get("unclear") or [],
                    "frame_ids": item.get("frame_ids") or [],
                    "source": "vlm",
                }
    vision_error = str(getattr(vision, "LAST_ERROR", "") or "").strip()
    plan = _remake_plan(run, beats, facts, visual)
    plan["source"]["cuts_s"] = cuts
    provider = str(getattr(vision, "LAST_PROVIDER", "") or "")
    model = str(getattr(vision, "LAST_MODEL", "") or "")
    warnings = []
    if visual and provider == "dsh":
        warnings.append(f"视觉标签由 DSH 文本模型 {model or 'auto'} 生成")
    if not visual:
        warnings.append("视觉标签不可用，拆解为启发式结果")
        if vision_error:
            warnings.append(vision_error)
    analysis = {
        "mode": "frames" if visual else "heuristic",
        "provider": provider if visual else "",
        "model": model if visual else "",
        "degraded": not bool(visual),
        "reason": "" if visual else ("视觉标签不可用，拆解为启发式结果" + (f"：{vision_error}" if vision_error else "")),
        "warnings": warnings,
        "frame_count": len(analysis_frames),
        "initial_frame_budget": vision_budget,
        "vision_budget": vision_max_frames,
        "refine_rounds": refine_rounds,
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
        "confidence": {"asr": 0.85 if transcript else 0.0, "vision": (0.68 if provider == "dsh" else 0.75) if visual else 0.0, "speakers": 0.0, "structure": 0.6 if visual else 0.3},
        "notes": [
            "ASR transcript attached." if transcript else "No transcript: sound may be absent, ASR disabled, or speech not recognized.",
            (
                f"Doubao vision tags attached to keyframes ({model})." if provider == "ark"
                else ("Vision tags attached to keyframes." if provider == "minimax" else f"DSH vision tags attached to keyframes ({model}).")
            ) if visual else ("Vision unavailable or disabled." if not vision.available() else "Vision returned no usable tags."),
        ],
    }
    path = root / "artifacts" / "skeleton.json"
    store.atomic_write_json(path, skeleton)
    return skeleton
