"""Persona text normalization for reference-based generation.

Reference analysis describes the people in the source video. When the operator
selects a persona, those descriptions are useful for blocking/actions but must
not override the selected gender/age. Keep that rule in one place so script and
provider prompts agree.
"""
from __future__ import annotations

import re
from typing import Any


def persona(advanced: dict[str, Any] | None) -> dict[str, Any]:
    value = (advanced or {}).get("persona")
    return value if isinstance(value, dict) else {}


def persona_label(advanced: dict[str, Any] | None) -> str:
    p = persona(advanced)
    if not p:
        return ""
    gender = {"male": "男性", "female": "女性", "any": "人物"}.get(p.get("gender") or "any", "人物")
    age = {"teenager": "18–24 岁", "youth": "25–34 岁", "middle_aged": "35–54 岁", "senior": "55 岁以上"}.get(p.get("age") or "youth", "")
    body = {"slim": "偏瘦", "standard": "标准", "athletic": "健硕", "chubby": "微胖"}.get(p.get("body_type") or "standard", "")
    ethnicity = {"asian": "亚洲", "caucasian": "欧美", "latino": "拉美", "african": "非洲", "middle_eastern": "中东", "any": "不限"}.get(p.get("ethnicity") or "any", "")
    return "，".join(x for x in (age + gender, body + "体型", ethnicity) if x)


def persona_instruction(advanced: dict[str, Any] | None) -> str:
    label = persona_label(advanced)
    if not label:
        return ""
    return (
        f"模特设定：{label}。参考片人物只用于动作、构图和人物关系，"
        "不得沿用参考片中人物的性别、年龄或外貌；所有出镜人物必须符合模特设定。"
    )


def neutralize_people(text: str, advanced: dict[str, Any] | None) -> str:
    """Replace contradictory gender words in reference-derived actions."""
    value = str(text or "")
    p = persona(advanced)
    gender = p.get("gender")
    if not value or gender not in {"male", "female"}:
        return value
    if gender == "female":
        value = re.sub(r"男子|男性|男人|男生|男演员|男孩", "女性", value)
        value = re.sub(r"三男|两名男|几名男", "三名女性", value)
    else:
        value = re.sub(r"女子|女性|女人|女生|女演员|女孩", "男性", value)
        value = re.sub(r"三女|两名女|几名女", "三名男性", value)
    age = p.get("age")
    if age in {"teenager", "youth"}:
        value = re.sub(r"老年|老人|中年", "青年", value)
    return value
