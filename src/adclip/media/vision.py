"""MiniMax M3 vision analysis for reference keyframes.

This is optional and uses the same MiniMax key as text/video. It never blocks a
run: failures return no visual tags and the heuristic analysis still proceeds.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
MODEL = os.environ.get("ADSTUDIO_VISION_MODEL", "MiniMax-M3")
LAST_ERROR = ""


def available() -> bool:
    if os.environ.get("ADSTUDIO_VISION", "1") == "0":
        return False
    return bool(os.environ.get("MINIMAX_API_KEY", "").strip())


def _strip(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _data_uri(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def analyze_frames(frames: list[dict[str, Any]], *, max_frames: int = 6) -> dict[str, dict[str, Any]]:
    """Return visual tags keyed by beat id. Empty dict means unavailable."""
    global LAST_ERROR
    LAST_ERROR = ""
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key or not frames:
        return {}
    selected = frames[:max_frames]
    usable = [f for f in selected if Path(str(f.get("path") or "")).is_file()]
    if not usable:
        return {}
    labels = []
    content: list[dict[str, Any]] = []
    prompt = (
        "你是广告片视觉分析师。按顺序分析这些参考片关键帧，只描述画面中确实看得见的内容。"
        "输出 JSON：{\"frames\":[{\"id\":\"b0\",\"shot_size\":\"景别\",\"action\":\"人物/动作\","
        "\"people\":\"人数/关系\",\"product\":\"商品及可见包装\",\"scene\":\"场景\","
        "\"on_screen_text\":\"画面文字/价格\"}]}。"
        "看不清的字段留空字符串，不要编造。"
    )
    content.append({"type": "text", "text": prompt})
    for frame in usable:
        label = str(frame.get("id") or "")
        labels.append(label)
        content.append({"type": "text", "text": f"关键帧 {label}，时间 {frame.get('start_s', 0)}-{frame.get('end_s', 0)} 秒："})
        try:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(Path(str(frame["path"])))}})
        except Exception:
            continue
    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            response = client.post(
                f"{BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": [{"role": "user", "content": content}], "max_tokens": 4000, "temperature": 0.15},
            )
        if response.status_code >= 400:
            LAST_ERROR = f"HTTP {response.status_code}: {response.text[:240]}"
            return {}
        data = response.json()
        raw = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        text = _strip(str(raw))
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            LAST_ERROR = f"no JSON in {len(text)} chars"
            return {}
        value = json.loads(text[start:end + 1])
        rows = value.get("frames") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            LAST_ERROR = "JSON has no frames[]"
            return {}
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            frame_id = str(row.get("id") or "")
            if frame_id not in labels:
                continue
            out[frame_id] = {
                "shot_size": str(row.get("shot_size") or "")[:30],
                "action": str(row.get("action") or "")[:200],
                "people": str(row.get("people") or "")[:80],
                "product": str(row.get("product") or "")[:120],
                "scene": str(row.get("scene") or "")[:80],
                "on_screen_text": str(row.get("on_screen_text") or "")[:120],
            }
        return out
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR = f"{type(exc).__name__}: {exc}"[:300]
        return {}
