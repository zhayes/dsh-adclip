"""Speech timing rules shared by the script writer and the prompt renderer.

Four Chinese characters per second is the pace of a natural ad read. A model
speaks comfortably up to about five and a half, so a slot that only fits at
that faster pace is still allowed. Beyond that the line is physically
impossible: the clip ends before the sentence does, which is exactly the
failure this module exists to prevent.

The last line always ends a moment before the shot does, so a cut never clips
the tail of a word.
"""
from __future__ import annotations

DEFAULT_CPS = 4.0
MAX_CPS = 5.5
# Budgeting ceiling. Text is written for this pace, not the physical maximum: a
# line planned at 5.5 chars/s has no slack, and the model's last words land
# after the cut.
BUDGET_CPS = 4.6
PACE_FLOOR = 3.2
GRACE = 1.15
SINGLE_GRACE = 1.5
MIN_LINE_S = 0.7
LINE_GAP_S = 0.2
TAIL_S = 0.45
MIN_LINE_CHARS = 4
_PUNCT = "，。！？、；：,.!?;:的了呢啊吧呀嘛哦着过"


def speak_seconds(text: str, cps: float = DEFAULT_CPS) -> float:
    """Minimum time needed to say `text` at a natural pace."""
    return max(MIN_LINE_S, len(str(text or "")) / max(0.5, cps))


def measured_cps(rows: list[dict[str, Any]] | None) -> float | None:
    """Speaking rate of the reference dialogue, in characters per spoken second."""
    spoken = 0.0
    chars = 0
    for row in rows or []:
        try:
            span = float(row.get("end_s") or 0) - float(row.get("start_s") or 0)
        except (TypeError, ValueError):
            continue
        text = str(row.get("text") or "").strip()
        if span <= 0.2 or not text:
            continue
        spoken += span
        chars += len(text)
    if spoken <= 0.0 or not chars:
        return None
    return chars / spoken


def fit_cps(measured: float | None, *, floor: float = PACE_FLOOR, ceiling: float = BUDGET_CPS) -> float:
    """Budget a beat at the reference's pace, inside what a speaker can do.

    A reference shouted at 7 chars/s is remade faster than a calm one, but the
    budget never plans above `BUDGET_CPS`: text written for an impossible pace
    is exactly what gets clipped at the end.
    """
    if not measured:
        return DEFAULT_CPS
    return max(floor, min(ceiling, float(measured)))


def pace_label(cps: float | None) -> str:
    if not cps:
        return ""
    if cps >= 5.2:
        return "偏快（像直播叫卖）"
    if cps >= 4.4:
        return "较快"
    if cps >= 3.4:
        return "正常"
    return "偏慢（像聊天）"


def char_budget(seconds: float, cps: float = DEFAULT_CPS) -> int:
    """How many characters fit in `seconds`."""
    return max(MIN_LINE_CHARS, int(max(0.5, seconds) * max(0.5, cps)))


def speak_span(seconds: float) -> float:
    """The part of a shot's length available for speech.

    The tail is not padding: a line that ends exactly on the cut is clipped by
    the next shot, and a model that starts its next sentence late reads as a
    long pause between cuts.
    """
    return max(0.5, float(seconds) - TAIL_S)


def _cut(text: str, limit: int) -> str:
    """Take a speakable prefix, preferring to stop on punctuation or a particle."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    floor = max(1, int(limit * 0.6))
    for index in range(len(head) - 1, floor - 1, -1):
        if head[index] in _PUNCT:
            return head[:index].rstrip(_PUNCT + " 　")
    return head.rstrip(_PUNCT + " 　")


def fit_lines(
    lines: list[str],
    seconds: float,
    *,
    cps: float = DEFAULT_CPS,
    grace: float = GRACE,
    single_grace: float = SINGLE_GRACE,
) -> tuple[list[str], bool]:
    """Shorten a beat's lines so every one can be spoken inside `seconds`.

    Returns `(kept_lines, trimmed)`. Lines are never dropped: shortfall comes
    out of the longest lines first, so the tail of the shot is not the only
    thing that gets squeezed.
    """
    texts = [str(line or "").strip() for line in lines if str(line or "").strip()]
    if not texts:
        return [], False
    budget = char_budget(seconds, cps)
    total = sum(len(text) for text in texts)
    if len(texts) == 1:
        # A lone line is all the operator has here; only cut a clearly
        # impossible one (10 chars/s territory). Callers with a hard window
        # pass single_grace=1.0 instead.
        if total <= budget * single_grace:
            return texts, False
        return [_cut(texts[0], budget)], True
    # A hair over is fine: the speaker pushes the pace slightly.
    if total <= budget * grace:
        return texts, False
    shares = [max(MIN_LINE_CHARS, int(budget * len(text) / total)) for text in texts]
    while sum(shares) > budget:
        index = max(range(len(shares)), key=lambda i: shares[i])
        if shares[index] <= MIN_LINE_CHARS:
            break
        shares[index] -= 1
    kept = [_cut(text, share) for text, share in zip(texts, shares)]
    return [line for line in kept if line], True


def overflow(lines: list[str], start: float, end: float, *, cps: float = MAX_CPS) -> bool:
    """True when the lines cannot be said inside `start`–`end`, even fast."""
    texts = [str(line or "").strip() for line in lines if str(line or "").strip()]
    if not texts:
        return False
    span = max(0.0, float(end) - float(start) - TAIL_S)
    return sum(len(text) for text in texts) > char_budget(span, cps)


def schedule(
    lines: list[str],
    start: float,
    end: float,
    *,
    cps: float = DEFAULT_CPS,
    gap: float = LINE_GAP_S,
) -> list[dict[str, float | str]]:
    """Place lines inside one shot.

    Proportional to character count, never shorter than `speak_seconds`, and the
    last line always ends at least `TAIL_S` before the shot does.
    """
    texts = [str(line or "").strip() for line in lines if str(line or "").strip()]
    if not texts:
        return []
    span = max(0.5, float(end) - float(start))
    usable = max(0.5, span - TAIL_S)
    needed = [speak_seconds(text, cps) for text in texts]
    fast = [speak_seconds(text, BUDGET_CPS) for text in texts]
    gap_total = gap * max(0, len(texts) - 1)
    if sum(needed) + gap_total <= usable:
        # Comfortable: natural pace plus a pause, with the slack spread out.
        room = usable - sum(needed) - gap_total
        total_chars = sum(len(text) for text in texts) or 1
        durations = [need + room * len(text) / total_chars for text, need in zip(texts, needed)]
        return _layout(texts, durations, start, gap)
    if sum(fast) + gap_total <= usable:
        # Tight but speakable: raise the pace, drop the pauses.
        room = usable - sum(fast)
        total_chars = sum(len(text) for text in texts) or 1
        durations = [need + room * len(text) / total_chars for text, need in zip(texts, fast)]
        return _layout(texts, durations, start, 0.0)
    # Truly impossible slot: share it by characters and let the caller report
    # the overflow (QA does) instead of silently giving one line no time at all.
    total_chars = sum(len(text) for text in texts) or 1
    durations = [usable * len(text) / total_chars for text in texts]
    return _layout(texts, durations, start, 0.0)


def _layout(texts: list[str], durations: list[float], start: float, gap: float) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    cursor = float(start)
    for text, duration in zip(texts, durations):
        end_at = cursor + max(0.2, float(duration))
        rows.append({"start_s": round(cursor, 3), "end_s": round(end_at, 3), "text": text})
        cursor = end_at + gap
    return rows
