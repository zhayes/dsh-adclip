"""Generation: demo fallback plus the real Ark Seedance adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import params, store
from ..media import ffmpeg
from ..media import stitch as stitch_mod
from ..providers.ark import ArkProvider
from ..providers.kling import KlingProvider
from ..providers.minimax import MiniMaxProvider
from . import persona as persona_mod


def resolve_model(run: Any) -> str:
    requested = str((run.advanced or {}).get("model") or "auto")
    if requested not in {"", "auto"}:
        model = params.get_model(requested)
        if model is None:
            raise RuntimeError(f"unknown model: {requested}")
        if model.get("enabled") is False:
            raise RuntimeError(f"模型 {requested} 未启用")
        if not model.get("available"):
            raise RuntimeError(f"模型 {requested} 不可用：{model.get('reason')}")
        return requested
    needs_dialogue = run.scenario == "viral-remake"
    for candidate in ("ark.seedance-2.5", "ark.seedance-2.0", "ark.seedance-2.0-fast", "ark.seedance-2.0-mini", "kling.v3", "minimax.h3", "minimax.hailuo-2.3-fast"):
        model = params.get_model(candidate)
        if not model or not model.get("available") or model.get("enabled") is False:
            continue
        if "text_to_video" not in (model.get("modes") or []):
            continue
        if needs_dialogue and not model.get("native_audio"):
            continue
        return candidate
    return "demo"


def _cast_text(advanced: dict[str, Any]) -> str:
    persona = (advanced.get("persona") or {}) if isinstance(advanced.get("persona"), dict) else {}
    if not persona:
        return ""
    gender = {"male": "男性", "female": "女性", "any": "人物"}.get(persona.get("gender") or "any")
    age = {"teenager": "18–24 岁", "youth": "25–34 岁", "middle_aged": "35–54 岁", "senior": "55 岁以上"}.get(persona.get("age") or "youth")
    body = {"slim": "偏瘦", "standard": "标准", "athletic": "健硕", "chubby": "微胖"}.get(persona.get("body_type") or "standard")
    return f"{age}{gender}，{body}体型"


def _segment_prompt(run: Any, script: dict[str, Any], seg: dict[str, Any]) -> str:
    advanced = params.merged_advanced(run.advanced)
    brief = str((run.inputs or {}).get("brief") or "").strip()
    rows = script.get("beats") or []
    index = int(seg.get("index") or 0)
    beat = rows[index] if 0 <= index < len(rows) else {}
    lines = "；".join(str(x.get("text") or "") for x in (beat.get("lines") or []) if str(x.get("text") or "").strip())
    shot = str(seg.get("action") or beat.get("shot") or "").strip()
    cast = _cast_text(advanced)
    duration = max(0.5, float(seg.get("end_s") or 0) - float(seg.get("start_s") or 0))
    parts = [
        f"竖屏 {advanced.get('aspect', '9:16')}，约 {duration:.1f} 秒，单个镜头，画面干净，自然光。",
        f"人物：{cast}。" if cast else "",
        persona_mod.persona_instruction(advanced),
        f"场景/动作：{persona_mod.neutralize_people(shot, advanced)}。" if shot else "",
        f"中文同期对白（只念以下句子，不要念画面描述或制作要求；按顺序说）：{lines}。" if lines else "",
    ]
    if not lines and brief:
        parts.append(f"画面/产品：{brief[:300]}")
    parts.append("要求：口型与台词同步；不要出现字幕、水印、logo；商品标签留白；不要念出这段说明。")
    return "".join(part for part in parts if part).strip()[:1400]


def _script_prompt(run: Any, script: dict[str, Any]) -> str:
    advanced = params.merged_advanced(run.advanced)
    brief = str((run.inputs or {}).get("brief") or "").strip()
    lines = []
    actions = []
    for beat in script.get("beats") or []:
        spoken = " / ".join(str(x.get("text") or "") for x in beat.get("lines") or [])
        if spoken:
            lines.append(spoken)
        if beat.get("shot"):
            actions.append(str(beat["shot"]))
    cast = _cast_text(advanced)
    is_dialogue = run.scenario == "viral-remake"
    parts = [
        f"竖屏 {advanced.get('aspect', '9:16')}，约 {advanced.get('duration', 12)} 秒，一镜到底，画面干净，自然光。",
        f"人物：{cast}。" if cast else "",
        persona_mod.persona_instruction(advanced),
        f"场景/动作：{'；'.join(persona_mod.neutralize_people(x, advanced) for x in actions[:4])}。" if actions else "",
    ]
    if is_dialogue and lines:
        parts.append(
            "中文同期对白（只念以下句子，不要念画面描述、产品说明或制作要求；两个不同声部，按顺序说）："
            + "；".join(lines[:6]) + "。"
        )
    elif brief:
        parts.append(f"画面/产品：{brief[:500]}")
    parts.append("要求：口型与台词同步；画面不要出现字幕、水印、logo；商品标签留白；不要把这段说明念出来。")
    return "".join(part for part in parts if part).strip()[:1800]


def _reference_images(run: Any) -> list[Path]:
    paths: list[Path] = []
    inputs = run.inputs or {}
    for asset_id in list(inputs.get("product_asset_ids") or [])[:3]:
        try:
            paths.append(store.asset_media_path(str(asset_id)))
        except Exception:
            continue
    ref = inputs.get("reference_image_asset_id")
    if ref:
        try:
            paths.append(store.asset_media_path(str(ref)))
        except Exception:
            pass
    return paths


def generate_segment(run: Any, seg: dict[str, Any], output: Path) -> dict[str, Any]:
    """Generate only one storyboard segment (used by true shot replacement)."""
    model = resolve_model(run)
    advanced = params.merged_advanced(run.advanced)
    width, height = params.size_for(str(advanced.get("aspect") or "9:16"), str(advanced.get("resolution") or "720p"))
    seg_len = max(0.5, float(seg.get("end_s") or 0) - float(seg.get("start_s") or 0))
    script = store.read_json(store.run_dir(run.id) / "artifacts" / "script.json", {}) or {}
    ref_id = (run.inputs or {}).get("reference_asset_id")
    source = store.asset_media_path(ref_id) if ref_id else None
    if model == "demo":
        ffmpeg.make_demo_clip(source, output, duration=seg_len, width=width, height=height, fps=int(advanced.get("fps") or 30))
        return {"model": "demo", "path": str(output), "demo": True, "duration_s": seg_len}
    prompt = _segment_prompt(run, script, seg)
    if model.startswith("kling."):
        provider = KlingProvider()
    elif model.startswith("minimax."):
        provider = MiniMaxProvider()
    else:
        provider = ArkProvider()
    allowed = list((params.get_model(model) or {}).get("durations") or [4, 5, 6, 10])
    target = int(seg_len + 0.999)
    gen_duration = next((d for d in sorted(allowed) if d >= target), max(allowed))
    provider.generate(
        prompt,
        images=_reference_images(run),
        duration=int(gen_duration),
        resolution=str(advanced.get("resolution") or "720p"),
        aspect=str(advanced.get("aspect") or "9:16"),
        model=model,
        output=output,
    )
    return {"model": model, "path": str(output), "demo": False, "duration_s": seg_len}


def generate(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    model = resolve_model(run)
    advanced = params.merged_advanced(run.advanced)
    duration = max(1.0, float(advanced.get("duration") or 12))
    width, height = params.size_for(str(advanced.get("aspect") or "9:16"), str(advanced.get("resolution") or "720p"))
    ref_id = (run.inputs or {}).get("reference_asset_id")
    source = store.asset_media_path(ref_id) if ref_id else None
    out = store.run_artifact(run_id, "demo_raw.mp4")

    if model != "demo":
        script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
        prompt = _script_prompt(run, script)
        if model.startswith("kling."):
            provider = KlingProvider()
        elif model.startswith("minimax."):
            provider = MiniMaxProvider()
        else:
            provider = ArkProvider()
        result_path = store.run_artifact(run_id, "provider_raw.mp4")
        provider.generate(
            prompt,
            images=_reference_images(run),
            duration=int(duration),
            resolution=str(advanced.get("resolution") or "720p"),
            aspect=str(advanced.get("aspect") or "9:16"),
            model=model,
            output=result_path,
        )
        return {"model": model, "path": str(result_path), "demo": False, "duration_s": duration}

    mode = str(advanced.get("generation_mode") or "fast")
    if mode == "fine" and duration > 8:
        half = duration / 2
        a = store.run_artifact(run_id, "demo_part0.mp4")
        b = store.run_artifact(run_id, "demo_part1.mp4")
        ffmpeg.make_demo_clip(source, a, duration=half, width=width, height=height, fps=int(advanced.get("fps") or 30))
        ffmpeg.make_demo_clip(source, b, duration=half, width=width, height=height, fps=int(advanced.get("fps") or 30))
        plan_data = stitch_mod.plan(
            [{"path": str(a), "in_s": 0, "out_s": half}, {"path": str(b), "in_s": 0, "out_s": half}],
            width=width, height=height, fit="black_pad", transition="cut", audio="keep",
        )
        stitch_mod.execute(plan_data, out)
    else:
        ffmpeg.make_demo_clip(source, out, duration=duration, width=width, height=height, fps=int(advanced.get("fps") or 30))
    return {"model": "demo", "path": str(out), "demo": True, "duration_s": duration}
