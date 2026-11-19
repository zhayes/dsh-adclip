"""Remake spec and prompt renderer checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_spec.py
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-spec-")
os.environ["ADCLIP_TEST_MODE"] = "1"

from adclip import requirements  # noqa: E402
from adclip.pipeline import generate, remake_spec  # noqa: E402


def _run(brief: str = "商品改成鱿鱼须，到手49块8，去掉原视频中的所有广告大字报，尽量镜头干净",
         aspect: str = "9:16", override: str = "") -> SimpleNamespace:
    inputs = {"brief": brief, "explicit_overrides": "", "product_asset_ids": ["p1"]}
    if override:
        inputs["prompt_override"] = override
    return SimpleNamespace(
        scenario="viral-remake",
        inputs=inputs,
        advanced={
            "aspect": aspect,
            "duration": 12,
            "replace_scope": "both",
            "persona": {"gender": "female", "age": "youth", "body_type": "standard"},
        },
    )


def _skeleton(aspect: str = "9:16") -> dict:
    rows = [
        {"start_s": 0.4, "end_s": 2.2, "text": "家人们刚拉回来一车"},
        {"start_s": 2.2, "end_s": 5.0, "text": "可折叠贝壳椅"},
    ]
    return {
        "source": {"duration_s": 11.2, "aspect": aspect, "has_audio": True},
        "cuts_s": [],
        "beats": [{
            "id": "b0", "start_s": 0.0, "end_s": 11.2, "function": "hook",
            "dialogue": [row["text"] for row in rows],
            "dialogue_rows": rows,
            "dialogue_source": "asr",
        }],
        "remake_plan": {
            "shots": [{
                "id": "s0", "start_s": 0.0, "end_s": 11.2,
                "camera": {"shot_size": "中景", "movement": "固定", "angle": "平视"},
                "scene": "户外货车旁，工业厂房背景",
                "action": "男子揭开红布露出纸箱，举起商品展示",
                "composition": "",
                "continuity": "",
                "product": {"name": "折叠椅", "appearance": "", "position": ""},
                "cast": [{"role": "A", "description": "一名中年男性"}],
                "dialogue": [row["text"] for row in rows],
                "dialogue_rows": rows,
                "dialogue_source": "asr",
                "on_screen_text": "全场 20 元",
                "transition_in": "start",
            }],
            "global": {"preserve": ["镜头", "场景", "动作", "节奏"], "replace": ["人物", "商品"]},
        },
    }


def _script() -> dict:
    return {
        "beats": [{
            "id": "b0",
            "lines": [
                {"speaker": "A", "text": "家人们看过来"},
                {"speaker": "A", "text": "鱿鱼须到手49块8"},
            ],
            "shot": "男子面对镜头举着商品介绍",
        }],
        "source": {"degraded": False},
    }


def check_requirements() -> None:
    got = requirements.derive(
        "商品改成鱿鱼须，到手49块8，去掉原视频中的所有广告大字报，尽量镜头干净",
        {"persona": {"gender": "female"}},
    )
    assert got["clean_text"] is True, got
    assert got["no_bgm"] is True, got
    assert got["product_hint"] == "鱿鱼须", got
    assert any("49" in price for price in got["prices"]), got
    assert requirements.derive("加个轻快的背景音乐")["no_bgm"] is False
    assert requirements.derive("")["no_bgm"] is True
    assert requirements.derive("不要背景音乐")["clean_text"] is False


def check_spec() -> None:
    spec = remake_spec.build_spec(_run(), _skeleton(), _script())
    assert len(spec["shots"]) == 1, spec
    shot = spec["shots"][0]
    assert len(shot["timed_lines"]) == 2, shot["timed_lines"]
    # The reference windows are reused, not re-spread from zero.
    assert shot["timed_lines"][0]["start_s"] == 0.4, shot["timed_lines"]
    # Interior lines keep the ASR end; the closing line runs to the cut so
    # the model has every remaining second for it.
    assert [row["end_s"] for row in shot["timed_lines"]] == [2.2, 11.2], shot["timed_lines"]
    assert shot["dialogue_source"] == "asr", shot
    assert spec["requirements"]["clean_text"] is True, spec["requirements"]
    assert spec["constraints"]["product_count"] == 1, spec["constraints"]


def check_generation_prompt() -> None:
    spec = remake_spec.build_spec(_run(), _skeleton(), _script())
    text = remake_spec.render_generation(spec)
    for line in ("家人们看过来", "鱿鱼须到手49块8"):
        assert line in text, text
    assert "00:00.40–" in text, text
    assert "49块8" in text, text
    assert "鱿鱼须" in text, text
    assert "折叠椅" not in text, "the reference product name must not leak into a replacement prompt"
    assert "竖屏" in text, text
    assert "一次连续拍摄" in text, text
    assert "广告大字报" in text, text
    # The prompt reads like a hand-written one: per-shot header, one flowing
    # visual paragraph, and a timestamped dialogue list. Pace arithmetic stays
    # out (the model paces itself from the timestamps), but the reference's
    # delivery is stated: without it the lines read complete but flat.
    assert "【镜头 1｜" in text, text
    assert "画面：" in text, text
    assert "台词（必须与画面动作、口型同步）：" in text, text
    assert "[00:00.40–" in text, text
    assert "【台词】共" in text, text
    assert "【语感】" in text, text
    assert "【节奏】" in text, text
    assert "播报腔" in text, text
    assert "每秒" in text, text
    assert "不得漏句" in text, text
    assert "水印" not in text, "watermark suppression belongs to the provider parameter, not the prompt"
    assert "秒前说完" not in text, text
    assert "每句间隔" not in text, text
    assert len(text) <= 3500, len(text)

    wide = remake_spec.render_generation(remake_spec.build_spec(_run(aspect="16:9"), _skeleton("16:9"), _script()))
    assert "横屏" in wide and "竖屏" not in wide, wide


def check_multi_shot_prompt() -> None:
    skeleton = _skeleton()
    skeleton["remake_plan"]["shots"].append({
        "id": "s1", "start_s": 6.0, "end_s": 11.2,
        "camera": {"shot_size": "近景", "movement": "固定", "angle": "平视"},
        "scene": "户外货车旁，工业厂房背景",
        "action": "举起商品指向价格牌",
        "product": {"name": "折叠椅", "appearance": "", "position": ""},
        "cast": [], "dialogue": [], "dialogue_rows": [], "transition_in": "cut",
    })
    skeleton["beats"].append({"id": "b1", "start_s": 6.0, "end_s": 11.2, "dialogue_rows": []})
    script = _script()
    script["beats"].append({"id": "b1", "lines": [], "shot": "近景展示商品"})
    text = remake_spec.render_generation(remake_spec.build_spec(_run(), skeleton, script))
    assert "硬切" in text, text
    assert "一次连续拍摄" not in text, text


def check_timed_lines_follow_analysis() -> None:
    """Line windows stay on the analysis windows, tight or not."""
    from adclip.pipeline import timing

    skeleton = _skeleton()
    script = _script()
    script["beats"][0]["lines"] = [{"speaker": "A", "text": "一" * 30}]
    spec = remake_spec.build_spec(_run(), skeleton, script)
    rows = spec["shots"][0]["timed_lines"]
    assert len(rows) == 1, rows
    # One rewritten line, two reference windows: the merged slot keeps the
    # analysis edges instead of spreading over the whole 11.2s shot.
    assert (rows[0]["start_s"], rows[0]["end_s"]) == (0.4, 11.2), rows
    # The closing line gets the whole tail of the shot, so 30 characters fit.
    assert rows[0]["window_s"] > 10.0, rows
    assert rows[0]["needs_s"] <= rows[0]["window_s"], rows


def check_delivery() -> None:
    """Expression, tone and the measured pace reach the prompt."""
    skeleton = _skeleton()
    skeleton["remake_plan"]["shots"][0]["expression"] = "夸张瞪眼、得意"
    skeleton["remake_plan"]["shots"][0]["tone"] = "夸张叫卖"
    skeleton["remake_plan"]["shots"][0]["pace_cps"] = 6.0
    skeleton["remake_plan"]["pace_cps"] = 6.0
    text = remake_spec.render_generation(remake_spec.build_spec(_run(), skeleton, _script()))
    assert "表演：夸张瞪眼、得意；夸张叫卖。" in text, text
    assert "参考片语速约每秒 6.0 个字，偏快" in text, text
    # No pace arithmetic: the timestamps already carry the windows.
    assert "秒前说完" not in text, text


def check_reference_prompt() -> None:
    spec = remake_spec.build_spec(_run(), _skeleton(), _script())
    text = remake_spec.render_reference(spec)
    assert "视频编辑" in text, text
    assert "鱿鱼须到手49块8" in text, text
    assert len(text) <= 1500, len(text)


def check_anchor_prompt() -> None:
    spec = remake_spec.build_spec(_run(), _skeleton(), _script())
    text = remake_spec.render_generation(spec, anchor=True)
    assert "图片1=参考片首帧" in text, text
    assert "图片1=替换后的商品" not in text, text


def check_override() -> None:
    run = _run(override="自定义提示词：一镜到底")
    text = generate._generation_prompt(run, _script(), _skeleton(), {"mode": "generation"})
    assert text == "自定义提示词：一镜到底", text


def main() -> None:
    check_requirements()
    check_spec()
    check_generation_prompt()
    check_timed_lines_follow_analysis()
    check_delivery()
    check_multi_shot_prompt()
    check_reference_prompt()
    check_anchor_prompt()
    check_override()
    print("adclip remake spec: ok")


if __name__ == "__main__":
    main()
