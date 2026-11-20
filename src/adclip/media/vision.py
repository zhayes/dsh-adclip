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
import time
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
# Every DSH bridge call of the current analysis: pass, frame count, status and
# elapsed seconds. Analysis copies this into the run so a degraded result can
# explain itself instead of showing one opaque error.
LAST_ATTEMPTS: list[dict[str, Any]] = []

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
    "cast": [{
      "key": "A",
      "role": "主角/同伴/路人",
      "appearance": "年龄段、性别、族裔、发型、面部特征（眼镜/胡须等），60字内",
      "wardrobe": "上装、下装、配饰，40字内，不写“身穿”",
      "props": "手中或身上的道具与持握方式，30字内",
      "expression": "当前可见表情，20字内",
      "gaze": "看镜头/看商品/看对方/低头，10字内"
    }],
    "action": "画面中可见动作，40字内",
    "tone": "说话语气，15字内，如夸张叫卖/急切追问/轻松调侃；没人在说话就留空",
    "product": "商品及可见包装，20字内；看不清写未识别商品",
    "product_appearance": "包装形态、颜色、材质，40字内；看不清留空",
    "product_position": "商品在画面中的位置或手持方式，20字内",
    "product_visibility": "主体/背景/部分遮挡/不可见",
    "scene": "场景，15字内",
    "background": "地点、环境元素、背景道具、天气与时间，80字内",
    "lighting": "光源方向、强弱、色温、阴影，40字内",
    "composition": "主体位置/前中后景/留白",
    "on_screen_text": "画面文字或价格，原文照抄，没有就空",
    "continuity": "与上一帧相比：同场景/换场景/同人物/换人物/不确定",
    "confidence": 0.0,
    "unclear": ["看不清的字段"]
  }]
}

示例（只示范写法，不要把示例内容写进输出）：
{"id":"b0","people":"1名男子","cast":[{"key":"A","role":"主角","appearance":"40岁左右亚洲男性，戴黑框眼镜，短寸头","wardrobe":"深蓝色西装外套，内搭白衬衫","props":"右手握黄色美工刀","expression":"期待微笑","gaze":"看镜头"}],"action":"右手持刀站在车厢红布前，准备剪彩","product":"棕色纸箱货物","product_appearance":"牛皮纸色纸箱，成摞码放","product_position":"画面中央车斗上","product_visibility":"主体","scene":"货车旁","background":"明亮蓝天白云下的工业厂房前水泥空地，右侧停着白色厢式货车","lighting":"日光充足，右侧偏亮，阴影短","composition":"人物居左，货车居右，画面上方留白","confidence":0.9}

规则：
- 商品名只有包装清晰可读时才填；不要编造品牌、价格、功效。
- on_screen_text 不翻译、不补价格。
- cast 每个画面中的人一条；同一人物在不同帧必须用同一个 key（A/B/C），不要按帧重新编号。
- 人物只写看得见的外形特征；看不清的特征留空，不要猜身份、职业、姓名。
- wardrobe 不写“身穿”，只写衣物本身；看不清就留空。
- props 只写手里拿着或身上佩戴的道具，写清哪只手、怎么拿。
- expression/gaze 只写看得见的内容，不写性格或心理活动。
- background 写环境本身（地点、环境元素、背景道具、天气），不要重复人物动作。
- lighting 没有明确线索就留空，不要用“自然光”这类套话。
- tone 只在人物确实在说话时判断，参考嘴型和张嘴/笑/皱眉等可见线索；多帧连起来判断情绪走向。
- 多帧一起看可以用前后帧判断连续性，但不能把不同帧的内容混到同一帧。
- 同一人物、同一场景在不同帧用同样的词描述，方便跨帧合并。"""

DESCRIBE_PROMPT = """你是广告片分镜描述器。输入是同一参考片按时间顺序排列的关键帧，按镜头分组，并附该镜台词。
为每个镜头写一段连贯的中文画面描述，供视频生成模型复现这一镜。
只描述画面中确实看得见的内容；不根据 brief、商品名或常识补全；不编造品牌、价格、功效。
每镜一段，id 必须对应输入的镜头 id，不要新增镜头。按这个顺序写成一段连续的文字：
1) 人物动作的过程（先做什么、再做什么，带上手部动作）；
2) 表情、视线和情绪变化；
3) 环境、背景元素和光线；
4) 构图与主体在画面中的位置。
不要描写人物的长相、年龄、发型、服装、配饰和道具（这些字段会单独提供）；不要复述台词原文。
不要写“镜头1”“画面：”这类标题，不要用列表或分条。
每段 120–200 字，2–4 句，句子之间用逗号或句号自然衔接；没有人物就只写环境和动作过程。
看不清的细节略过，不要猜。
只输出 JSON，不要 markdown：{"beats":[{"id":"b0","description":"..."}]}"""


def available() -> bool:
    if os.environ.get("ADSTUDIO_VISION", "1") == "0":
        return False
    return (
        bool(os.environ.get("MINIMAX_API_KEY", "").strip())
        or ark_text.available()
        or bool(DSH_VISION_URL)
    )


def reset_attempts() -> None:
    """Forget the previous analysis' bridge calls before a new ladder run."""
    LAST_ATTEMPTS.clear()


def chain_signature() -> str:
    """Which vision providers can run, in ladder order.

    Part of the analysis cache key: switching a provider off must not replay a
    cached result that provider produced.
    """
    parts: list[str] = []
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        parts.append("minimax")
    arks = [str(row.get("short") or row.get("id") or "") for row in ark_text.vision_models()]
    if arks:
        parts.append("ark:" + ",".join(arks))
    if DSH_VISION_URL:
        parts.append("dsh")
    return "+".join(parts) if parts else "none"


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


def cast_description(item: dict[str, Any]) -> str:
    """One readable line for a cast entry: look, outfit, props.

    Renderers and the UI both want a sentence rather than four adjacent keys,
    and the H3 prompt deliberately uses the shorter ``people`` summary instead
    so a replaced person cannot inherit the reference person's appearance.
    """
    parts: list[str] = []
    look = str(item.get("appearance") or "").strip()
    if look:
        parts.append(look)
    outfit = str(item.get("wardrobe") or "").strip().lstrip("穿")
    if outfit:
        parts.append("身穿" + outfit)
    props = str(item.get("props") or "").strip()
    if props:
        parts.append(props)
    return "，".join(parts)[:160]


def _normalize_cast(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not isinstance(value, list):
        return items
    seen: set[str] = set()
    for index, raw in enumerate(value[:4]):
        if isinstance(raw, str):
            raw = {"appearance": raw}
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip().upper()[:2] or chr(65 + index)
        if key in seen:
            key = chr(65 + len(items))
        seen.add(key)
        item = {
            "key": key,
            "role": str(raw.get("role") or "")[:12],
            "appearance": str(raw.get("appearance") or "")[:90],
            "wardrobe": str(raw.get("wardrobe") or "")[:60],
            "props": str(raw.get("props") or "")[:50],
            "expression": str(raw.get("expression") or "")[:40],
            "gaze": str(raw.get("gaze") or "")[:20],
        }
        item["description"] = cast_description(item)
        if item["description"]:
            items.append(item)
    return items


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
        people = str(row.get("people") or row.get("people_relation") or "")[:160]
        cast = _normalize_cast(row.get("cast"))
        if not cast and people:
            # Older prompt revisions only returned a one-line people summary;
            # keep it usable as the single cast row instead of dropping it.
            cast = [{"key": "A", "role": "主角", "appearance": "", "wardrobe": "", "props": "",
                     "expression": "", "gaze": "", "description": people}]
        out[frame_id] = {
            "shot_size": str(row.get("shot_size") or "")[:30],
            "action": str(row.get("action") or "")[:240],
            "expression": str(row.get("expression") or "")[:60],
            "tone": str(row.get("tone") or "")[:60],
            "people": people,
            "cast": cast,
            "product": str(row.get("product") or "")[:120],
            "product_appearance": str(row.get("product_appearance") or "")[:80],
            "product_position": str(row.get("product_position") or "")[:60],
            "scene": str(row.get("scene") or "")[:120],
            "background": str(row.get("background") or "")[:160],
            "lighting": str(row.get("lighting") or "")[:100],
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


def _normalize_beats(value: dict[str, Any] | None, labels: list[str]) -> dict[str, str]:
    """Per-shot description text keyed by beat id, ignoring frame labels."""
    rows = (value or {}).get("beats")
    if not isinstance(rows, list):
        return {}
    wanted = set(labels)
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        beat_id = str(row.get("id") or "")
        if beat_id not in wanted:
            continue
        text = str(row.get("description") or "").strip()
        if text:
            out[beat_id] = text[:400]
    return out


def _beat_manifest(beats: list[dict[str, Any]], frames: list[dict[str, Any]]) -> str:
    rows = []
    for beat in beats:
        beat_id = str(beat.get("id") or "")
        ids = [str(frame.get("id")) for frame in frames if str(frame.get("beat_id") or "") == beat_id]
        if not ids:
            continue
        line = f"镜头 {beat_id}（{beat.get('start_s', 0)}–{beat.get('end_s', 0)}s），关键帧：{'、'.join(ids)}"
        text = str(beat.get("dialogue_text") or "").strip()
        if text:
            line += "；台词：" + text[:120]
        rows.append(line)
    return "\n".join(rows)


def _analyze_minimax(frames: list[dict[str, Any]], *, prompt: str = VISION_PROMPT, normalize=_normalize_rows) -> dict[str, Any]:
    global LAST_ERROR
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    labels = [str(frame.get("id") or "") for frame in frames]
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt + "\n\n" + _manifest(frames)}]
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
            json={"model": MODEL, "messages": [{"role": "user", "content": content}], "max_tokens": 6000, "temperature": 0.15},
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
    rows = normalize(value, labels)
    if rows:
        LAST_ERROR = ""
    return rows


def _analyze_ark(frames: list[dict[str, Any]], models: list[dict[str, Any]] | None = None, *, prompt: str = VISION_PROMPT, normalize=_normalize_rows) -> dict[str, Any]:
    """Doubao-Seed-2.1 on Ark, tried in the configured pro/turbo/lite order."""
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL
    labels = [str(frame.get("id") or "") for frame in frames]
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt + "\n\n" + _manifest(frames)}]
    for frame in frames:
        frame_id = str(frame.get("id") or "")
        content.append({"type": "text", "text": f"关键帧 {frame_id}，时间 {frame.get('start_s', 0)}-{frame.get('end_s', 0)} 秒："})
        try:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(Path(str(frame["path"])))}})
        except Exception:
            continue
    errors: list[str] = []
    candidates = models if models is not None else _ark_order()
    if not candidates:
        # Silently returning an empty dict here used to erase the reason the
        # whole rung was skipped, leaving the user with the DSH error only.
        LAST_ERROR = "方舟视觉模型未启用（设置 → 文本/视觉调度 里勾选 Doubao-Seed-2.1）"
        return {}
    for row in candidates:
        try:
            result = ark_text.chat(
                "",
                [{"role": "user", "content": content}],
                model=str(row["id"]),
                max_tokens=6000,
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
        rows = normalize(value, labels)
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


def _env_num(name: str, default: float) -> float:
    try:
        value = float(str(os.environ.get(name, "") or default))
    except (TypeError, ValueError):
        return float(default)
    return value if value > 0 else float(default)


def _dsh_payload(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for frame in frames:
        frame_id = str(frame.get("id") or "")
        try:
            data = base64.b64encode(Path(str(frame["path"])).read_bytes()).decode("ascii")
        except Exception:
            continue
        payload.append({"id": frame_id, "mediaType": "image/jpeg", "data": data, "name": f"{frame_id}.jpg"})
    return payload


def _cast_hint(rows: dict[str, Any]) -> str:
    """Keep cast keys stable when one shot is labelled across several calls."""
    seen: dict[str, str] = {}
    for row in rows.values():
        if not isinstance(row, dict):
            continue
        for item in row.get("cast") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip().upper()
            text = str(item.get("description") or "").strip()
            if key and text and key not in seen:
                seen[key] = text[:80]
    if not seen:
        return ""
    return "已分配人物（沿用同一个 key，不要重新编号）：" + "；".join(
        f"{key}={text}" for key, text in sorted(seen.items())
    )


def _dsh_once(
    chunk: list[dict[str, Any]],
    *,
    prompt: str,
    normalize,
    labels: list[str],
    max_tokens: int,
    timeout: float,
    hint: str,
) -> tuple[dict[str, Any], str]:
    payload = _dsh_payload(chunk)
    if not payload:
        raise RuntimeError("no readable frames")
    body = prompt + "\n\n" + _manifest(chunk)
    if hint:
        body += "\n" + hint
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
        response = client.post(
            DSH_VISION_URL,
            json={"frames": payload, "prompt": body, "maxTokens": max_tokens},
        )
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:240]}")
    data = response.json().get("dsh") or {}
    text = _strip(str(data.get("text") or ""))
    value = _extract_json(text)
    if value is None:
        raise RuntimeError(f"no JSON in {len(text)} chars")
    rows = normalize(value, labels)
    if not rows:
        raise RuntimeError(f"JSON has no usable rows in {len(text)} chars")
    return rows, str(data.get("model") or "")


def _dsh_chunks(frames: list[dict[str, Any]], size: int, group_key: str | None) -> list[list[dict[str, Any]]]:
    size = max(1, int(size))
    if not group_key:
        return [frames[index:index + size] for index in range(0, len(frames), size)]
    # A shot's frames stay in one call: the description is written per shot, and
    # splitting a shot would describe it twice from half its evidence.
    order: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        key = str(frame.get(group_key) or frame.get("id") or "")
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(frame)
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for key in order:
        items = grouped[key]
        if current and len(current) + len(items) > size:
            chunks.append(current)
            current = []
        current.extend(items)
    if current:
        chunks.append(current)
    return chunks


def _analyze_dsh(
    frames: list[dict[str, Any]],
    *,
    prompt: str = VISION_PROMPT,
    normalize=_normalize_rows,
    batch_size: int = 4,
    tokens_per_frame: int = 3000,
    deadline_s: float = 240.0,
    group_key: str | None = None,
    label: str = "tag",
) -> dict[str, Any]:
    """Label keyframes through the Host bridge in budgeted batches.

    The bridge is not streaming, so one HTTP read covers one whole generation,
    and the same call swings between 25s and 80s depending on load. Packing every
    frame into a single request means one slow token drops every label, so the
    ladder sends small batches, bisects a batch that fails, and stops at a total
    deadline keeping whatever was labelled. Partial labels beat no labels.
    """
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL
    if not DSH_VISION_URL:
        return {}
    usable = [frame for frame in frames if Path(str(frame.get("path") or "")).is_file()]
    if not usable:
        LAST_ERROR = "DSH vision: no readable frames"
        return {}
    timeout = _env_num("ADSTUDIO_DSH_VISION_TIMEOUT", 120.0)
    deadline = time.monotonic() + max(1.0, float(deadline_s))
    rows: dict[str, Any] = {}
    attempts: list[dict[str, Any]] = []
    failures: list[str] = []
    missed: list[str] = []
    model_used = ""

    def run(chunk: list[dict[str, Any]], depth: int = 0) -> None:
        nonlocal model_used
        if time.monotonic() >= deadline:
            attempts.append({"pass": label, "frames": len(chunk), "status": "skipped", "error": "超过总时限", "seconds": 0.0})
            missed.extend(str(frame.get("id") or "") for frame in chunk)
            return
        # The describe contract is keyed by shot, the tag contract by frame: a
        # batched call must label what the caller's normalizer expects.
        labels = list(dict.fromkeys(
            str(frame.get(group_key) or frame.get("id") or "") for frame in chunk
        ))
        started = time.monotonic()
        try:
            batch_rows, model = _dsh_once(
                chunk,
                prompt=prompt,
                normalize=normalize,
                labels=labels,
                max_tokens=min(16000, max(4000, int(tokens_per_frame) * len(chunk))),
                timeout=timeout,
                hint=_cast_hint(rows) if normalize is _normalize_rows else "",
            )
        except Exception as exc:  # noqa: BLE001
            attempts.append({
                "pass": label,
                "frames": len(chunk),
                "status": "failed",
                "error": str(exc)[:200],
                "seconds": round(time.monotonic() - started, 1),
            })
            failures.append(f"{len(chunk)} 帧: {str(exc)[:120]}")
            if len(chunk) > 1 and depth < 2:
                middle = len(chunk) // 2
                run(chunk[:middle], depth + 1)
                run(chunk[middle:], depth + 1)
            else:
                missed.extend(labels)
            return
        rows.update(batch_rows)
        if model:
            model_used = model
        attempts.append({
            "pass": label,
            "frames": len(chunk),
            "status": "ok",
            "error": "",
            "seconds": round(time.monotonic() - started, 1),
        })

    for chunk in _dsh_chunks(usable, batch_size, group_key):
        run(chunk)
    LAST_ATTEMPTS.extend(attempts)
    del LAST_ATTEMPTS[:-40]
    if rows:
        LAST_PROVIDER = "dsh"
        LAST_MODEL = model_used
        # Partial success is still success; missing frames are reported through
        # LAST_ATTEMPTS so analysis can warn without discarding the labels.
        LAST_ERROR = ""
        return rows
    LAST_ERROR = ("DSH vision: " + " | ".join(failures))[:300] if failures else "DSH vision: 没有可用的标注"
    return {}


def describe_beats(
    frames: list[dict[str, Any]],
    beats: list[dict[str, Any]],
    *,
    max_frames: int = 14,
) -> dict[str, str]:
    """One flowing description per shot, keyed by beat id. Empty means unavailable.

    Runs on the same ladder as the tag pass but with a different contract: the
    model reads every frame of a shot together and writes a paragraph, because a
    renderer can only concatenate fields and a prompt needs prose. Appearance is
    deliberately excluded so a replaced person cannot inherit the reference look.
    """
    global LAST_ERROR, LAST_PROVIDER, LAST_MODEL
    LAST_ERROR = ""
    if os.environ.get("ADSTUDIO_DESCRIBE", "1") == "0":
        return {}
    selected = [f for f in frames[:max_frames] if Path(str(f.get("path") or "")).is_file()]
    labels = [str(beat.get("id")) for beat in beats if str(beat.get("id") or "")]
    if not selected or not labels:
        return {}
    manifest = _beat_manifest(beats, selected)
    if not manifest:
        return {}
    prompt = DESCRIBE_PROMPT + "\n\n" + manifest
    errors: list[str] = []
    if os.environ.get("MINIMAX_API_KEY", "").strip():
        try:
            rows = _analyze_minimax(selected, prompt=prompt, normalize=_normalize_beats)
            if rows:
                LAST_PROVIDER = "minimax"
                LAST_MODEL = MODEL
                return {key: value for key, value in rows.items() if key in labels}
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"MiniMax: {type(exc).__name__}: {exc}")
    else:
        errors.append("MiniMax: 未配置 MINIMAX_API_KEY")
    if ark_text.available():
        try:
            rows = _analyze_ark(selected, prompt=prompt, normalize=_normalize_beats)
            if rows:
                return {key: value for key, value in rows.items() if key in labels}
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Ark: {type(exc).__name__}: {exc}")
    else:
        errors.append("Ark: 未配置 ARK_API_KEY")
    if DSH_VISION_URL:
        try:
            rows = _analyze_dsh(
                selected,
                prompt=prompt,
                normalize=_normalize_beats,
                batch_size=int(_env_num("ADSTUDIO_DSH_DESCRIBE_BATCH", 6)),
                tokens_per_frame=1000,
                deadline_s=_env_num("ADSTUDIO_DSH_DESCRIBE_DEADLINE", 180.0),
                group_key="beat_id",
                label="describe",
            )
            if rows:
                return {key: value for key, value in rows.items() if key in labels}
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"DSH: {type(exc).__name__}: {exc}")
    LAST_ERROR = " | ".join(errors)[:400] or "没有可用的描述模型"
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
    else:
        errors.append("MiniMax: 未配置 MINIMAX_API_KEY")
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
    else:
        errors.append("Ark: 未配置 ARK_API_KEY")
    if DSH_VISION_URL:
        try:
            rows = _analyze_dsh(
                usable,
                batch_size=int(_env_num("ADSTUDIO_DSH_VISION_BATCH", 4)),
                deadline_s=_env_num("ADSTUDIO_DSH_VISION_DEADLINE", 240.0),
                label="tag",
            )
            if rows:
                return rows
            if LAST_ERROR:
                errors.append(LAST_ERROR)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"DSH: {type(exc).__name__}: {exc}")
    LAST_ERROR = " | ".join(errors)[:600] or "没有可用的视觉模型"
    return {}
