"""Generation: capability-driven model choice plus the real provider adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import catalog, params, remake_policy, store
from ..media import ffmpeg
from . import persona as persona_mod
from . import remake_spec
from ..providers.ark import ArkProvider
from ..providers.kling import KlingProvider
from ..providers.minimax import MiniMaxProvider

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
    selection = getattr(run, "selection", None) or {}
    if selection.get("mode") in {
        "h3_reference", "reference", "keyframe", "generation",
        # legacy selections written before the rung rename
        "reference_fallback", "generation_fallback",
    } and selection.get("model"):
        return str(selection["model"])
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
        f"{remake_spec.orientation(str(advanced.get('aspect') or '9:16'))} {advanced.get('aspect', '9:16')}，约 {duration:.1f} 秒，单个镜头，画面干净，自然光。",
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
        f"{remake_spec.orientation(str(advanced.get('aspect') or '9:16'))} {advanced.get('aspect', '9:16')}，约 {advanced.get('duration', 12)} 秒，一镜到底，画面干净，自然光。",
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


def _product_images(run: Any) -> list[Path]:
    paths: list[Path] = []
    for asset_id in list((run.inputs or {}).get("product_asset_ids") or [])[:3]:
        try:
            paths.append(store.asset_media_path(str(asset_id)))
        except Exception:
            continue
    ref = (run.inputs or {}).get("reference_image_asset_id")
    if ref:
        try:
            paths.append(store.asset_media_path(str(ref)))
        except Exception:
            pass
    return paths


def _persona_images(run: Any) -> list[Path]:
    paths: list[Path] = []
    advanced = run.advanced or {}
    persona = advanced.get("persona") if isinstance(advanced.get("persona"), dict) else {}
    ids = set()
    for value in (advanced.get("persona_map") or {}).values():
        if str(value).strip():
            ids.add(str(value))
    for value in (persona.get("reference_images") or []):
        if str(value).strip():
            ids.add(str(value))
    for value in list(ids)[:6]:
        try:
            record = store.get_persona(value)
            if record:
                for image in (record.get("reference_images") or [])[:3]:
                    try:
                        paths.append(store.asset_media_path(str(image)))
                    except Exception:
                        continue
            else:
                paths.append(store.asset_media_path(value))
        except Exception:
            continue
    return paths[:3]


def _keyframe_image(run: Any, skeleton: dict[str, Any], run_id: str) -> Path | None:
    """First frame of the first shot, used by the keyframe rung."""
    ref_id = (run.inputs or {}).get("reference_asset_id")
    if not ref_id:
        return None
    shots = (skeleton.get("remake_plan") or {}).get("shots") or []
    start = float((shots[0] or {}).get("start_s") or 0) if shots else 0.0
    target = store.run_artifact(run_id, "keyframe.jpg")
    try:
        source = store.asset_media_path(str(ref_id))
        ffmpeg.extract_frame(source, max(0.0, start + 0.05), target, width=720)
    except Exception:
        return None
    return target


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


def generate_h3_reference(run_id: str) -> dict[str, Any]:
    """Run MiniMax H3 with the reference video and replacement images."""
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    advanced = params.merged_advanced(run.advanced)
    selection = getattr(run, "selection", None) or {}
    ref_id = (run.inputs or {}).get("reference_asset_id")
    if not ref_id:
        raise RuntimeError("H3 参考复刻需要参考视频")
    source = store.asset_media_path(str(ref_id))
    facts = ffmpeg.probe(source)
    duration = float(facts.get("duration_s") or 0)
    if duration < 4 or duration > 15:
        raise RuntimeError("H3 参考复刻仅支持 4–15 秒参考片")
    if Path(source).stat().st_size > 50 * 1024 * 1024:
        raise RuntimeError("参考片超过 MiniMax 50MB 上限")
    products = _product_images(run)
    personas = _persona_images(run)
    from . import remake as remake_mod
    script_doc = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    audio_mode = str(advanced.get("audio_mode") or "regenerate")
    warnings: list[str] = []
    if audio_mode == "regenerate" and not remake_mod._spoken_lines(script_doc):
        audio_mode = "preserve"
        warnings.append("脚本没有可用台词，H3 自动保留原声")
    reference_for_h3 = Path(source)
    audio_source = "reference" if audio_mode == "preserve" else "h3"
    if audio_mode == "regenerate":
        try:
            reference_for_h3 = ffmpeg.strip_audio(source, store.run_artifact(run_id, "reference_silent.mp4"))
        except Exception as exc:  # noqa: BLE001
            audio_mode = "preserve"
            audio_source = "reference"
            reference_for_h3 = Path(source)
            warnings.append(f"参考片静音失败，改用保留原声：{type(exc).__name__}: {exc}"[:240])
    if audio_mode == "preserve" and not facts.get("has_audio"):
        audio_source = "h3"
        warnings.append("参考片没有音轨，保留原声不可用，改用 H3 生成音频")
    prompt = remake_mod.build_h3_replace_prompt(
        run,
        store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {},
        product_count=len(products),
        person_count=len(personas),
        script_doc=script_doc,
        audio_mode=audio_mode,
    )
    target_duration = int(round(duration))
    target_duration = max(4, min(15, target_duration))
    resolution = str((selection.get("params") or {}).get("resolution") or advanced.get("resolution") or "768P")
    output = store.run_artifact(run_id, "provider_raw.mp4")
    provider = _adapter("minimax.h3")
    if provider is None:
        raise RuntimeError("MiniMax H3 适配器不可用")
    provider.generate(
        prompt,
        images=(products + personas)[:9],
        reference_video=Path(reference_for_h3),
        duration=target_duration,
        resolution=resolution,
        aspect=str(facts.get("aspect") or advanced.get("aspect") or "9:16"),
        model="minimax.h3",
        output=output,
    )
    return {
        "model": "minimax.h3",
        "path": str(output),
        "demo": False,
        "duration_s": duration,
        "audio_mode": audio_mode,
        "audio_source": audio_source,
        "warnings": warnings,
    }


def _provider_fatal(message: str) -> bool:
    text = str(message or "").lower()
    return any(token in text for token in ("insufficient balance", "余额", "quota", "unauthorized", "invalid api key", "401", "402", "403", "429", "rate limit"))


def _video_candidates(run: Any) -> list[dict[str, Any]]:
    selection = getattr(run, "selection", None) or {}
    requested = str((run.advanced or {}).get("model") or "auto")
    preferred = str(selection.get("model") or "") if requested in {"", "auto"} else requested
    rows = catalog.with_capability("text_to_video", kind="video", usable=True)
    # The full tier is reachable only through the H3 reference path. Calling it
    # here would burn a paid H3 run without the reference video it needs.
    rows = [row for row in rows if str((row.get("remake") or {}).get("tier") or "") != "full"]
    ordered: list[dict[str, Any]] = []
    if preferred:
        ordered.extend(row for row in rows if row.get("id") == preferred)
    ordered.extend(row for row in rows if row.get("id") != preferred)
    return ordered


def _generation_prompt(run: Any, script: dict[str, Any], skeleton: dict[str, Any], selection: dict[str, Any]) -> str:
    """Prompt for a model that does not receive the reference video.

    A saved `inputs.prompt_override` always wins so the operator can inspect and
    edit the rendered prompt before spending a generation call.
    """
    override = str((run.inputs or {}).get("prompt_override") or "").strip()
    if override:
        return override[:4000]
    if run.scenario != "viral-remake":
        return _script_prompt(run, script)
    spec = remake_spec.build_spec(run, skeleton, script)
    mode = str(selection.get("mode") or "generation")
    if mode == "keyframe":
        return remake_spec.render_generation(spec, anchor=True)
    if mode == "reference":
        return remake_spec.render_reference(spec)
    return remake_spec.render_generation(spec)


def generate(run_id: str) -> dict[str, Any]:
    run = store.read_run(run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    selection = getattr(run, "selection", None) or {}
    attempts: list[dict[str, Any]] = []
    if selection.get("mode") == "h3_reference":
        try:
            generated_h3 = generate_h3_reference(run_id)
            generated_h3["attempts"] = []
            generated_h3["warnings"] = list(generated_h3.get("warnings") or [])
            return generated_h3
        except Exception as exc:  # noqa: BLE001
            # A failed H3 run must not fail the whole run while a weaker but
            # usable rung exists. Step one rung down inside the same run and
            # keep the failure in `history` so the UI can explain it.
            error = f"{type(exc).__name__}: {exc}"[:500]
            run = store.read_run(run_id) or run
            degraded = remake_policy.degrade(run, selection, reason=error)
            run.selection = degraded
            store.write_run(run)
            attempts.append({"rung": "full", "model": "minimax.h3", "status": "failed", "error": error})
            if degraded.get("mode") == "analysis_only":
                raise RuntimeError(f"完整复刻失败，且没有可降级的视频模型：{error}") from exc
            selection = degraded
    advanced = params.merged_advanced(run.advanced)
    selected_duration = (selection.get("params") or {}).get("duration")
    duration = max(1.0, float(selected_duration or advanced.get("duration") or 12))
    width, height = params.size_for(str(advanced.get("aspect") or "9:16"), str(advanced.get("resolution") or "720p"))
    ref_id = (run.inputs or {}).get("reference_asset_id")
    source = store.asset_media_path(ref_id) if ref_id else None
    result_path = store.run_artifact(run_id, "provider_raw.mp4")
    script = store.read_json(store.run_dir(run_id) / "artifacts" / "script.json", {}) or {}
    skeleton = store.read_json(store.run_dir(run_id) / "artifacts" / "skeleton.json", {}) or {}
    prompt = _generation_prompt(run, script, skeleton, selection)
    images = _reference_images(run)
    if str(selection.get("mode") or "") == "keyframe":
        anchor = _keyframe_image(run, skeleton, run_id)
        if anchor is not None:
            # Keyframe adapters take exactly one image; the anchor wins over
            # product references, which is why the policy skips this rung for
            # product replacement.
            images = [anchor]
    candidates = _video_candidates(run)
    if not candidates:
        raise RuntimeError("没有可用的视频模型：请在设置里启用对应厂商 key")
    skipped_providers: set[str] = set()
    for model in candidates:
        model_id = str(model.get("id") or "")
        provider_name = str(model.get("provider") or "")
        if provider_name in skipped_providers:
            attempts.append({"model": model_id, "error": "skipped: same provider failed"})
            continue
        try:
            provider = _adapter(model_id)
            if provider is None:
                # Test-only synthetic model: local clip, no provider key.
                ffmpeg.make_synthetic_clip(source, result_path, duration=duration, width=width, height=height, fps=int(advanced.get("fps") or 30))
                generated = {"model": model_id, "path": str(result_path), "demo": True, "duration_s": duration}
            else:
                provider.generate(
                    prompt,
                    images=images,
                    duration=int(duration),
                    resolution=str(advanced.get("resolution") or "720p"),
                    aspect=str(advanced.get("aspect") or "9:16"),
                    model=model_id,
                    output=result_path,
                )
                generated = {"model": model_id, "path": str(result_path), "demo": False, "duration_s": duration}
            generated["attempts"] = attempts
            warnings = [f"已切换到 {model_id}"] if attempts else []
            if attempts and attempts[0].get("rung") == "full":
                warnings.insert(0, f"完整复刻失败，已降级为按拆解生成：{str(attempts[0].get('error') or '')[:160]}")
            generated["warnings"] = warnings
            run = store.read_run(run_id) or run
            run.advanced["model"] = model_id
            if selection:
                run.selection = {**selection, "model": model_id, "fallback": bool(attempts) or bool(selection.get("fallback"))}
            store.write_run(run)
            return generated
        except Exception as exc:  # noqa: BLE001
            attempts.append({"model": model_id, "error": f"{type(exc).__name__}: {exc}"[:500]})
            if _provider_fatal(f"{type(exc).__name__}: {exc}"):
                skipped_providers.add(provider_name)
    raise RuntimeError("所有视频模型均失败：" + " | ".join(f"{item['model']}: {item['error']}" for item in attempts)[:900])
