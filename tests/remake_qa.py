"""Requirement checks and acceptance thresholds.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_qa.py
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-qa-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"

from adclip.pipeline import qa  # noqa: E402

BRIEF = "商品改成鱿鱼须，到手49块8，去掉原视频中的所有广告大字报，尽量镜头干净"
ADVANCED = {"replace_scope": "both", "audio_mode": "regenerate"}
RUN = SimpleNamespace(inputs={"brief": BRIEF}, advanced=ADVANCED)


def _words(*texts: str) -> list[dict]:
    return [{"start_s": index, "end_s": index + 0.8, "text": text} for index, text in enumerate(texts)]


def check_thresholds() -> None:
    assert qa.SCORE_THRESHOLDS == {"h3_reference": 80, "reference": 65, "keyframe": 45, "generation": 45}


def check_requirements_with_transcript() -> None:
    checks = qa._requirement_checks(RUN, ADVANCED, _words("鱿鱼须", "到手", "49", "块8"))
    by_id = {item["id"]: item for item in checks}
    assert by_id["req_price"]["status"] == "pass", by_id["req_price"]
    assert by_id["req_product"]["status"] == "pass", by_id["req_product"]
    assert by_id["req_clean_text"]["status"] == "warn", by_id["req_clean_text"]
    assert by_id["req_clean_text"]["value"]["verified"] is False, by_id["req_clean_text"]


def check_requirements_without_transcript() -> None:
    checks = qa._requirement_checks(RUN, ADVANCED, [])
    by_id = {item["id"]: item for item in checks}
    assert by_id["req_price"]["status"] == "warn", by_id["req_price"]
    assert "未校验" in by_id["req_price"]["note"], by_id["req_price"]
    assert by_id["req_product"]["value"]["verified"] is False, by_id["req_product"]


def check_missing_price() -> None:
    checks = qa._requirement_checks(RUN, ADVANCED, _words("鱿鱼须", "很好吃"))
    price = {item["id"]: item for item in checks}["req_price"]
    assert price["status"] == "warn", price
    assert price["value"]["missing"], price


def check_quoted_line() -> None:
    brief = "商品改成鱿鱼须，「鱿鱼须到手49块8」"
    run = SimpleNamespace(inputs={"brief": brief}, advanced=ADVANCED)
    hit = {item["id"]: item for item in qa._requirement_checks(run, ADVANCED, _words("鱿鱼须到手49块8"))}
    assert hit["req_line_0"]["status"] == "pass", hit["req_line_0"]
    miss = {item["id"]: item for item in qa._requirement_checks(run, ADVANCED, _words("家人们看过来"))}
    assert miss["req_line_0"]["status"] == "warn", miss["req_line_0"]


def check_dialogue_timing() -> None:
    """A line longer than its slot is reported, not silently accepted."""
    run = SimpleNamespace(
        scenario="viral-remake",
        inputs={"brief": BRIEF, "explicit_overrides": "", "product_asset_ids": []},
        advanced={"aspect": "9:16", "duration": 4, "replace_scope": "both"},
    )
    skeleton = {
        "source": {"duration_s": 4.0, "aspect": "9:16", "has_audio": True},
        "cuts_s": [],
        "beats": [{"id": "b0", "start_s": 0.0, "end_s": 4.0, "len_s": 4.0, "dialogue_rows": []}],
        "remake_plan": {
            "shots": [{
                "id": "s0", "start_s": 0.0, "end_s": 4.0,
                "camera": {}, "scene": "", "action": "", "composition": "", "continuity": "",
                "product": {}, "cast": [], "dialogue": [], "dialogue_rows": [],
            }],
            "global": {},
        },
    }
    long_line = {"beats": [{"id": "b0", "lines": [{"speaker": "A", "text": "一" * 30}], "shot": ""}]}
    info = qa._dialogue_timing(run, skeleton, long_line, 4.0)
    # The renderer shortens a line that cannot be said inside the shot, so the
    # check reports the fitted text rather than a guaranteed overflow.
    assert info and info["lines"] == 1, info
    assert info["chars"] < 30, info
    assert info["tight_count"] == 0, info
    assert info["cps"] <= qa.timing.MAX_CPS, info

    short = {"beats": [{"id": "b0", "lines": [{"speaker": "A", "text": "只需七十多"}], "shot": ""}]}
    ok = qa._dialogue_timing(run, skeleton, short, 4.0)
    assert ok and ok["tight_count"] == 0, ok

    empty = qa._dialogue_timing(run, skeleton, {"beats": [{"id": "b0", "lines": [], "shot": ""}]}, 4.0)
    assert empty is None, empty


def main() -> None:
    check_thresholds()
    check_requirements_with_transcript()
    check_requirements_without_transcript()
    check_missing_price()
    check_quoted_line()
    check_dialogue_timing()
    print("adclip remake qa: ok")


if __name__ == "__main__":
    main()
