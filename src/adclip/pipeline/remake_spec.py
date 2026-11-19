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


def _merge_to(lines: list[str], count: int) -> list[str]:
    """Merge adjacent lines until there are `count` of them.

    The reference only has `count` spoken windows; keeping the extra rewrite
    lines would force an even re-spread and lose the original pauses (and the
    tail of the last line). Joining with a comma keeps every word.
    """
    out = [str(line).strip() for line in lines if str(line).strip()]
    while len(out) > count:
        index = min(range(len(out) - 1), key=lambda i: len(out[i]) + len(out[i + 1]))
        out[index:index + 2] = [out[index].rstrip("，。！？；、,.!?;") + "，" + out[index + 1].lstrip("，。 ")]
    return out


def _timed_lines(shot: dict[str, Any]) -> list[dict[str, Any]]:
    """New dialogue lines mapped onto time slots.

    The reference's own ASR windows are the ground truth for rhythm: if the
    rewrite has one line per reference line, each line keeps the original
    start/end and is shortened to what that window holds. That copies the
    original speaker's pauses instead of spreading the text evenly, which used
    to squeeze the last line into a slot it could not finish.
    """
    lines = [str(text).strip() for text in shot.get("lines") or [] if str(text).strip()]
    if not lines:
        return []
    start_s = float(shot.get("start_s") or 0)
    end_s = float(shot.get("end_s") or 0)
    rows = shot.get("dialogue_rows") or []
    if rows and len(lines) > len(rows):
        lines = _merge_to(lines, len(rows))
    if len(rows) == len(lines) and rows:
        aligned: list[dict[str, Any]] = []
        for line, row in zip(lines, rows):
            row_start = max(start_s, float(row.get("start_s") or 0))
            row_end = min(end_s - timing.TAIL_S, float(row.get("end_s") or 0))
            if row_end - row_start < 0.4:
                row_end = min(end_s - timing.TAIL_S, row_start + 0.4)
            window = max(0.4, row_end - row_start)
            # Only cut what is physically impossible in this window: the
            # script prompt already asks for one short line per window.
            fitted, _ = timing.fit_lines(
                [line], window, cps=timing.MAX_CPS, grace=1.0, single_grace=1.0
            )
            aligned.append({
                "start_s": round(row_start, 2),
                "end_s": round(row_end, 2),
                "text": (fitted or [line])[0],
            })
        if all(item["end_s"] > item["start_s"] for item in aligned):
            return aligned
    # Line count differs from the reference: fall back to an even spread.
    lines, _ = timing.fit_lines(
        lines, timing.speak_span(end_s - start_s), cps=timing.MAX_CPS, grace=timing.GRACE
    )
    return timing.schedule(lines, start_s, end_s)


def _clip_level_fit(shots: list[dict[str, Any]], duration: Any) -> None:
    """Trim the longest lines until the whole script fits the clip.

    A generation model recites continuously at roughly four characters a
    second; per-shot windows cannot see the other shots, so a script that only
    fits when every shot is packed is exactly the one that loses its last
    words. Only the longest line shrinks, never below four characters.
    """
    total_duration = float(duration or 0)
    if total_duration <= 0:
        return
    limit = timing.char_budget(timing.speak_span(total_duration), timing.DEFAULT_CPS)
    rows = [row for shot in shots for row in shot.get("timed_lines") or []]
    total = sum(len(str(row.get("text") or "")) for row in rows)
    if total <= limit or not rows:
        return
    if len(rows) == 1:
        rows[0]["text"] = timing.shorten(str(rows[0].get("text") or ""), limit)
        return
    # The closing line carries the price or the punchline: shrink the others
    # proportionally and leave it whole.
    closing = str(rows[-1].get("text") or "")
    others = rows[:-1]
    budget = max(timing.MIN_LINE_CHARS * len(others), limit - len(closing))
    for row, text in zip(others, timing.fit_chars([str(item.get("text") or "") for item in others], budget)):
        row["text"] = text


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
            "expression": str(shot.get("expression") or ""),
            "tone": str(shot.get("tone") or ""),
            "pace_cps": (float(shot["pace_cps"]) if isinstance(shot.get("pace_cps"), (int, float)) and shot["pace_cps"] else None),
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
    pace = plan.get("pace_cps")
    if not isinstance(pace, (int, float)) or not pace:
        pace = timing.measured_cps([row for shot in shots for row in shot.get("dialogue_rows") or []])
    req = requirements.derive(str(inputs.get("brief") or ""), advanced)
    for shot in shots:
        if not shot.get("pace_cps"):
            shot["pace_cps"] = round(float(pace), 2) if pace else None
        shot["timed_lines"] = _timed_lines(shot)
    _clip_level_fit(shots, source.get("duration_s"))
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
            "pace_cps": round(float(pace), 2) if pace else None,
        },
        "requirements": req,
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
    if shot.get("expression"):
        lines.append("表情：" + str(shot["expression"]))
    tone = str(shot.get("tone") or "").strip()
    pace_label = timing.pace_label(shot.get("pace_cps"))
    delivery = "；".join(value for value in (tone, ("语速" + pace_label) if pace_label else "") if value)
    if delivery:
        lines.append("语气：" + delivery)
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

    persona = str((spec.get("global") or {}).get("persona") or "").strip().rstrip("。；;，,")
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
            "标准普通话，同一时间只有一个人说话；句间只留约 0.1 秒换气，"
            "不要出现明显空白或静音段；镜头切换处不要停，上一句说完直接切。"
        )
        pace = (spec.get("global") or {}).get("pace_cps")
        if pace:
            label = timing.pace_label(pace)
            head.append(
                f"【语速】原片约每秒 {float(pace):.1f} 个字" + (f"，{label}" if label else "")
                + "；用同样的语气和节奏复刻，不要拖慢也不要像播报员念稿。"
            )
        else:
            head.append("【语速】按参考片的节奏念，不要拖慢也不要像播报员念稿。")
        head.append("严格贴着每句标注的起止时间；句子还没念完不要切走。")
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
        lines.append(
            "台词（按顺序逐句念完，不得省略或合并，不要念镜头描述"
            + (f"；语速每秒约 {(spec.get('global') or {}).get('pace_cps'):.1f} 个字" if (spec.get("global") or {}).get("pace_cps") else "")
            + "）："
        )
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
