"""SRT generation from the AdClip script."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(script: dict[str, Any], target: str | Path) -> Path:
    out = Path(target)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    index = 1
    for beat in script.get("beats") or []:
        lines = beat.get("lines") or []
        text = " ".join(str(line.get("text") or "").strip() for line in lines).strip()
        if not text:
            continue
        start = float(beat.get("start_s") or 0.0)
        end = float(beat.get("end_s") or (start + 1.0))
        rows.extend([str(index), f"{_ts(start)} --> {_ts(end)}", text, ""])
        index += 1
    out.write_text("\n".join(rows).strip() + ("\n" if rows else ""), encoding="utf-8")
    return out


def plain_text(script: dict[str, Any]) -> str:
    parts = []
    for beat in script.get("beats") or []:
        for line in beat.get("lines") or []:
            text = str(line.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)
