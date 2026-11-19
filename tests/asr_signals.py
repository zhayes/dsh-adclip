"""ASR coverage heuristics (no model, no network).

Run with:
  PYTHONPATH=src .venv/bin/python tests/asr_signals.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-asr-")
os.environ["ADSTUDIO_ASR"] = "0"

from adclip.media import asr  # noqa: E402


def check_covered() -> None:
    rows = [{"start_s": 0.0, "end_s": 2.0}, {"start_s": 3.0, "end_s": 4.5}]
    assert asr._covered(rows) == 3.5, asr._covered(rows)


def check_retry_signals() -> None:
    # Empty transcript on a real clip: retry.
    assert asr._needs_retry([], 11.0) is True
    # VAD stopped halfway through: retry.
    assert asr._needs_retry([{"start_s": 0.0, "end_s": 4.5}], 11.0) is True
    # One long merged block: retry.
    assert asr._needs_retry([{"start_s": 0.0, "end_s": 4.5}], 11.0) is True
    # A normal 6-line transcript: keep it.
    rows = [
        {"start_s": 0.0, "end_s": 2.6},
        {"start_s": 2.6, "end_s": 4.5},
        {"start_s": 4.5, "end_s": 5.5},
        {"start_s": 5.5, "end_s": 7.5},
        {"start_s": 7.5, "end_s": 8.3},
        {"start_s": 8.3, "end_s": 10.7},
    ]
    assert asr._needs_retry(rows, 11.0) is False
    # Very short clips never trigger a second pass.
    assert asr._needs_retry([], 3.0) is False


def check_cleanup_guard() -> None:
    """Cleanup is opt-out and never changes the timing fields."""
    os.environ["ADSTUDIO_ASR_CLEANUP"] = "0"
    try:
        rows = [{"start_s": 0.0, "end_s": 1.0, "text": "通天你盖了"}]
        assert asr.refine(rows, hint="冬天") == rows
    finally:
        os.environ.pop("ADSTUDIO_ASR_CLEANUP", None)


def main() -> None:
    check_covered()
    check_retry_signals()
    check_cleanup_guard()
    print("adclip asr signals: ok")


if __name__ == "__main__":
    main()
