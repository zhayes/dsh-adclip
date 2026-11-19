"""Rule-first assistant changes.

The assistant is deliberately a form copilot: it returns changes, never starts
a run. The common phrases from the operator playbook are handled here.
"""
from __future__ import annotations

import re
from typing import Any

from . import catalog
from .models import AssistantRequest


def _change(field: str, old: Any, new: Any, stage: str, label: str) -> dict[str, Any]:
    return {
        "field": field,
        "from": old,
        "to": new,
        "stage": stage,
        "requires_regeneration": stage == "generate",
        "label": label,
    }


def analyze(req: AssistantRequest) -> dict[str, Any]:
    text = req.message.strip()
    context = req.context or {}
    advanced = dict(context.get("advanced") or {})
    persona = dict(context.get("persona") or {})
    post = dict(context.get("post") or {})
    changes: list[dict[str, Any]] = []
    questions: list[str] = []
    actions: list[str] = []

    # aspect
    aspect = None
    if re.search(r"横屏|16\s*[:：]\s*9", text):
        aspect = "16:9"
    elif re.search(r"竖屏|9\s*[:：]\s*16", text):
        aspect = "9:16"
    elif re.search(r"方形|1\s*[:：]\s*1", text):
        aspect = "1:1"
    if aspect and aspect != advanced.get("aspect"):
        changes.append(_change("advanced.aspect", advanced.get("aspect"), aspect, "generate", "比例"))
        advanced["aspect"] = aspect

    # resolution
    resolution = None
    if re.search(r"1080|高清", text):
        resolution = "1080p"
    elif re.search(r"720|标清", text):
        resolution = "720p"
    elif re.search(r"480|草稿", text):
        resolution = "480p"
    if resolution and resolution != advanced.get("resolution"):
        changes.append(_change("advanced.resolution", advanced.get("resolution"), resolution, "generate", "清晰度"))
        advanced["resolution"] = resolution

    # duration
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s|S)", text)
    if match:
        duration = int(round(float(match.group(1))))
        duration = max(1, min(30, duration))
        if duration != advanced.get("duration"):
            changes.append(_change("advanced.duration", advanced.get("duration"), duration, "generate", "时长"))
            advanced["duration"] = duration

    # model: a vendor keyword selects that vendor's first usable model, never a
    # hardcoded id, so new models from the same provider are picked up.
    vendor = None
    if re.search(r"可灵|kling", text, re.I):
        vendor = "kling"
    elif re.search(r"seedance|方舟|ark", text, re.I):
        vendor = "ark"
    elif re.search(r"minimax|海螺|hailuo", text, re.I):
        vendor = "minimax"
    if vendor:
        candidate = next((row for row in catalog.rows()
                          if row["kind"] == "video" and row["provider"] == vendor
                          and row.get("available") and row.get("enabled")), None)
        if candidate is not None:
            changes.append(_change("advanced.model", advanced.get("model"), candidate["id"], "generate", "模型"))

    # persona gender
    gender = None
    if re.search(r"换成女性|女性|女生|女主", text):
        gender = "female"
    elif re.search(r"换成男性|男性|男生|男主", text):
        gender = "male"
    if gender and gender != persona.get("gender"):
        changes.append(_change("persona.gender", persona.get("gender"), gender, "generate", "模特性别"))
        persona["gender"] = gender

    # persona age
    age = None
    if re.search(r"年龄大|老一点|成熟", text):
        age = {"teenager": "youth", "youth": "middle_aged", "middle_aged": "senior", "senior": "senior"}.get(persona.get("age") or "youth")
    elif re.search(r"年轻|年龄小|小几岁", text):
        age = {"teenager": "teenager", "youth": "teenager", "middle_aged": "youth", "senior": "middle_aged"}.get(persona.get("age") or "youth")
    if age and age != persona.get("age"):
        changes.append(_change("persona.age", persona.get("age"), age, "generate", "模特年龄"))
        persona["age"] = age

    # persona body
    body = None
    if re.search(r"壮|健硕|肌肉", text):
        body = "athletic"
    elif re.search(r"瘦|纤细", text):
        body = "slim"
    elif re.search(r"微胖|丰满", text):
        body = "chubby"
    elif re.search(r"标准|匀称", text):
        body = "standard"
    if body and body != persona.get("body_type"):
        changes.append(_change("persona.body_type", persona.get("body_type"), body, "generate", "模特体型"))
        persona["body_type"] = body

    # persona ethnicity
    ethnicity = None
    if re.search(r"欧美|白人|caucasian", text, re.I):
        ethnicity = "caucasian"
    elif re.search(r"亚洲|asian", text, re.I):
        ethnicity = "asian"
    elif re.search(r"拉美|latino", text, re.I):
        ethnicity = "latino"
    elif re.search(r"非洲|african", text, re.I):
        ethnicity = "african"
    elif re.search(r"中东|middle", text, re.I):
        ethnicity = "middle_eastern"
    if ethnicity and ethnicity != persona.get("ethnicity"):
        changes.append(_change("persona.ethnicity", persona.get("ethnicity"), ethnicity, "generate", "模特族裔"))
        persona["ethnicity"] = ethnicity

    # post-only: subtitle delivery is a switch (SRT sidecar or nothing).
    # Size/music/burn-in controls are gone: the local ffmpeg has neither libass
    # nor drawtext, so those fields could only ever claim a change.
    subtitle_toggled = False
    current_subtitle = str(advanced.get("subtitle") or "off")
    if re.search(r"字幕", text) and re.search(r"关闭|关掉|不要|不用|去掉|取消|不启用|别加|无字幕", text):
        subtitle_toggled = True
        if current_subtitle != "off":
            changes.append(_change("post.subtitle", current_subtitle, "off", "post", "字幕"))
            advanced["subtitle"] = "off"
    elif re.search(r"字幕", text) and re.search(r"开启|打开|加上|加个|要字幕|带字幕|加字幕|启用", text):
        subtitle_toggled = True
        if current_subtitle != "sidecar":
            changes.append(_change("post.subtitle", current_subtitle, "sidecar", "post", "字幕"))
            advanced["subtitle"] = "sidecar"
    if re.search(r"文件.*(小|太大)|码率|体积", text):
        changes.append(_change("post.export_bitrate", post.get("export_bitrate", "8M"), "4M", "post", "导出码率"))
        post["export_bitrate"] = "4M"

    # stitch intent
    stitch_words = re.search(r"拼|合并|接起来|插入|中间加|加个广告|串起来", text)
    if stitch_words:
        actions.append("stitch")
        questions.append("请选择至少两个视频片段，或在素材库里勾选后再打开拼接计划。")

    # reroll / revert
    if re.search(r"再来一条|换一条|重生成一条", text):
        actions.append("retry")
    if re.search(r"上一版|回退|恢复", text):
        actions.append("version")

    # price / product text -> brief changes
    price = re.search(r"价格.*?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:块|元|块九|\.9)", text)
    if price and re.search(r"价格|活动价|原价", text):
        value = price.group(1) or price.group(2)
        changes.append(_change("inputs.brief", context.get("brief"), f"价格调整为 {value}，其余结构不变", "generate", "价格台词"))
        actions.append("needs_brief_merge")

    # A message scoped to one selected shot with no parameter match is a content
    # edit for that shot: applying it rewrites just this beat.
    if req.selected_segment_id and not changes and not actions and not questions and len(text) >= 2:
        changes.append(_change("segment.rewrite", None, text, "generate", "这一镜：重写台词和画面"))

    requires_regen = any(c["stage"] == "generate" for c in changes)
    post_only = bool(changes) and not requires_regen
    if changes and changes[0]["field"] == "segment.rewrite":
        reply = "我把这条要求归到选中的这一镜，应用后只重写并重生成这一段。"
    elif not changes and not questions and actions:
        reply = {"retry": "好，按同参数再生成一条。", "version": "可以切换到上一版。", "stitch": "请选择片段后打开拼接计划。"}.get(actions[0], "我整理成一个动作了，请确认。")
    elif not changes and not questions:
        reply = "我理解为你想调整这条片子。请说具体一点：改台词、换商品/模特、改比例/清晰度、拼接，或只改字幕/音乐。"
        questions.append("你想改内容、画面，还是只改后期？")
    elif post_only:
        reply = "这些是后期修改，不用重生成。"
    elif stitch_words:
        reply = "这需要走拼接计划：选择片段、插入点、转场和音频后，再应用拼接。"
    else:
        reply = "我整理成变更卡了。生成参数变化需要重生成整条或选中分镜；请确认后应用。"
    return {
        "reply": reply,
        "changes": changes,
        "questions": questions,
        "actions": actions,
        "requires_regeneration": requires_regen,
        "post_only": post_only,
        "context_patch": {"advanced": advanced, "persona": persona, "post": post},
    }
