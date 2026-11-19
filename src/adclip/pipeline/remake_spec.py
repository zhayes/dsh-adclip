"""One remake spec, three deterministic renderers.

The analysis produces facts; the brief produces requirements. Neither is
rewritten here. `build_spec()` merges them into one document, and each renderer
flattens that document for a family of video models:

- `render_h3()`        reference video direct: only "change this, keep that".
- `render_reference()` reference video direct, shorter contract.
- `render_generation()` no reference video: everything must be spelled out.

Renderers are pure functions of the spec: no model calls, no randomness, so the
same run always produces the same prompt and tests can assert on it.
"""
from __future__ import annotations

from typing import Any

from .. import requirements
from . import persona as persona_mod
from . import timing


def orientation(aspect: str) -> str:
    value = str(aspect or "9:16")
    if value in {"16:9", "4:3", "21:9"}:
        return "横屏"
    if value in {"1:1"}:
        return "方形"
    return "竖屏"


def _timed_lines(shot: dict[str, Any]) -> list[dict[str, Any]]:
    """New dialogue lines mapped onto time slots.

    When the ASR rows and the script lines line up they share their real
    timings; otherwise the lines are spread evenly across the shot, which is
    honest about not knowing where each sentence lands.
    """
    lines = [str(text).strip() for text in shot.get("lines") or [] if str(text).strip()]
    if not lines:
        return []
    span = float(shot.get("end_s") or 0) - float(shot.get("start_s") or 0)
    # Last guard before the prompt: a line that no human could say inside the
    # shot is shortened here, so the model is never asked for the impossible.
    lines, _ = timing.fit_lines(lines, span, cps=timing.MAX_CPS)
    rows = shot.get("dialogue_rows") or []
    if len(rows) == len(lines):
        aligned = [
            {
                "start_s": round(float(row.get("start_s") or 0), 2),
                "end_s": round(float(row.get("end_s") or 0), 2),
                "text": line,
            }
            for line, row in zip(lines, rows)
        ]
        if all(
            item["end_s"] - item["start_s"] >= timing.speak_seconds(item["text"], timing.MAX_CPS)
            for item in aligned
        ):
            return aligned
    return timing.schedule(lines, float(shot.get("start_s") or 0), float(shot.get("end_s") or 0))


def build_spec(run: Any, skeleton: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
    plan = skeleton.get("remake_plan") or {}
    source = skeleton.get("source") or {}
    advanced = dict(getattr(run, "advanced", None) or {})
    inputs = dict(getattr(run, "inputs", None) or {})
    beats = skeleton.get("beats") or []
    script_beats = {str(item.get("id")): item for item in (script.get("beats") or [])}
    shots: list[dict[str, Any]] = []
    for index, shot in enumerate(plan.get("shots") or []):
        beat = beats[index] if index < len(beats) else {}
        script_beat = script_beats.get(str(beat.get("id"))) or {}
        camera = shot.get("camera") or {}
        shots.append({
            "index": index,
            "start_s": float(shot.get("start_s") or beat.get("start_s") or 0),
            "end_s": float(shot.get("end_s") or beat.get("end_s") or 0),
            "shot_size": str(camera.get("shot_size") or ""),
            "camera_angle": str(camera.get("angle") or ""),
            "camera_movement": str(camera.get("movement") or ""),
            "composition": str(shot.get("composition") or ""),
            "continuity": str(shot.get("continuity") or ""),
            "scene": str(shot.get("scene") or ""),
            "action": str(script_beat.get("shot") or shot.get("action") or ""),
            "reference_action": str(shot.get("action") or ""),
            "cast": list(shot.get("cast") or []),
            "product": dict(shot.get("product") or {}),
            "on_screen_text": str(shot.get("on_screen_text") or ""),
            "transition_in": str(shot.get("transition_in") or "cut"),
            "dialogue_source": str(shot.get("dialogue_source") or beat.get("dialogue_source") or ""),
            "dialogue_rows": list(shot.get("dialogue_rows") or beat.get("dialogue_rows") or []),
            "lines": [
                str((line or {}).get("text") or "").strip()
                for line in (script_beat.get("lines") or [])
                if str((line or {}).get("text") or "").strip()
            ],
        })
    for shot in shots:
        shot["timed_lines"] = _timed_lines(shot)
    scope = str(advanced.get("replace_scope") or "both")
    replace = ["商品"] if scope == "product" else ["人物"] if scope == "person" else ["人物", "商品"]
    return {
        "version": 1,
        "source": {
            "duration_s": source.get("duration_s"),
            "aspect": str(source.get("aspect") or advanced.get("aspect") or "9:16"),
            "cuts_s": list(skeleton.get("cuts_s") or []),
            "has_audio": bool(source.get("has_audio")),
        },
        "shots": shots,
        "global": {
            "preserve": list((plan.get("global") or {}).get("preserve") or ["镜头", "景别", "运镜", "场景", "动作", "构图", "节奏", "转场"]),
            "replace": replace,
            "persona": persona_mod.persona_instruction(advanced),
        },
        "requirements": requirements.derive(str(inputs.get("brief") or ""), advanced),
        "overrides": str(inputs.get("explicit_overrides") or "").strip(),
        "audio": {
            "mode": str(advanced.get("audio_mode") or "regenerate"),
            "no_bgm": True,
        },
        "constraints": {
            "product_count": len(list(inputs.get("product_asset_ids") or [])),
            "person_count": len(list((advanced.get("persona_map") or {}).values())),
        },
    }


def _camera_label(shot: dict[str, Any]) -> str:
    return " · ".join(
        value for value in (
            str(shot.get("shot_size") or ""),
            str(shot.get("camera_movement") or ""),
            str(shot.get("camera_angle") or ""),
        ) if value
    )


def _shot_block(shot: dict[str, Any], index: int, *, persona: str, people_replaced: bool) -> list[str]:
    """One shot as the breakdown described it: camera, scene, action, framing.

    The analysis is the only grounded description of the reference, so it is
    carried shot by shot instead of being averaged into one global line: a
    two-shot reference often changes scene, lens and framing between cuts.
    """
    span = f"{float(shot.get('start_s') or 0):.1f}–{float(shot.get('end_s') or 0):.1f}s"
    camera = _camera_label(shot)
    lines = [f"【镜头{index + 1}】{span}" + ("｜" + camera if camera else "")]
    if shot.get("scene"):
        lines.append("场景：" + str(shot["scene"]))
    action = str(shot.get("reference_action") or shot.get("action") or "").strip()
    if action:
        lines.append("动作：" + action)
    if shot.get("composition"):
        lines.append("构图：" + str(shot["composition"]))
    if shot.get("continuity") and str(shot["continuity"]) not in {"不确定", "unknown"}:
        lines.append("衔接：" + str(shot["continuity"]))
    if index > 0 and str(shot.get("transition_in") or "cut") == "cut":
        lines.append("转场：从上个镜头硬切")
    cast = [str(item.get("description") or "").strip() for item in shot.get("cast") or [] if str(item.get("description") or "").strip()]
    if cast and not persona and not people_replaced:
        lines.append("人物：" + "、".join(dict.fromkeys(cast[:3])))
    for row in shot.get("timed_lines") or []:
        lines.append(
            f"台词 [{float(row['start_s']):.1f}–{float(row['end_s']):.1f}s] {row['text']}"
        )
    return lines


def render_generation(spec: dict[str, Any], *, limit: int = 3500, anchor: bool = False) -> str:
    """Full description for a model that cannot see the reference video.

    The layout mirrors the breakdown: every shot keeps its own lens, scene,
    action and framing, because that is where the reference drift shows up.
    """
    shots = spec.get("shots") or []
    source = spec.get("source") or {}
    req = spec.get("requirements") or {}
    audio = spec.get("audio") or {}
    preserve = list((spec.get("global") or {}).get("preserve") or [])
    replace = list((spec.get("global") or {}).get("replace") or [])
    # The spoken audio is rewritten in `regenerate`, so claiming to preserve it
    # in the same sentence would contradict the dialogue block.
    if (spec.get("audio") or {}).get("mode") == "regenerate":
        preserve = [value for value in preserve if value != "原声"]
    duration = float(source.get("duration_s") or 0)
    orientation_label = orientation(str(source.get("aspect") or "9:16"))
    if len(shots) <= 1:
        shot_phrase = "一次连续拍摄，中间不切换镜头"
    else:
        shot_phrase = f"{len(shots)} 个镜头按顺序拍摄，镜头之间硬切，无转场特效（切点位置为近似）"
    head = [
        f"任务：{orientation_label}短视频，约 {duration:.1f} 秒，{shot_phrase}。" if duration
        else f"任务：{orientation_label}短视频，{shot_phrase}。",
    ]
    if replace:
        head.append(
            f"【替换】只替换：{'、'.join(replace)}；"
            f"{'、'.join(preserve) if preserve else '镜头、场景、动作、构图、节奏、转场'} 与参考片一致。"
        )
    materials: list[str] = []
    if anchor:
        materials.append("图片1=参考片首帧，第 1 帧必须与图片一致，后续动作从该帧自然延续")
    elif int((spec.get("constraints") or {}).get("product_count") or 0):
        materials.append("图片1=替换后的商品，包装、颜色、文字以图片为准")
    if int((spec.get("constraints") or {}).get("person_count") or 0):
        materials.append("人物参考图=替换后的人物")
    if materials:
        head.append("【素材】" + "；".join(materials) + "。")

    persona = str((spec.get("global") or {}).get("persona") or "").strip()
    cast = [item.get("description") for shot in shots for item in shot.get("cast") or [] if item.get("description")]
    if persona:
        head.append(f"【人物】{persona}，面向镜头自然交流；人数、站位与参考片一致。")
    elif "人物" in replace:
        head.append("【人物】人物全部替换，人数、站位、动作与参考片一致；不要新增或删除人物。")
    elif cast:
        head.append("【人物】" + "、".join(dict.fromkeys(cast[:3])) + "。")

    product_hint = str(req.get("product_hint") or "").strip()
    if product_hint:
        head.append(f"【商品】{product_hint}，包装与图片一致，手持展示、标签清晰。")

    for index, shot in enumerate(shots):
        head.extend(_shot_block(shot, index, persona=persona, people_replaced="人物" in replace))

    dialogue = [
        row for shot in shots for row in (shot.get("timed_lines") or [])
    ]
    if dialogue:
        head.append(
            f"【台词要求】共 {len(dialogue)} 句，必须逐句完整念完，不得省略、合并或改写；"
            "标准普通话，同一时间只有一个人说话；每句说完停 0.2–0.5 秒。"
        )
        head.append("【语速】按每秒 4–5 个字念，严格贴着每句标注的起止时间；句子还没念完不要切走。")
        prices = [str(value) for value in req.get("prices") or []]
        if prices:
            head.append("必须清楚说出价格：" + "、".join(prices) + "。")
        if duration:
            head.append(f"全部台词必须在约 {max(0.5, duration - 0.3):.1f} 秒前说完；说完后不要留长时间空白画面。")
    if audio.get("no_bgm"):
        head.append("【音频】无背景音乐；只有人物同期声；环境音可选且音量低于人声。")

    # Watermarks are controlled by the provider parameter (`watermark: false`),
    # not by prompt text: naming them can leak the word into the picture, so the
    # negative list describes the look instead of repeating the words.
    forbidden = ["无字幕", "无贴纸", "无分屏", "无画中画", "不得漏句"]
    if req.get("clean_text"):
        forbidden.append("画面内只保留商品本身，不出现价格牌或广告大字报")
    head.append("【禁止】" + "、".join(forbidden) + "。")

    text = "\n".join(head)
    brief = str(req.get("brief") or "").strip()
    if brief:
        note = f"【制作说明（不是台词）】{brief[:300]}"
        if len(text) + len(note) + 1 <= limit:
            text += "\n" + note
    overrides = str(spec.get("overrides") or "").strip()
    if overrides:
        note = f"【用户明确要求】{overrides[:300]}"
        if len(text) + len(note) + 1 <= limit:
            text += "\n" + note
    return text[:limit]


def render_reference(spec: dict[str, Any], *, limit: int = 1500) -> str:
    """Short contract for a model that receives the reference video."""
    shots = spec.get("shots") or []
    req = spec.get("requirements") or {}
    scope = "、".join((spec.get("global") or {}).get("replace") or ["人物", "商品"])
    lines = [
        "任务：视频编辑，不是重新拍摄。保留参考视频1的镜头、景别、运镜、场景、动作、构图、节奏和转场。",
        f"只替换：{scope}。未提及的部分保持原样。",
    ]
    if int((spec.get("constraints") or {}).get("product_count") or 0):
        lines.append("图片1=替换后的商品；保留原商品的位置、大小、手持方式和出现时机。")
    persona = str((spec.get("global") or {}).get("persona") or "").strip()
    if persona and "人物" in scope:
        lines.append(f"人物替换为：{persona}；保留原人物位置、动作、表情和口型节奏。")
    dialogue = []
    for shot in shots:
        for row in shot.get("timed_lines") or []:
            dialogue.append(f"[{float(row['start_s']):.1f}–{float(row['end_s']):.1f}s] {row['text']}")
    if dialogue:
        lines.append("台词（按顺序逐句念完，不得省略或合并，不要念镜头描述；语速每秒 4–5 个字）：")
        lines.extend(dialogue[:12])
        if req.get("prices"):
            lines.append("必须清楚说出价格：" + "、".join(req["prices"]) + "。")
    else:
        lines.append("保留原声台词和音效，不要重新生成音频。")
    forbidden = ["无字幕", "无分屏"]
    if req.get("clean_text"):
        forbidden.append("画面内不出现任何文字或广告大字报")
    lines.append("禁止：" + "、".join(forbidden) + "。")
    if req.get("brief"):
        lines.append(f"制作说明（不是台词）：{req['brief'][:300]}")
    text = "\n".join(lines)
    return text[:limit]


def render_h3(
    spec: dict[str, Any],
    run: Any,
    skeleton: dict[str, Any],
    script: dict[str, Any],
    *,
    audio_mode: str = "regenerate",
) -> str:
    """H3 keeps its own long contract; this wrapper keeps one entry point."""
    from . import remake as remake_mod

    constraints = spec.get("constraints") or {}
    return remake_mod.build_h3_replace_prompt(
        run,
        skeleton,
        product_count=int(constraints.get("product_count") or 0),
        person_count=int(constraints.get("person_count") or 0),
        script_doc=script,
        audio_mode=audio_mode,
    )


def render(spec: dict[str, Any], mode: str, *, run: Any = None, skeleton: dict[str, Any] | None = None,
           script: dict[str, Any] | None = None, audio_mode: str = "regenerate") -> str:
    """Pick the renderer for a selection mode."""
    if str(mode) == "h3_reference" and run is not None and skeleton is not None and script is not None:
        return render_h3(spec, run, skeleton, script, audio_mode=audio_mode)
    if str(mode) in {"reference", "keyframe"}:
        return render_reference(spec)
    return render_generation(spec)
