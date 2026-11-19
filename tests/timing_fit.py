"""Speech timing guards: a line never exceeds the time it needs to be spoken.

Run with:
  PYTHONPATH=src .venv/bin/python tests/timing_fit.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-timing-")
os.environ["ADCLIP_TEST_MODE"] = "1"

from adclip.pipeline import timing  # noqa: E402


def check_speak_seconds() -> None:
    assert timing.speak_seconds("") == timing.MIN_LINE_S
    assert timing.speak_seconds("冬天你盖了") == 5 / 4.0
    assert timing.speak_seconds("短") == timing.MIN_LINE_S


def check_fit_lines() -> None:
    kept, trimmed = timing.fit_lines(["一二三四", "五六七八"], 2.0)
    assert kept == ["一二三四", "五六七八"], kept
    assert trimmed is False
    # 30 chars in 3 seconds is 10 cps: even the fastest read cannot finish it,
    # so the single line is cut to the natural-read budget instead of running
    # past the cut.
    kept, trimmed = timing.fit_lines(["一" * 30], 3.0)
    assert len(kept) == 1 and len(kept[0]) == timing.char_budget(3.0), kept
    assert trimmed is True
    # Several lines are shortened in place, never dropped: a missing punchline
    # or price is worse than a shorter one.
    kept, trimmed = timing.fit_lines(["一二三四五六七八九十", "十一十二"], 2.0)
    assert len(kept) == 2, kept
    assert trimmed is True
    assert sum(len(line) for line in kept) <= timing.char_budget(2.0), kept
    # A line that fits at a normal pace is left untouched.
    kept, trimmed = timing.fit_lines(["价格搞错了，只要七十多"], 4.0)
    assert kept == ["价格搞错了，只要七十多"] and trimmed is False, kept


def check_overflow() -> None:
    assert timing.overflow(["一" * 30], 0.0, 3.0) is True
    assert timing.overflow(["一二三四", "五六七八"], 0.0, 4.0) is False


def check_schedule() -> None:
    rows = timing.schedule(["一二三四五六七八", "短句"], 0.0, 4.0)
    assert len(rows) == 2, rows
    assert rows[0]["start_s"] == 0.0, rows
    assert rows[-1]["end_s"] <= 4.0 - timing.TAIL_S + 1e-6, rows
    for row in rows:
        assert row["end_s"] - row["start_s"] >= timing.speak_seconds(row["text"], timing.MAX_CPS) - 1e-6, row

    # A tight shot still never runs past its end, and every line keeps a slot.
    tight = timing.schedule(["一二三四五", "六七八九十", "十一十二"], 0.0, 2.0)
    assert tight[-1]["end_s"] <= 2.0 - timing.TAIL_S + 1e-6, tight
    assert all(row["end_s"] > row["start_s"] for row in tight), tight
    assert len(tight) == 3, tight


def main() -> None:
    check_speak_seconds()
    check_fit_lines()
    check_overflow()
    check_schedule()
    print("adclip timing fit: ok")


if __name__ == "__main__":
    main()
