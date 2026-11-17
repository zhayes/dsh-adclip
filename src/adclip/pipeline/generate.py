"""Generation: capability-driven model choice plus the real provider adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import catalog, params, store
from ..media import ffmpeg
from ..providers.ark import ArkProvider
from ..providers.kling import KlingProvider
from ..providers.minimax import MiniMaxProvider
from . import persona as persona_mod

PROVIDERS = {"ark": ArkProvider, "kling": KlingProvider, "minimax": MiniMaxProvider}


def _adapter(model_id: str) -> Any | None:
    """Adapter instance for a catalogue row, or None for the test-only model."""
    row = catalog.get(model_id) or {}
    provider = str(row.get("provider") or "")
    if provider == "synthetic":
        return None
    factory = PROVIDERS.get(provider)
    if factory is None:
        raise RuntimeError(f"模型 {model_id} 没有可用的适配器（provider={provider or 'unknown'}）")
    return factory()


def resolve_model(run: Any) -> str:
    """The model id this run should use: explicit when valid, else capability-first."""
    requested = str((run.advanced or {}).get("model") or "auto")
    if requested not in {"", "auto"}:
        model = catalog.get(requested)
        if model is None:
            raise RuntimeError(f"unknown model: {requested}")
        if model.get("enabled") is False:
            raise RuntimeError(f"模型 {requested} 未启用")
        if not model.get("available"):
            raise RuntimeError(f"模型 {requested} 不可用：{model.get('reason')}")
        return requested
    needs_dialogue = run.scenario == "viral-remake"
    rows = catalog.with_capability("text_to_video", kind="video", usable=True)
    if not rows:
        raise RuntimeError("没有可用的视频模型：请在设置里配置对应厂商的 key")
    order = {row["id"]: index for index, row in enumerate(catalog.rows())}

    def rank(row: dict[str, Any]) -> tuple[int, int, int]:
        # Real providers first, dialogue-capable models first when the scenario
        # speaks, then catalogue order so the choice is deterministic.
        return (
            1 if row.get("provider") == "synthetic" else 0,
            0 if (not needs_dialogue or row.get("native_audio")) else 1,
            order.get(row["id"], 999),
        )

    return sorted(rows, key=rank)[0]["id"]


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
    prompt = _segment_prompt(run, script, seg)
    provider = _adapter(model)
    if provider is None:
        ffmpeg.make_synthetic_clip(source, output, duration=seg_len, width=width, height=height, fps=int(advanced.get("fps") or 30))
        return {"model": model, "path": str(output), "demo": True, "duration_s": seg_len}
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
    result_path = store.run_artifact(run_id, "provider_raw.mp4")
    provider = _adapter(model)
    if provider is None:
        # Test-only synthetic model: a local clip so the pipeline stays runnable
        # without any provider key.
        ffmpeg.make_synthetic_clip(source, result_path, duration=duration, width=width, height=height, fps=int(advanced.get("fps") or 30))
        return {"model": model, "path": str(result_path), "demo": True, "duration_s": duration}
    script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    prompt = _script_prompt(run, script)
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
