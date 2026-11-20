"""Reference analysis: probe, cut detection, beat grid, storyboard thumbnails."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Any

from .. import analysis_cache, store
from ..media import asr, ffmpeg, similarity, vision
from . import timing


def _dialogue_gaps(transcript: list[dict[str, Any]], *, min_gap: float = 0.6) -> list[float]:
    """Midpoints of real pauses in the transcript."""
    rows: list[tuple[float, float]] = []
    for item in transcript:
        try:
            start = float(item.get("start_s") or 0)
            end = float(item.get("end_s") or 0)
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        rows.append((start, end))
    rows.sort()
    gaps: list[float] = []
    previous_end = 0.0
    for start, end in rows:
        if start - previous_end >= min_gap:
            gaps.append(round((previous_end + start) / 2, 3))
        previous_end = max(previous_end, end)
    return gaps


def _beats(duration: float, cuts: list[float], *, transcript: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Beat grid from validated cuts, refined by dialogue pauses.

    A single-take reference stays one beat unless the transcript has a real
    pause to split on: camera movement is not a shot boundary.
    """
    points = [0.0] + [round(c, 3) for c in cuts if 0.4 < c < duration - 0.4] + [round(duration, 3)]
    # merge tiny beats into the next one
    merged: list[float] = [points[0]]
    for value in points[1:]:
        if value - merged[-1] < 0.8 and value != points[-1]:
            continue
        merged.append(value)
    if merged[-1] != points[-1]:
        merged.append(points[-1])
    if len(merged) <= 2 and transcript:
        for gap in _dialogue_gaps(transcript):
            if not (0.8 < gap < duration - 0.8):
                continue
            if min(abs(gap - point) for point in merged) < 1.2:
                continue
            merged.append(gap)
        merged = sorted(set(merged))
    # cap at 8 readable beats
    while len(merged) > 9:
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
                "dialogue_rows": [],
                "visual": {"action": "", "shot_size": "中景", "product": {}, "cast": [], "background": "", "lighting": ""},
            }
        )
    return rows


def _assign_transcript(beats: list[dict[str, Any]], transcript: list[dict[str, Any]]) -> None:
    """Attach every ASR line to the beat with the largest temporal overlap.

    No line is dropped. A line longer than its beat still belongs to the beat
    with the most overlap and is flagged `crosses_boundary`, so the dialogue
    timeline stays complete even when beats and speech disagree.
    """
    for beat in beats:
        beat["dialogue"] = []
        beat["dialogue_rows"] = []
    for item in transcript:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start_s") or 0)
            end = float(item.get("end_s") or 0)
        except (TypeError, ValueError):
            continue
        if end < start:
            end = start
        best = None
        best_overlap = 0.0
        for beat in beats:
            overlap = max(0.0, min(end, float(beat["end_s"])) - max(start, float(beat["start_s"])))
            if overlap > best_overlap:
                best, best_overlap = beat, overlap
        if best is None:
            # The line sits in a gap with no overlap; attach it to the nearest beat.
            middle = (start + end) / 2
            best = min(
                beats,
                key=lambda beat: abs((float(beat["start_s"]) + float(beat["end_s"])) / 2 - middle),
            )
        best["dialogue_rows"].append({
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "text": text,
            "crosses_boundary": bool(
                start < float(best["start_s"]) - 0.05 or end > float(best["end_s"]) + 0.05
            ),
        })
        best["dialogue"].append(text)


def _snap_beats(beats: list[dict[str, Any]], *, window: float = 0.35, minimum: float = 0.4) -> None:
    """Move beat boundaries into a nearby dialogue gap.

    The ASR timeline is the clock: a beat boundary 0.3s before a line ends cuts
    the sentence in half. Nudging the boundary into the gap keeps sentence and
    shot aligned without dropping any line.
    """
    for index in range(1, len(beats)):
        previous, current = beats[index - 1], beats[index]
        boundary = float(current["start_s"])
        span_start, span_end = float(previous["start_s"]), float(current["end_s"])
        candidates: list[float] = []
        for beat in (previous, current):
            for row in beat.get("dialogue_rows") or []:
                candidates.extend((float(row["start_s"]), float(row["end_s"])))
        best = None
        for value in candidates:
            if abs(value - boundary) > window:
                continue
            if value - span_start < minimum or span_end - value < minimum:
                continue
            if best is None or abs(value - boundary) < abs(best - boundary):
                best = value
        if best is None:
            continue
        boundary = round(best, 3)
        previous["end_s"] = boundary
        current["start_s"] = boundary
        previous["len_s"] = round(boundary - span_start, 2)
        current["len_s"] = round(span_end - boundary, 2)
    for beat in beats:
        for row in beat.get("dialogue_rows") or []:
            row["crosses_boundary"] = bool(
                float(row["start_s"]) < float(beat["start_s"]) - 0.05
                or float(row["end_s"]) > float(beat["end_s"]) + 0.05
            )


def _pace_cps(rows: list[dict[str, Any]]) -> float | None:
    """Speaking rate of the reference dialogue: characters per spoken second.

    Measured from the ASR timings instead of assumed: an ad that is shouted at
    7 chars/s must not be remade at a fixed 4 chars/s, or the delivery loses
    its urgency.
    """
    value = timing.measured_cps(rows)
    return round(value, 2) if value else None


def _remake_plan(run: Any, beats: list[dict[str, Any]], facts: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    scope = str((run.advanced or {}).get("replace_scope") or "both")
    replace = (
        [] if scope == "none"
        else ["商品"] if scope == "product"
        else ["人物"] if scope == "person"
        else ["人物", "商品"]
    )
    shots = []
    for index, beat in enumerate(beats):
        view = beat.get("visual") or {}
        product_name = ""
        product = view.get("product")
        if isinstance(product, dict):
            product_name = str(product.get("name") or "")
        people = str(view.get("people") or "")
        cast: list[dict[str, Any]] = []
        for position, item in enumerate(view.get("cast") or []):
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or "").strip() or vision.cast_description(item)
            if not description:
                continue
            cast.append({
                "key": str(item.get("key") or chr(65 + position)),
                "role": str(item.get("role") or "人物"),
                "description": description,
                "appearance": str(item.get("appearance") or ""),
                "wardrobe": str(item.get("wardrobe") or ""),
                "props": str(item.get("props") or ""),
                "gaze": str(item.get("gaze") or ""),
            })
        if not cast and people:
            cast = [{"key": "A", "role": "主角", "description": people}]
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
            "background": str(view.get("background") or ""),
            "lighting": str(view.get("lighting") or ""),
            "action": str(view.get("action") or ""),
            "expression": str(view.get("expression") or ""),
            "tone": str(view.get("tone") or ""),
            "pace_cps": _pace_cps(beat.get("dialogue_rows") or []),
            "people": people,
            "cast": cast,
            "description": str(view.get("description") or ""),
            "product": {
                "name": product_name,
                "appearance": str(view.get("product_appearance") or ""),
                "position": str(view.get("product_position") or ""),
            },
            "dialogue": list(beat.get("dialogue") or []),
            "dialogue_rows": list(beat.get("dialogue_rows") or []),
            "dialogue_source": str(beat.get("dialogue_source") or ""),
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
        "pace_cps": _pace_cps([row for beat in beats for row in beat.get("dialogue_rows") or []]),
        "global": {
            "preserve": ["镜头", "景别", "运镜", "场景", "动作", "构图", "节奏", "转场", "原声"],
            "replace": replace,
            "warnings": [] if visual else ["视觉标签不可用，拆解为启发式结果"],
        },
    }


def _cast_roster(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per person across the whole reference, not per shot.

    The UI and the confirmation step read this to describe who is on screen;
    per-shot rows stay in `remake_plan.shots[].cast` for the prompt renderers.
    """
    rows: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for shot in shots:
        for item in shot.get("cast") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("role") or "A")
            entry = rows.get(key)
            if entry is None:
                entry = {
                    "key": key,
                    "role": str(item.get("role") or "人物"),
                    "appearance": "",
                    "wardrobe": "",
                    "props": "",
                    "gaze": "",
                    "description": "",
                    "shots": [],
                }
                rows[key] = entry
                order.append(key)
            for field in ("appearance", "wardrobe", "props", "gaze"):
                if item.get(field) and not entry.get(field):
                    entry[field] = str(item[field])
            if item.get("description") and not entry.get("description"):
                entry["description"] = str(item["description"])
            shot_id = str(shot.get("id") or "")
            if shot_id and shot_id not in entry["shots"]:
                entry["shots"].append(shot_id)
    return [rows[key] for key in order]


def _scene_roster(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Distinct backgrounds with the shots they cover."""
    groups: list[dict[str, Any]] = []
    for shot in shots:
        text = str(shot.get("background") or shot.get("scene") or "").strip()
        if not text:
            continue
        entry = next((item for item in groups if item["text"] == text), None)
        if entry is None:
            entry = {
                "text": text,
                "scene": str(shot.get("scene") or ""),
                "lighting": str(shot.get("lighting") or ""),
                "shots": [],
            }
            groups.append(entry)
        elif shot.get("lighting") and not entry.get("lighting"):
            entry["lighting"] = str(shot["lighting"])
        shot_id = str(shot.get("id") or "")
        if shot_id and shot_id not in entry["shots"]:
            entry["shots"].append(shot_id)
    return groups


def _vision_max_frames() -> int:
    try:
        maximum = int(os.environ.get("ADSTUDIO_VISION_MAX_FRAMES", "14"))
    except (TypeError, ValueError):
        maximum = 14
    return max(4, min(18, maximum))


def _vision_budget(duration: float) -> int:
    """Initial frames worth spending: roughly one every 2.5s, with a floor/ceiling."""
    try:
        minimum = int(os.environ.get("ADSTUDIO_VISION_MIN_FRAMES", "4"))
    except (TypeError, ValueError):
        minimum = 4
    maximum = _vision_max_frames()
    target = int(math.ceil(max(0.1, float(duration)) / 2.5)) + 1
    return max(minimum, min(maximum, target))


def _frame_times_for(start: float, end: float, count: int, peaks: list[float]) -> list[tuple[float, str]]:
    """First frame, last frame, then motion peaks, then even fill.

    First/last pin the action interval; peaks spend the remaining budget where
    something actually changed instead of at arbitrary midpoints.
    """
    span = max(0.0, float(end) - float(start))
    if count <= 1 or span <= 0.4:
        return [(round(float(start) + span / 2, 3), "mid")]
    head = min(0.3, span * 0.1)
    picks: list[tuple[float, str]] = [
        (round(float(start) + head, 3), "first"),
        (round(float(end) - head, 3), "last"),
    ]
    interior = count - 2
    if interior > 0:
        inside = sorted(value for value in peaks if float(start) + 0.15 < value < float(end) - 0.15)
        step = span / (interior + 1)
        for index in range(interior):
            target = float(start) + step * (index + 1)
            if inside:
                pick = min(inside, key=lambda value: abs(value - target))
                inside.remove(pick)
                picks.append((round(pick, 3), "peak"))
            else:
                picks.append((round(target, 3), "mid"))
    picks.sort()
    unique: list[tuple[float, str]] = []
    for time_s, role in picks:
        if unique and abs(time_s - unique[-1][0]) < 0.15:
            continue
        unique.append((time_s, role))
    return unique


def _plan_analysis_frames(
    run_id: str,
    source: Path,
    beats: list[dict[str, Any]],
    duration: float,
    *,
    max_frames: int | None = None,
    events: list[dict[str, Any]] | None = None,
    stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Budget frames across beats, then dedupe near-identical stills."""
    if not beats:
        return []
    budget = max(1, int(max_frames or _vision_budget(duration)))
    peaks = [float(event.get("t") or 0) for event in (events or []) if str(event.get("kind")) == "motion"]
    counts = [1 for _ in beats]
    remaining = max(0, budget - len(beats))
    order = sorted(
        range(len(beats)),
        key=lambda index: -(float(beats[index]["end_s"]) - float(beats[index]["start_s"])),
    )
    while remaining > 0:
        progressed = False
        for index in order:
            if remaining <= 0:
                break
            if counts[index] >= 4:
                continue
            counts[index] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break
    frames: list[dict[str, Any]] = []
    hashes: list[int] = []
    deduped = 0
    for beat, count in zip(beats, counts):
        start, end = float(beat["start_s"]), float(beat["end_s"])
        for frame_index, (time_s, role) in enumerate(_frame_times_for(start, end, count, peaks)):
            frame_id = f"{beat['id']}_f{frame_index}"
            thumb = store.run_artifact(run_id, f"storyboard/analysis_{frame_id}.jpg")
            try:
                ffmpeg.extract_frame(source, time_s, thumb, width=360)
            except Exception:
                continue
            hashed = similarity.dhash(thumb)
            if hashed is not None and hashes:
                closest = max((similarity.similarity(hashed, other) or 0.0) for other in hashes)
                if closest >= 0.97:
                    thumb.unlink(missing_ok=True)
                    deduped += 1
                    continue
            if hashed is not None:
                hashes.append(hashed)
            frames.append({
                "id": frame_id,
                "beat_id": beat["id"],
                "start_s": start,
                "end_s": end,
                "time_s": time_s,
                "role": role,
                "path": thumb,
            })
    if stats is not None:
        stats["budget"] = budget
        stats["planned"] = sum(counts)
        stats["used"] = len(frames)
        stats["deduped"] = deduped
    return frames


def _merge_cast(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge per-frame cast rows by key, best frame first.

    The vision pass labels each keyframe separately, so the same person arrives
    several times with different fields filled in. Keeping the first non-empty
    value per field gives one complete row per person without letting a later
    frame overwrite a better description.
    """
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for group in groups:
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or "A").strip().upper() or "A"
            if key not in merged:
                merged[key] = dict(entry)
                merged[key]["key"] = key
                order.append(key)
                continue
            for field, value in entry.items():
                if field in {"key", "description"}:
                    continue
                if value and not merged[key].get(field):
                    merged[key][field] = value
    rows: list[dict[str, Any]] = []
    for key in order:
        row = merged[key]
        row["description"] = vision.cast_description(row)
        if row["description"]:
            rows.append(row)
    return rows


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
        "shot_size", "camera_angle", "camera_movement", "action", "expression", "tone", "product",
        "product_appearance", "product_position", "product_visibility", "scene", "background",
        "lighting", "composition", "on_screen_text", "continuity",
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
        merged["cast"] = _merge_cast([list(item.get("cast") or []) for item in [best, *items]])
        merged["confidence"] = max((float(item.get("confidence") or 0.0) for item in items), default=0.0) or None
        merged["unclear"] = sorted({str(value) for item in items for value in (item.get("unclear") or []) if str(value).strip()})
        merged["frame_ids"] = [str(frame.get("id")) for frame in frames if str(frame.get("beat_id")) == str(beat.get("id")) and visual_frames.get(str(frame.get("id")))]
        aggregated[str(beat.get("id"))] = merged
    return aggregated

def _from_cache(run: Any, root: Path, ref_id: str | None, cached: dict[str, Any]) -> dict[str, Any] | None:
    """Rebuild a skeleton from cached reference facts for a new run."""
    source = dict(cached.get("source") or {})
    beats = copy.deepcopy(cached.get("beats") or [])
    if not source or not beats or not ref_id:
        return None
    try:
        source["path"] = str(store.asset_media_path(ref_id))
    except FileNotFoundError:
        return None
    source["asset_id"] = ref_id
    for beat in beats:
        thumb = store.run_artifact(run.id, f"storyboard/{beat['id']}.jpg")
        try:
            ffmpeg.extract_frame(source["path"], (float(beat["start_s"]) + float(beat["end_s"])) / 2, thumb, width=360)
            beat["thumbnail"] = store.rel_to_data(thumb)
        except Exception:
            beat["thumbnail"] = None
    visual = {"cached": True} if (cached.get("analysis") or {}).get("mode") == "frames" else {}
    plan = _remake_plan(run, beats, source, visual)
    plan["source"]["cuts_s"] = list(cached.get("cuts_s") or [])
    analysis = dict(cached.get("analysis") or {})
    analysis["cached"] = True
    skeleton = {
        "version": 3,
        "partial": False,
        "source": source,
        "analysis": analysis,
        "remake_plan": plan,
        "cuts_s": list(cached.get("cuts_s") or []),
        "cut_events": list(cached.get("cut_events") or []),
        "beats": beats,
        "transcript": list(cached.get("transcript") or []),
        "confidence": dict(cached.get("confidence") or {}),
        "notes": list(cached.get("notes") or []) + ["Cached reference analysis."],
    }
    store.atomic_write_json(root / "artifacts" / "skeleton.json", skeleton)
    return skeleton


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
    cache_key = ""
    if ref_id:
        cache_key = analysis_cache.key(
            str(ref_id),
            asr_available=asr.available(),
            vision_available=vision.available(),
            vision=vision.chain_signature(),
        )
        cached = analysis_cache.load(cache_key)
        if cached:
            restored = _from_cache(run, root, str(ref_id), cached)
            if restored is not None:
                return restored
    events: list[dict[str, Any]] = []
    if source:
        try:
            events = ffmpeg.detect_events(source, duration)
        except Exception:
            events = []
    cuts = [float(event["t"]) for event in events if str(event.get("kind")) == "cut"]
    transcript: list[dict[str, Any]] = []
    asr_source = "no_reference"
    asr_error = ""
    prompt_hint = ""
    if source:
        if not facts.get("has_audio"):
            asr_source = "silent"
            asr_error = "参考片没有音轨"
        elif asr.disabled():
            asr_source = "disabled"
            asr_error = "ADSTUDIO_ASR=0"
        elif not asr.available():
            asr_source = "not_installed"
            asr_error = "未安装 faster-whisper"
        else:
            try:
                # Product names from the brief bias the decoder towards the right
                # homophones (e.g. 冬天 vs 通天) without changing the audio.
                try:
                    from .. import requirements as requirements_mod

                    req = requirements_mod.derive(str((run.inputs or {}).get("brief") or ""), run.advanced or {})
                    product = str(req.get("product_hint") or "").strip()
                    if product:
                        prompt_hint = f"以下台词来自一条带货视频，商品名称是{product}。"
                except Exception:
                    prompt_hint = ""
                transcript = asr.transcribe(source, prompt_hint=prompt_hint)
                refine = getattr(asr, "refine", None)
                if transcript and callable(refine):
                    selected_text_model = (run.advanced or {}).get("text_model")
                    transcript = refine(
                        transcript,
                        hint=prompt_hint,
                        text_model=selected_text_model if isinstance(selected_text_model, dict) else None,
                    )
            except Exception as exc:  # noqa: BLE001
                transcript = []
                asr_error = f"{type(exc).__name__}: {exc}"[:240]
            if transcript:
                asr_source = "asr"
            else:
                asr_source = "failed"
                asr_error = asr_error or str(getattr(asr, "LAST_ERROR", "") or "没有识别到台词")
    beats = _beats(duration, cuts, transcript=transcript)
    if transcript:
        _assign_transcript(beats, transcript)
        _snap_beats(beats)
    else:
        for beat in beats:
            beat["dialogue"] = []
            beat["dialogue_rows"] = []
    for beat in beats:
        beat["dialogue_source"] = asr_source
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
    frame_stats: dict[str, int] = {}
    vision_budget = _vision_budget(duration) if vision.available() else 0
    vision_max_frames = _vision_max_frames() if vision.available() else 0
    if source and vision.available():
        analysis_frames = _plan_analysis_frames(
            run_id, source, beats, duration, max_frames=vision_budget, events=events, stats=frame_stats
        )
        if analysis_frames:
            vision.reset_attempts()
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
                        "role": "refine",
                        "path": thumb,
                    })
                if extra_frames:
                    # Re-send the previous batch's last frame as a continuity
                    # anchor so "compared to the previous frame" still means
                    # something across two requests. It is not aggregated.
                    anchor = None
                    if analysis_frames:
                        last = analysis_frames[-1]
                        anchor = {**last, "id": f"{last['id']}_ctx", "context": True}
                    batch = ([anchor] if anchor else []) + extra_frames
                    extra_visual = vision.analyze_frames(batch, max_frames=len(batch))
                    if extra_visual:
                        if anchor:
                            extra_visual.pop(str(anchor["id"]), None)
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
                    "product_appearance": item.get("product_appearance") or "",
                    "product_position": item.get("product_position") or "",
                    "people": item.get("people") or "",
                    "cast": list(item.get("cast") or []),
                    "scene": item.get("scene") or "",
                    "background": item.get("background") or "",
                    "lighting": item.get("lighting") or "",
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
    provider = str(getattr(vision, "LAST_PROVIDER", "") or "")
    model = str(getattr(vision, "LAST_MODEL", "") or "")
    # Second pass: one flowing description per shot. The per-frame tags are facts
    # a renderer can only concatenate; a short paragraph is what a prompt needs.
    # Appearance stays out of it on purpose: the cast fields already carry it and
    # a replaced person must not inherit the reference look.
    describe_meta: dict[str, Any] = {"shots": 0, "provider": "", "model": "", "error": ""}
    if visual and analysis_frames:
        describe_beats = [
            {
                "id": beat.get("id"),
                "start_s": beat.get("start_s"),
                "end_s": beat.get("end_s"),
                "dialogue_text": " ".join(
                    str(row.get("text") or "") for row in (beat.get("dialogue_rows") or [])
                ),
            }
            for beat in beats
        ]
        try:
            described = vision.describe_beats(analysis_frames, describe_beats)
        except Exception as exc:  # noqa: BLE001
            described = {}
            describe_meta["error"] = f"{type(exc).__name__}: {exc}"[:200]
        for beat in beats:
            text = str(described.get(str(beat.get("id"))) or "").strip()
            if text:
                beat.setdefault("visual", {})["description"] = text
        describe_meta.update({
            "shots": sum(1 for beat in beats if str((beat.get("visual") or {}).get("description") or "").strip()),
            "provider": str(getattr(vision, "LAST_PROVIDER", "") or ""),
            "model": str(getattr(vision, "LAST_MODEL", "") or ""),
        })
        if not describe_meta["shots"] and not describe_meta["error"]:
            describe_meta["error"] = str(getattr(vision, "LAST_ERROR", "") or "")[:200]
    plan = _remake_plan(run, beats, facts, visual)
    plan["source"]["cuts_s"] = cuts
    warnings = []
    attempts = [item for item in (getattr(vision, "LAST_ATTEMPTS", []) or []) if isinstance(item, dict)]
    if visual and provider == "dsh":
        warnings.append(f"视觉标签由 DSH 文本模型 {model or 'auto'} 生成")
    if visual and attempts:
        # A bisected batch can still deliver most labels; say how many were lost
        # instead of pretending the pass was clean.
        lost = [item for item in attempts if str(item.get("status")) in {"failed", "skipped"}]
        if lost:
            missing = sum(int(item.get("frames") or 0) for item in lost)
            first_error = str((lost[0].get("error") or "")).strip()
            warnings.append(
                f"视觉标签部分缺失：{missing} 帧未标注" + (f"（{first_error}）" if first_error else "")
            )
    if visual and not describe_meta["shots"]:
        warnings.append("镜头描述未生成，提示词退回字段拼接" + (f"：{describe_meta['error']}" if describe_meta.get("error") else ""))
    if not visual:
        warnings.append("视觉标签不可用，拆解为启发式结果")
        if vision_error:
            warnings.append(vision_error)
    escalated = int(getattr(vision, "LAST_ESCALATED", 0) or 0)
    if escalated:
        warnings.append(f"商品/画面文字由 Doubao pro 复核 {escalated} 帧")
    asr_note = str(getattr(asr, "LAST_NOTE", "") or "") if asr_source == "asr" else ""
    if asr_note:
        warnings.append(f"ASR：{asr_note}")
    # A failed homophone cleanup leaves visibly wrong characters in the
    # storyboard, so it has to be reported instead of silently falling back.
    asr_cleanup_error = ""
    if asr_source == "asr" and not asr_note:
        probe = str(getattr(asr, "LAST_ERROR", "") or "").strip()
        if probe.startswith("cleanup"):
            asr_cleanup_error = probe
            warnings.append(f"同音字校对未生效：{probe}")
    asr_warning = {
        "silent": "参考片没有音轨，无法转写台词",
        "disabled": "ASR 已关闭（ADSTUDIO_ASR=0），分镜没有台词",
        "not_installed": "ASR 未安装，参考片只做画面分析；分镜台词为空",
        "failed": f"ASR 转写失败：{asr_error}",
    }.get(asr_source)
    if asr_warning:
        warnings.append(asr_warning)
    analysis = {
        "mode": "frames" if visual else "heuristic",
        "provider": provider if visual else "",
        "model": model if visual else "",
        "degraded": not bool(visual),
        "reason": "" if visual else ("视觉标签不可用，拆解为启发式结果" + (f"：{vision_error}" if vision_error else "")),
        "warnings": warnings,
        "cast_roster": _cast_roster(plan.get("shots") or []),
        "scenes": _scene_roster(plan.get("shots") or []),
        "describe": describe_meta,
        "asr": {
            "source": asr_source,
            "model": str(getattr(asr, "LAST_MODEL", "") or "") if asr_source == "asr" else "",
            "error": asr_error or asr_cleanup_error,
            "lines": len(transcript),
            "note": asr_note,
            "cleanup": "ok" if asr_note else ("failed" if asr_cleanup_error else "skipped"),
        },
        "frame_count": len(analysis_frames),
        "initial_frame_budget": vision_budget,
        "vision_budget": vision_max_frames,
        "refine_rounds": refine_rounds,
        "frames": {
            "budget": frame_stats.get("budget", vision_budget),
            "planned": frame_stats.get("planned", 0),
            "used": len(analysis_frames),
            "deduped": frame_stats.get("deduped", 0),
        },
        "cuts": {"cut": len(cuts), "motion": max(0, len(events) - len(cuts))},
        "escalated_frames": int(getattr(vision, "LAST_ESCALATED", 0) or 0),
        "vision_attempts": attempts,
    }
    skeleton = {
        "version": 3,
        "partial": False,
        "source": {**facts, "asset_id": ref_id},
        "analysis": analysis,
        "remake_plan": plan,
        "cuts_s": cuts,
        "cut_events": events,
        "beats": beats,
        "transcript": transcript,
        "confidence": {"asr": 0.85 if transcript else 0.0, "vision": (0.68 if provider == "dsh" else 0.75) if visual else 0.0, "speakers": 0.0, "structure": 0.6 if visual else 0.3},
        "notes": [
            (
                "ASR transcript attached." if transcript
                else f"No transcript ({asr_source})" + (f": {asr_error}" if asr_error else "")
            ),
            (
                f"Doubao vision tags attached to keyframes ({model})." if provider == "ark"
                else ("Vision tags attached to keyframes." if provider == "minimax" else f"DSH vision tags attached to keyframes ({model}).")
            ) if visual else ("Vision unavailable or disabled." if not vision.available() else "Vision returned no usable tags."),
        ],
    }
    path = root / "artifacts" / "skeleton.json"
    store.atomic_write_json(path, skeleton)
    # Never cache a transient failure: a retry must be able to succeed, and a
    # cached "ASR failed" entry would outlive the network problem that caused it.
    cacheable = asr_source != "failed" and not (vision.available() and not visual)
    if cache_key and cacheable:
        analysis_cache.save(cache_key, {
            "source": {k: value for k, value in skeleton["source"].items() if k != "asset_id"},
            "analysis": analysis,
            "cuts_s": cuts,
            "cut_events": events,
            "beats": beats,
            "transcript": transcript,
            "confidence": skeleton["confidence"],
            "notes": skeleton["notes"],
        })
    return skeleton
