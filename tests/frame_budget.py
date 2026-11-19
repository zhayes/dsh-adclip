"""Adaptive keyframe budget and visual aggregation checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/frame_budget.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-frames-")
os.environ["ADSTUDIO_VISION"] = "1"

from adclip.pipeline import analyze  # noqa: E402


def beats_for(duration: float, count: int = 4):
    length = duration / count
    return [
        {"id": f"b{i}", "start_s": round(i * length, 3), "end_s": round((i + 1) * length, 3)}
        for i in range(count)
    ]


def check_budget() -> None:
    expected = {4: 4, 5: 4, 8: 5, 11: 6, 20: 9, 30: 13}
    for duration, value in expected.items():
        assert analyze._vision_budget(duration) == value, (duration, analyze._vision_budget(duration))
    assert analyze._vision_budget(60) == 14


def check_distribution() -> None:
    original = analyze.ffmpeg.extract_frame
    analyze.ffmpeg.extract_frame = lambda *args, **kwargs: None
    try:
        for duration, count, budget in [(5, 2, 4), (11, 4, 6), (20, 5, 9), (30, 6, 13)]:
            stats: dict[str, int] = {}
            frames = analyze._plan_analysis_frames(
                "/tmp/run", "/tmp/source", beats_for(duration, count), duration, max_frames=budget, stats=stats
            )
            assert 1 <= len(frames) <= budget, (duration, len(frames))
            assert stats["used"] == len(frames), stats
            assert stats["planned"] <= budget, stats
            assert len({frame["id"] for frame in frames}) == len(frames)
            assert all(0 <= frame["time_s"] <= duration for frame in frames)
            by_beat = {}
            for frame in frames:
                by_beat.setdefault(frame["beat_id"], []).append(frame)
            assert all(len(items) >= 1 for items in by_beat.values()), by_beat
            # Two frames per beat pin the action interval when budget allows.
            if budget >= 2 * count:
                assert all(len(items) >= 2 for items in by_beat.values()), by_beat
    finally:
        analyze.ffmpeg.extract_frame = original


def check_aggregation() -> None:
    frames = [
        {"id": "b0_f0", "beat_id": "b0"},
        {"id": "b0_f1", "beat_id": "b0"},
        {"id": "b1_f0", "beat_id": "b1"},
    ]
    tags = {
        "b0_f0": {"shot_size": "中景", "product": "", "confidence": 0.4, "unclear": ["product"]},
        "b0_f1": {"shot_size": "近景", "product": "咖啡", "confidence": 0.9, "unclear": []},
        "b1_f0": {"shot_size": "全景", "action": "走动", "confidence": 0.7, "unclear": []},
    }
    rows = analyze._aggregate_visual(tags, frames, [{"id": "b0"}, {"id": "b1"}])
    assert rows["b0"]["shot_size"] == "近景", rows
    assert rows["b0"]["product"] == "咖啡", rows
    assert rows["b0"]["confidence"] == 0.9, rows
    assert rows["b0"]["frame_ids"] == ["b0_f0", "b0_f1"], rows
    assert rows["b1"]["action"] == "走动", rows


def main() -> None:
    check_budget()
    check_distribution()
    check_aggregation()
    print("adclip frame budget: ok")


if __name__ == "__main__":
    main()
