"""Deterministic demo script and gag artefacts.

The real LLM/VLM extraction lands after the provider bake-off. This module
keeps the run shape complete so the UI, storyboard, QA and edits can be built
and tested without API keys.
"""
from __future__ import annotations

import re
from typing import Any

from .. import llm
from . import persona as persona_mod


def _text_model(run: Any) -> dict[str, Any] | None:
    value = (run.advanced or {}).get("text_model")
    return value if isinstance(value, dict) else None


def _fallback_gag(skeleton: dict[str, Any]) -> dict[str, Any]:
    beats = skeleton.get("beats") or []
    must_keep = []
    if beats:
        must_keep.append({"id": "m1", "text": "开头 2 秒内出现人物和商品", "beat": beats[0]["id"], "confidence": 0.6})
    if len(beats) > 2:
        must_keep.append({"id": "m2", "text": "中段出现价格/卖点信息", "beat": beats[len(beats) // 2]["id"], "confidence": 0.55})
    if beats:
        must_keep.append({"id": "m3", "text": "结尾有明确的行动或结果", "beat": beats[-1]["id"], "confidence": 0.55})
    return {
        "version": 2,
        "mechanism": "demo_recreate",
        "mechanism_label": "Demo：结构保真占位梗卡",
        "template_type": "剧情对话",
        "confidence": 0.55,
        "must_keep": must_keep,
        "timing": {"punchline_beat": beats[-1]["id"] if beats else None, "punchline_at_s": beats[-1]["end_s"] if beats else None},
        "transferable": True,
        "replicability": 0.6,
        "risk_tags": ["demo 占位"],
        "source": {"degraded": True, "reason": "demo pipeline"},
    }


def build_gag(run: Any, skeleton: dict[str, Any]) -> dict[str, Any]:
    """Ask the MiniMax text model for a structured gag; fall back locally."""
    brief = str((run.inputs or {}).get("brief") or "").strip()
    beats = skeleton.get("beats") or []
    transcript = (skeleton.get("transcript") or [])[:24]
    transcript_text = "\n".join(f"- {x.get('start_s')}-{x.get('end_s')}s {x.get('text')}" for x in transcript)[:1600]
    summary = "\n".join(
        f"- {b['id']} {b['start_s']:.1f}-{b['end_s']:.1f}s [{b.get('function')}] 画面：{((b.get('visual') or {}).get('action') or '')[:90]}"
        for b in beats
    )
    prompt = f"""参考片结构：
{summary}

参考片台词/ASR：
{transcript_text or '（无可用台词）'}

用户/产品需求：
{brief or '无'}

{persona_mod.persona_instruction(run.advanced)}

请判断这条参考片靠什么机制成立，并给出 3-6 条必须保留、可被第三人检查的具体要求。
只输出 JSON：
{{
  "mechanism": "price_compare_punchline|status_contrast|misunderstanding|exaggeration|repetition|snatch|callout|testimonial|unboxing|none",
  "mechanism_label": "一句中文说明",
  "must_keep": [{{"text": "具体要求", "beat": "b0", "confidence": 0.0}}],
  "punchline_beat": "b0 或 null",
  "confidence": 0.0,
  "risk_tags": ["合规或执行风险"]
}}
must_keep 每条必须挂到上面真实存在的 beat；不要写空话。不要编造用户没有提供的原价、对比价、销量、功效或绝对化宣传。没有提供对比价时，只写活动价，不要自己补一个原价数字。"""
    data = llm.chat_json("你是广告片结构分析师。只输出 JSON，不要解释。", prompt, max_tokens=2400, temperature=0.2, text_model=_text_model(run))
    if not data:
        return _fallback_gag(skeleton)
    valid_beats = {b["id"] for b in beats}
    keeps = []
    for i, item in enumerate(data.get("must_keep") or []):
        beat = str(item.get("beat") or "")
        text = str(item.get("text") or "").strip()
        if not text or beat not in valid_beats:
            continue
        keeps.append({"id": f"m{i+1}", "text": persona_mod.neutralize_people(text, run.advanced)[:120], "beat": beat, "confidence": float(item.get("confidence") or 0.6)})
        if len(keeps) >= 6:
            break
    if not keeps:
        fallback = _fallback_gag(skeleton)
        fallback["mechanism"] = str(data.get("mechanism") or fallback["mechanism"])
        fallback["mechanism_label"] = str(data.get("mechanism_label") or fallback["mechanism_label"])
        fallback["confidence"] = float(data.get("confidence") or fallback["confidence"])
        fallback["source"] = {"model": llm.model_label(), "degraded": True, "reason": "LLM must_keep invalid"}
        return fallback
    if len(keeps) < 3:
        fallback = _fallback_gag(skeleton)
        for item in fallback["must_keep"]:
            if len(keeps) >= 3:
                break
            if all(item["beat"] != existing["beat"] for existing in keeps):
                keeps.append(item)
    return {
        "version": 2,
        "mechanism": str(data.get("mechanism") or "none"),
        "mechanism_label": str(data.get("mechanism_label") or ""),
        "template_type": "剧情对话",
        "confidence": float(data.get("confidence") or 0.6),
        "must_keep": keeps[:6],
        "timing": {"punchline_beat": data.get("punchline_beat"), "punchline_at_s": None},
        "transferable": True,
        "replicability": float(data.get("confidence") or 0.6),
        "risk_tags": list(data.get("risk_tags") or []),
        "source": {"model": llm.model_label(), "degraded": False},
    }


def _spoken_lines(brief: str) -> list[str]:
    """Turn a mixed brief into short, speakable lines for the demo pipeline.

    The real LLM script adapter will replace this. Until then, never let the
    model read the whole brief (including production instructions) as dialogue.
    """
    clauses = [part.strip(" ：:，,;；。\n") for part in re.split(r"[。；;，,\n]", brief)]
    keep = []
    for clause in clauses:
        if not clause or len(clause) < 2:
            continue
        # Production instructions are not dialogue.
        if re.search(r"保留|不要|要求|改成|更生活化|结构|动作|镜头|台词|信息|修改|参考", clause):
            continue
        if len(clause) > 24:
            clause = clause[:24]
        keep.append(clause)
    if not keep:
        keep = ["这个产品现在活动价 19.9", "不油腻，追剧吃刚好", "真的可以试试"]
    return keep[:3]


def _fallback_script(run: Any, skeleton: dict[str, Any], gag: dict[str, Any]) -> dict[str, Any]:
    brief = str((run.inputs or {}).get("brief") or "").strip()
    spoken = _spoken_lines(brief)
    beats = skeleton.get("beats") or []
    rows = []
    for i, beat in enumerate(beats):
        texts = spoken[:3] if len(beats) == 1 else [spoken[min(i, len(spoken) - 1)]] if spoken else ["这个产品现在活动价 19.9"]
        lines = []
        for j, text in enumerate(texts[:3]):
            speaker = "A" if j % 2 == 0 else "B"
            lines.append({"speaker": speaker, "text": text[:24], "chars": len(text[:24])})
        rows.append({
            "id": beat["id"], "function": beat.get("function"), "len_s": beat.get("len_s"),
            "cps": 4.0, "max_chars": max(12, int(float(beat.get("len_s") or 2) * 4.0)),
            "chars": sum(line["chars"] for line in lines), "fit": "ok", "lines": lines,
            "shot": (persona_mod.persona_label(run.advanced) + "在中景里自然交流，商品可见") if persona_mod.persona_label(run.advanced) else "人物在中景里自然交流，商品可见", "start_s": beat.get("start_s"), "end_s": beat.get("end_s"),
        })
    return {"version": 2, "beats": rows, "totals": {"duration_s": (skeleton.get("source") or {}).get("duration_s"), "chars": sum(r["chars"] for r in rows)}, "must_keep_map": {i["id"]: i.get("beat") for i in gag.get("must_keep") or []}, "compliance_flags": ["demo 文案，价格/功效需人工核对"], "source": {"degraded": True, "reason": "demo pipeline"}}


def build_script(run: Any, skeleton: dict[str, Any], gag: dict[str, Any]) -> dict[str, Any]:
    brief = str((run.inputs or {}).get("brief") or "").strip()
    advanced = run.advanced or {}
    beats = skeleton.get("beats") or []
    target = float(advanced.get("duration") or (skeleton.get("source") or {}).get("duration_s") or 8)
    transcript = (skeleton.get("transcript") or [])[:24]
    transcript_text = "\n".join(f"- {x.get('start_s')}-{x.get('end_s')}s {x.get('text')}" for x in transcript)[:1600]
    beat_text = "\n".join(
        f"- {b['id']} {b['start_s']:.1f}-{b['end_s']:.1f}s [{b.get('function')}] 画面：{((b.get('visual') or {}).get('action') or '')[:90]}"
        for b in beats
    )
    keeps = "\n".join(f"- [{k['beat']}] {k['text']}" for k in gag.get("must_keep") or [])
    prompt = f"""目标时长：{target:g}s；参考片 beat：
{beat_text}

参考片台词/ASR：
{transcript_text or '（无可用台词）'}

必须保留：
{keeps}

产品/需求：
{brief or '产品展示，突出卖点，最后引导购买'}

{persona_mod.persona_instruction(run.advanced)}

写一段可直接交给原生对白视频模型的中文脚本。要求：
- 只输出 JSON；
- 每个 beat 给出 1-3 行短台词，每行不超过 18 个汉字；
- 台词自然、像人说话，不要把产品说明/制作要求整段念出来；
- 保留用户给出的价格数字和 must_keep 的动作/信息；
- 不要编造未提供的原价、对比价、销量、功效或绝对化宣传；没有对比价就只写活动价；
- 尽量用 A/B 两个说话人，除非明显是单人场景；
- 如果存在模特设定，参考片人物只用于动作/构图，action 不得沿用原片性别/年龄/外貌；
- 每个 beat 给一个画面 action。
JSON:
{{"beats":[{{"id":"b0","lines":[{{"speaker":"A","text":"..."}}],"shot":"..."}}]}}"""
    data = llm.chat_json("你是广告片编剧。只输出 JSON，不要解释。", prompt, max_tokens=3600, temperature=0.45, text_model=_text_model(run))
    if not data or not isinstance(data.get("beats"), list):
        fallback = _fallback_script(run, skeleton, gag)
        fallback["source"] = {"degraded": True, "reason": "LLM script failed: " + (llm.LAST_ERROR or "empty response")}
        return fallback
    by_id = {str(item.get("id")): item for item in data["beats"] if isinstance(item, dict)}
    rows = []
    for beat in beats:
        item = by_id.get(beat["id"]) or {}
        lines = []
        for j, line in enumerate((item.get("lines") or [])[:3]):
            text = str((line or {}).get("text") or "").strip()
            if not text:
                continue
            text = text[:24]
            speaker = str((line or {}).get("speaker") or ("A" if j % 2 == 0 else "B"))
            lines.append({"speaker": speaker if speaker in {"A", "B"} else "A", "text": text, "chars": len(text)})
        if not lines:
            fallback = _fallback_script(run, skeleton, gag)
            fallback_row = next((r for r in fallback["beats"] if r["id"] == beat["id"]), None)
            lines = fallback_row["lines"] if fallback_row else [{"speaker": "A", "text": "这个产品现在活动价 19.9", "chars": 13}]
        rows.append({
            "id": beat["id"], "function": beat.get("function"), "len_s": beat.get("len_s"),
            "cps": 4.0, "max_chars": max(12, int(float(beat.get("len_s") or 2) * 4.0)),
            "chars": sum(line["chars"] for line in lines), "fit": "ok", "lines": lines,
            "shot": persona_mod.neutralize_people(str(item.get("shot") or "人物在中景里自然交流，商品可见"), run.advanced)[:120],
            "start_s": beat.get("start_s"), "end_s": beat.get("end_s"),
        })
    return {"version": 2, "beats": rows, "totals": {"duration_s": target, "chars": sum(r["chars"] for r in rows)}, "must_keep_map": {i["id"]: i.get("beat") for i in gag.get("must_keep") or []}, "compliance_flags": ["LLM 文案，价格/功效需人工核对"], "source": {"model": llm.model_label(), "degraded": False}}
