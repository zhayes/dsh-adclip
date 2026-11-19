"""Deterministic reading of the free-text brief.

The operator keeps writing free text; this module only extracts what a prompt
must state explicitly (text cleanup, background music, prices, a product hint)
so the renderers do not have to guess. It never rewrites the brief and never
calls a model: anything it does not understand stays in `brief` and is still
passed to the prompt as production notes.
"""
from __future__ import annotations

import re
from typing import Any

_CLEAN_TEXT = re.compile(
    r"(?:去掉|删掉|去除|不要|别加|取消).{0,6}(?:字幕|大字报|文字|贴纸|角标|水印|文案)|镜头干净|画面干净"
)
_BGM = re.compile(r"(?:背景音乐|BGM|配乐|音乐)", re.IGNORECASE)
_BGM_OFF = re.compile(r"(?:不要|去掉|不用|别加|无|取消).{0,4}(?:背景音乐|BGM|配乐|音乐)", re.IGNORECASE)
_PRICE = re.compile(r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千两]+)\s*(?:元|块钱|块\d?|折|多)")
_PRODUCT = re.compile(r"(?:商品|产品|货)(?:名称|名)?(?:改成|改为|换成|换为|是)[「\"']?([^，。,.\n「」\"']{2,20})")
_QUOTED = re.compile(r"[「『“\"]([^」』”\"]{2,40})[」』”\"]")


def derive(brief: str, advanced: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured requirements for the prompt renderers."""
    advanced = advanced or {}
    text = str(brief or "")
    persona = advanced.get("persona") if isinstance(advanced.get("persona"), dict) else {}
    no_bgm = True
    if _BGM.search(text) and not _BGM_OFF.search(text):
        no_bgm = False
    product = _PRODUCT.search(text)
    return {
        "brief": text.strip(),
        "clean_text": bool(_CLEAN_TEXT.search(text)) or bool(advanced.get("suppress_on_screen_text")),
        "no_bgm": no_bgm,
        "prices": list(dict.fromkeys(match.strip() for match in _PRICE.findall(text)))[:4],
        "product_hint": (product.group(1).strip() if product else ""),
        "quoted": [line.strip() for line in _QUOTED.findall(text) if line.strip()][:4],
        "persona": persona,
    }
