"""Reference keyframe analysis.

Fallback ladder (first success wins, failure never blocks analysis):

1. MiniMax-M3 (``MINIMAX_API_KEY``)
2. Doubao-Seed-2.1 pro/turbo/lite on Volcengine Ark (``ARK_API_KEY``)
3. DSH vision bridge (an image-capable DSH model through the Host)
4. heuristic analysis in ``pipeline/analyze.py``

Every path shares ``VISION_PROMPT`` and the same JSON contract.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from ..providers import ark_text

BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
MODEL = os.environ.get("ADSTUDIO_VISION_MODEL", "MiniMax-M3")
_CHAT_URL = (os.environ.get("ADSTUDIO_DSH_CHAT_URL") or "").strip()
DSH_VISION_URL = (
    os.environ.get("ADSTUDIO_DSH_VISION_URL", "").strip()
    or (_CHAT_URL[:-len("/chat")] + "/vision" if _CHAT_URL.endswith("/chat") else "")
)
LAST_ERROR = ""
LAST_PROVIDER = ""
LAST_MODEL = ""
LAST_ESCALATED = 0

VISION_PROMPT = """你是广告片分镜视觉标签器。输入是同一参考片按时间顺序排列的关键帧。
只描述画面中确实看得见的内容，不根据 brief、商品名、常识或上下文补全。
每帧只输出一条，id 必须对应输入的关键帧 id。看不清的字段留空；无法判断写入 unclear。
只输出 JSON，不要 markdown，不要解释。

输出结构：
{
  "frames": [{
    "id": "b0",
    "shot_size": "特写/近景/中景/全景/远景",
    "camera_angle": "平视/俯拍/仰拍/侧拍",
    "camera_movement": "固定/推/拉/摇/移/跟/手持",
    "people": "人数与人物关系，20字内",
    "action": "画面中可见动作，20字内",
    "product": "商品及可见包装，20字内；看不清写未识别商品",
    "product_visibility": "主体/背景/部分遮挡/不可见",
    "scene": "场景，15字内",
    "composition": "主体位置/前中后景/留白",
    "on_screen_text": "画面文字或价格，原文照抄，没有就空",
    "continuity": "与上一帧相比：同场景/换场景/同人物/换人物/不确定",
    "confidence": 0.0,
    "unclear": ["看不清的字段"]
  }]
}
规则：
- 商品名只有包装清晰可读时才填；不要编造品牌、价格、功效。
- on_screen_text 不翻译、不补价格。
- 人物只写画面中可见的人数/关系，不推测身份。
- 多帧一起看可以用前后帧判断连续性，但不能把不同帧的内容混到同一帧。
- 标签尽量短，方便后续生成使用。"""


def available() -> bool:
    if os.environ.get("ADSTUDIO_VISION", "1") == "0":
        return False
    return (
        bool(os.environ.get("MINIMAX_API_KEY", "").strip())
        or ark_text.available()
        or bool(DSH_VISION_URL)
    )


def _strip(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _data_uri(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _manifest(frames: list[dict[str, Any]]) -> str:
    rows = []
    for frame in frames:
        rows.append(f"关键帧 {frame.get('id')}，时间 {frame.get('start_s', 0)}-{frame.get('end_s', 0)} 秒")
    return "\n".join(rows)


def _extract_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _normalize_rows(value: dict[str, Any] | None, labels: list[str]) -> dict[str, dict[str, Any]]:
    rows = (value or {}).get("frames")
    if not isinstance(rows, list):
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
            "people": str(row.get("people") or row.get("people_relation") or "")[:100],
            "product": str(row.get("product") or "")[:120],
            "scene": str(row.get("scene") or "")[:80],
            "on_screen_text": str(row.get("on_screen_text") or "")[:120],
            "camera_angle": str(row.get("camera_angle") or "")[:30],
            "camera_movement": str(row.get("camera_movement") or "")[:30],
            "composition": str(row.get("composition") or "")[:120],
            "continuity": str(row.get("continuity") or "")[:60],
            "product_visibility": str(row.get("product_visibility") or "")[:30],
            "confidence": row.get("confidence") if isinstance(row.get("confidence"), (int, float)) else None,
            "unclear": [str(item)[:40] for item in (row.get("unclear") or []) if str(item).strip()][:8] if isinstance(row.get("unclear"), list) else [],
        }
    return out


def _analyze_minimax(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    global LAST_ERROR
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    labels = [str(frame.get("id") or "") for frame in frames]
    content: list[dict[str, Any]] = [{"type": "text", "text": VISION_PROMPT + "\n\n" + _manifest(frames)}]
    for frame in frames:
        frame_id = str(frame.get("id") or "")
        content.append({"type": "text", "text": f"关键帧 {frame_id}，时间 {frame.get('start_s', 0)}-{frame.get('end_s', 0)} 秒："})
        try:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(Path(str(frame["path"])))}})
        except Exception:
            continue
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
        response = client.post(
            f"{BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": content}], "max_tokens": 4000, "temperature": 0.15},
        )
    if response.status_code >= 400:
        LAST_ERROR = f"MiniMax HTTP {response.status_code}: {response.text[:240]}"
        return {}
    data = response.json()
    raw = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    text = _strip(str(raw))
    value = _extract_json(text)
    if value is None:
        LAST_ERROR = f"MiniMax returned no JSON in {len(text)} chars"
        return {}
    rows = _normalize_rows(value, labels)
    if rows:
        LAST_ERROR = ""
    return rows


def _analyze_ark(frames: list[dict[str, Any]], models: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Doubao-Seed-2.1 on Ark, tried in the configured pro/turbo/lite order."""
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL
    labels = [str(frame.get("id") or "") for frame in frames]
    content: list[dict[str, Any]] = [{"type": "text", "text": VISION_PROMPT + "\n\n" + _manifest(frames)}]
    for frame in frames:
        frame_id = str(frame.get("id") or "")
        content.append({"type": "text", "text": f"关键帧 {frame_id}，时间 {frame.get('start_s', 0)}-{frame.get('end_s', 0)} 秒："})
        try:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(Path(str(frame["path"])))}})
        except Exception:
            continue
    errors: list[str] = []
    for row in (models if models is not None else _ark_order()):
        try:
            result = ark_text.chat(
                "",
                [{"role": "user", "content": content}],
                model=str(row["id"]),
                max_tokens=4000,
                temperature=0.15,
                thinking=False,
                timeout=120.0,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{row['short']}: {exc}"[:200])
            continue
        text = str(result.get("text") or "")
        value = _extract_json(text)
        if value is None:
            errors.append(f"{row['short']}: no JSON in {len(text)} chars")
            continue
        rows = _normalize_rows(value, labels)
        if rows:
            LAST_PROVIDER = "ark"
            LAST_MODEL = str(result.get("model") or ark_text.model_id(row))
            LAST_ERROR = ""
            return rows
        errors.append(f"{row['short']}: JSON has no frames[]")
    LAST_ERROR = " | ".join(errors)[:400]
    return {}


def _ark_order() -> list[dict[str, Any]]:
    """Cheapest capable model first, unless the operator pins the old order."""
    rows = ark_text.vision_models()
    if os.environ.get("ADSTUDIO_VISION_CHEAP_FIRST", "1") != "1":
        return list(rows)
    rank = {"lite": 0, "turbo": 1, "pro": 2}
    return sorted(rows, key=lambda row: rank.get(str(row.get("short") or ""), 9))


def _needs_review(item: dict[str, Any]) -> bool:
    """Frames worth a second look with the stronger model."""
    unclear = {str(value) for value in item.get("unclear") or []}
    if unclear & {"product", "on_screen_text"}:
        return True
    if str(item.get("product_visibility") or "") in {"主体", "部分遮挡"}:
        return True
    product = str(item.get("product") or "").strip()
    return not product or product in {"未识别商品"}


def _escalate(frames: list[dict[str, Any]], rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Re-read at most four doubtful frames with the pro model."""
    global LAST_ESCALATED
    LAST_ESCALATED = 0
    if os.environ.get("ADSTUDIO_VISION_ESCALATE", "1") != "1":
        return rows
    pro = next((row for row in ark_text.vision_models() if str(row.get("short")) == "pro"), None)
    if pro is None:
        return rows
    flagged = [frame for frame in frames if _needs_review(rows.get(str(frame.get("id"))) or {})][:4]
    if not flagged:
        return rows
    extra = _analyze_ark(flagged, models=[pro])
    if extra:
        rows.update(extra)
        LAST_ESCALATED = len(extra)
    return rows


def _analyze_dsh(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL
    if not DSH_VISION_URL:
        return {}
    labels = [str(frame.get("id") or "") for frame in frames]
    payload_frames = []
    for frame in frames:
        frame_id = str(frame.get("id") or "")
        try:
            data = base64.b64encode(Path(str(frame["path"])).read_bytes()).decode("ascii")
        except Exception:
            continue
        payload_frames.append({"id": frame_id, "mediaType": "image/jpeg", "data": data, "name": f"{frame_id}.jpg"})
    if not payload_frames:
        LAST_ERROR = "DSH vision: no readable frames"
        return {}
    try:
        with httpx.Client(timeout=httpx.Timeout(float(os.environ.get("ADSTUDIO_DSH_VISION_TIMEOUT", "45")), connect=10.0)) as client:
            response = client.post(
                DSH_VISION_URL,
                json={"frames": payload_frames, "prompt": VISION_PROMPT + "\n\n" + _manifest(frames), "maxTokens": 4000},
            )
        if response.status_code >= 400:
            LAST_ERROR = f"DSH vision HTTP {response.status_code}: {response.text[:240]}"
            return {}
        data = response.json().get("dsh") or {}
        text = _strip(str(data.get("text") or ""))
        value = _extract_json(text)
        if value is None:
            LAST_ERROR = f"DSH vision returned no JSON in {len(text)} chars"
            return {}
        rows = _normalize_rows(value, labels)
        if rows:
            LAST_PROVIDER = "dsh"
            LAST_MODEL = str(data.get("model") or "")
            LAST_ERROR = ""
        return rows
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR = f"DSH vision: {type(exc).__name__}: {exc}"[:300]
        return {}


def analyze_frames(frames: list[dict[str, Any]], *, max_frames: int = 6) -> dict[str, dict[str, Any]]:
    """Return visual tags keyed by beat id. Empty dict means unavailable."""
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL, LAST_ESCALATED
    LAST_ERROR = ""
    LAST_PROVIDER = ""
    LAST_MODEL = ""
    LAST_ESCALATED = 0
    if not frames:
        return {}
    selected = frames[:max_frames]
    usable = [f for f in selected if Path(str(f.get("path") or "")).is_file()]
    if not usable:
        return {}
    errors: list[str] = []
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        try:
            rows = _analyze_minimax(usable)
            if rows:
                LAST_PROVIDER = "minimax"
                LAST_MODEL = MODEL
                return rows
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"MiniMax: {type(exc).__name__}: {exc}")
    if ark_text.available():
        try:
            rows = _analyze_ark(usable)
            if rows:
                first_model = LAST_MODEL
                rows = _escalate(usable, rows)
                if LAST_ESCALATED:
                    LAST_MODEL = f"{first_model}+pro"
                return rows
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Ark: {type(exc).__name__}: {exc}")
    if DSH_VISION_URL:
        try:
            rows = _analyze_dsh(usable)
            if rows:
                return rows
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"DSH: {type(exc).__name__}: {exc}")
    LAST_ERROR = " | ".join(errors)[:600] or "没有可用的视觉模型"
    return {}
