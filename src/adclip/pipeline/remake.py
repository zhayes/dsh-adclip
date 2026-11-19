"""Prompt construction for MiniMax H3 reference replacement.

H3 sees the reference video and the replacement images; the prompt only has to
state what changes and what must stay. Keeping the contract in one place means
the UI, the DSH tool and the engine all send the same preservation rules.
"""
from __future__ import annotations

from typing import Any


def _persona_text(advanced: dict[str, Any]) -> str:
    persona = (advanced.get("persona") or {}) if isinstance(advanced.get("persona"), dict) else {}
    if not persona:
        return ""
    gender = {"male": "男性", "female": "女性", "any": "人物"}.get(str(persona.get("gender") or "any"), "人物")
    age = {
        "teenager": "18–24 岁",
        "youth": "25–34 岁",
        "middle_aged": "35–54 岁",
        "senior": "55 岁以上",
    }.get(str(persona.get("age") or "youth"), "25–34 岁")
    body = {"slim": "偏瘦", "standard": "标准", "athletic": "健硕", "chubby": "微胖"}.get(
        str(persona.get("body_type") or "standard"), "标准"
    )
    return f"{age}{gender}，{body}体型"


def analysis_summary(skeleton: dict[str, Any]) -> dict[str, Any]:
    plan = skeleton.get("remake_plan") or {}
    shots = plan.get("shots") or []
    products = [str((shot.get("product") or {}).get("name") or "").strip() for shot in shots]
    casts = [
        str(item.get("description") or "").strip()
        for shot in shots
        for item in (shot.get("cast") or [])
        if str(item.get("description") or "").strip()
    ]
    return {
        "shots": len(shots),
        "product": next((value for value in products if value), ""),
        "cast": list(dict.fromkeys(casts))[:4],
        "preserve": list((plan.get("global") or {}).get("preserve") or [])[:10],
    }


def _spoken_lines(script_doc: dict[str, Any] | None) -> list[str]:
    rows = (script_doc or {}).get("beats") or []
    out: list[str] = []
    for row in rows:
        lines = []
        for line in (row.get("lines") or []):
            text = str((line or {}).get("text") or "").strip()
            if not text:
                continue
            speaker = str((line or {}).get("speaker") or "").strip()
            lines.append(f"{speaker}：{text}" if speaker else text)
        if not lines:
            continue
        try:
            start = float(row.get("start_s") or 0)
            end = float(row.get("end_s") or 0)
        except (TypeError, ValueError):
            start, end = 0.0, 0.0
        out.append(f"{start:.1f}–{end:.1f}s：\n" + "\n".join(lines))
    return out


def build_h3_replace_prompt(
    run: Any,
    skeleton: dict[str, Any],
    *,
    product_count: int = 0,
    person_count: int = 0,
    script_doc: dict[str, Any] | None = None,
    audio_mode: str = "regenerate",
) -> str:
    """Build the H3 replacement instruction, bounded to 7000 characters."""
    inputs = run.inputs or {}
    advanced = run.advanced or {}
    brief = str(inputs.get("brief") or "").strip()
    overrides = str(inputs.get("explicit_overrides") or "").strip()
    scope = str(advanced.get("replace_scope") or "both")
    person_scope = str(advanced.get("person_scope") or "main")
    plan = skeleton.get("remake_plan") or {}
    summary = analysis_summary(skeleton)
    audio_mode = str(audio_mode or "regenerate")
    spoken = _spoken_lines(script_doc) if audio_mode == "regenerate" else []
    audio_tail = "和原声台词/音效。" if audio_mode != "regenerate" or not spoken else "。"

    lines: list[str] = [
        "参考视频1的镜头、景别、运镜、场景、动作、构图、光线、节奏、转场" + audio_tail,
        "只做以下替换，未提及的部分保持原样：",
    ]
    product_label = "图片1" if product_count else "商品参考图"
    if scope in {"both", "product"}:
        name = summary.get("product") or "原商品"
        lines.append(
            f"1. 将视频1中的商品（{name}）替换为{product_label}中的商品；"
            "保留原商品的位置、大小、手持方式、出现时机、包装朝向和遮挡关系。"
        )
    if scope in {"both", "person"}:
        start = product_count + 1 if product_count else 1
        person_label = f"图片{start}" if person_count else "人物参考图"
        cast = "、".join(summary.get("cast") or [])
        who = f"原片中的主角（{cast}）" if cast else "原片中的主角"
        if person_scope == "all":
            who = "原片中的所有人物"
        lines.append(
            f"{2 if scope == 'both' else 1}. 将{who}替换为{person_label}中的人物；"
            "保留原人物的位置、动作、表情、口型、服装风格、人物关系和镜头关系。"
        )
    if audio_mode == "regenerate" and spoken:
        lines.extend([
            "参考视频1没有声音；只保留画面、镜头、场景、动作、构图和节奏。",
            "台词（只念以下句子，不要念镜头描述或制作说明）：",
            *spoken[:8],
            "按时间顺序逐句念；同一时间只能有一个声音说话；",
            "不要同时念 A/B 两行，不要把两句台词叠在一起，不要叠加原声、旧台词或背景人声。",
            "请用与原片一致的语速、口型节奏和音色重新生成中文对白和必要音效；台词必须与以上文字一致。",
            "其他人物、场景、道具、构图、运镜、转场和时长保持不变。",
            "不要新增镜头，不要删除镜头，不要改变场景、动作、镜头或转场；不要生成字幕或任何屏幕叠加元素。",
        ])
    else:
        lines.extend([
            "其他人物、场景、道具、构图、运镜、转场、时长和原声台词/音效全部保持不变。",
            "不要新增镜头，不要删除镜头，不要改变场景、动作、台词或转场；不要生成字幕或任何屏幕叠加元素。",
            "保留参考视频1的原声、台词和音效，不要重新生成音频。",
        ])
    persona = _persona_text(advanced)
    if persona and scope in {"both", "person"}:
        lines.append(f"替换后的人物设定：{persona}。")
    if brief:
        lines.append(f"用户需求（制作说明，不是台词）：{brief[:800]}")
    if overrides:
        lines.append(f"用户明确要求改动的例外（其余仍按上面的保留规则）：{overrides[:800]}")
    # Keep the model's prompt budget; H3 accepts up to 7000 characters.
    text = "\n".join(line for line in lines if line.strip())
    return text[:7000]
