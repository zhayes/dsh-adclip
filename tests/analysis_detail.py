"""Breakdown detail: cast appearance, background and lighting reach the prompt.

Run with:
  PYTHONPATH=src .venv/bin/python tests/analysis_detail.py
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-detail-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from adclip.media import vision  # noqa: E402
from adclip.pipeline import analyze, remake, remake_spec, segment  # noqa: E402

APPEARANCE = "40岁左右亚洲男性，戴黑框眼镜，短寸头"
WARDROBE = "深蓝色西装外套，内搭白衬衫"
BACKGROUND = "明亮蓝天白云下的工业厂房前水泥空地，右侧停着白色厢式货车"


def _frame_payload() -> dict:
    return {
        "frames": [{
            "id": "b0",
            "shot_size": "中景",
            "camera_angle": "平视",
            "camera_movement": "固定",
            "people": "1名男子",
            "cast": [{
                "key": "A",
                "role": "主角",
                "appearance": APPEARANCE,
                "wardrobe": WARDROBE,
                "props": "右手握黄色美工刀",
                "expression": "期待微笑",
                "gaze": "看镜头",
            }],
            "action": "站在车厢红布前，右手持刀准备剪彩",
            "product": "棕色纸箱货物",
            "product_appearance": "牛皮纸色纸箱，成摞码放",
            "product_position": "画面中央车斗上",
            "product_visibility": "主体",
            "scene": "货车旁",
            "background": BACKGROUND,
            "lighting": "日光充足，右侧偏亮，阴影短",
            "composition": "人物居左，货车居右",
            "on_screen_text": "",
            "confidence": 0.9,
        }]
    }


def check_vision_normalize() -> None:
    rows = vision._normalize_rows(_frame_payload(), ["b0"])
    row = rows["b0"]
    assert row["background"] == BACKGROUND, row
    assert row["lighting"].startswith("日光充足"), row
    cast = row["cast"][0]
    assert cast["key"] == "A" and cast["role"] == "主角", cast
    assert APPEARANCE in cast["description"] and "身穿" + WARDROBE in cast["description"], cast
    assert row["product_appearance"].startswith("牛皮纸色"), row
    assert row["product_position"].startswith("画面中央"), row

    legacy = vision._normalize_rows({"frames": [{"id": "b0", "people": "一名女性"}]}, ["b0"])
    assert legacy["b0"]["cast"][0]["description"] == "一名女性", legacy


def _beats() -> list[dict]:
    return [{
        "id": "b0",
        "start_s": 0.0,
        "end_s": 8.0,
        "function": "hook",
        "dialogue_rows": [{"start_s": 0.4, "end_s": 2.0, "text": "家人们刚拉回来一车"}],
        "dialogue": ["家人们刚拉回来一车"],
        "dialogue_source": "asr",
    }]


def check_aggregate_merge() -> None:
    first = vision._normalize_rows(_frame_payload(), ["b0"])["b0"]
    second_payload = _frame_payload()
    second_payload["frames"][0]["id"] = "b0_ctx"
    second_payload["frames"][0]["cast"][0].pop("wardrobe")
    second_payload["frames"][0]["background"] = ""
    second = vision._normalize_rows(second_payload, ["b0_ctx"])["b0_ctx"]
    frames = [
        {"id": "b0", "beat_id": "b0"},
        {"id": "b0_ctx", "beat_id": "b0"},
    ]
    merged = analyze._aggregate_visual({"b0": second, "b0_ctx": first}, frames, _beats())["b0"]
    cast = merged["cast"][0]
    # The richer frame wins field by field: appearance from one label, wardrobe
    # from the other, never one frame overwriting the other.
    assert APPEARANCE in cast["description"] and "身穿" + WARDROBE in cast["description"], cast
    assert merged["background"] == BACKGROUND, merged


def _run(scope: str = "both", persona: dict | None = None) -> SimpleNamespace:
    advanced = {"replace_scope": scope, "aspect": "9:16", "duration": 12}
    if persona:
        advanced["persona"] = persona
    return SimpleNamespace(
        scenario="viral-remake",
        inputs={"brief": "", "reference_asset_id": "a1"},
        advanced=advanced,
    )


def _skeleton() -> dict:
    beats = _beats()
    beats[0]["visual"] = {
        "action": "站在车厢红布前，右手持刀准备剪彩",
        "shot_size": "中景",
        "product": {"name": "棕色纸箱货物"},
        "product_appearance": "牛皮纸色纸箱，成摞码放",
        "product_position": "画面中央车斗上",
        "people": "1名男子",
        "cast": [{
            "key": "A",
            "role": "主角",
            "appearance": APPEARANCE,
            "wardrobe": WARDROBE,
            "props": "右手握黄色美工刀",
            "gaze": "看镜头",
            "description": f"{APPEARANCE}，身穿{WARDROBE}，右手握黄色美工刀",
        }],
        "scene": "货车旁",
        "background": BACKGROUND,
        "lighting": "日光充足，右侧偏亮，阴影短",
        "expression": "期待微笑",
        "tone": "夸张叫卖",
        "composition": "人物居左，货车居右",
        "on_screen_text": "",
        "continuity": "",
        "camera_angle": "平视",
        "camera_movement": "固定",
        "confidence": 0.9,
        "unclear": [],
        "frame_ids": ["b0"],
    }
    plan = analyze._remake_plan(_run(), beats, {"duration_s": 8.0, "aspect": "9:16"}, {"b0": {}})
    return {
        "source": {"duration_s": 8.0, "aspect": "9:16", "has_audio": True},
        "beats": beats,
        "remake_plan": plan,
        "analysis": {
            "cast_roster": analyze._cast_roster(plan.get("shots") or []),
            "scenes": analyze._scene_roster(plan.get("shots") or []),
        },
    }


def _script() -> dict:
    return {
        "beats": [{
            "id": "b0",
            "lines": [{"speaker": "A", "text": "家人们看过来"}],
            "shot": "男子面对镜头举着纸箱介绍",
        }],
    }


def check_plan_fields() -> None:
    skeleton = _skeleton()
    shot = skeleton["remake_plan"]["shots"][0]
    assert shot["background"] == BACKGROUND, shot
    assert shot["lighting"].startswith("日光充足"), shot
    assert shot["people"] == "1名男子", shot
    assert shot["cast"][0]["key"] == "A", shot["cast"]
    assert "身穿" + WARDROBE in shot["cast"][0]["description"], shot["cast"]
    assert shot["product"]["appearance"].startswith("牛皮纸色"), shot["product"]
    assert shot["product"]["position"].startswith("画面中央"), shot["product"]

    roster = skeleton["analysis"]["cast_roster"]
    assert roster and APPEARANCE in roster[0]["description"], roster
    scenes = skeleton["analysis"]["scenes"]
    assert scenes and scenes[0]["text"] == BACKGROUND and scenes[0]["lighting"], scenes


def check_generation_prompt() -> None:
    skeleton = _skeleton()
    # Product-only replacement keeps the reference person, so the cast look is
    # part of what the model must reproduce.
    text = remake_spec.render_generation(remake_spec.build_spec(_run(scope="product"), skeleton, _script()))
    assert "【场景】" in text and "工业厂房" in text, text
    assert "光线日光充足" in text, text
    assert "【人物】" in text and "戴黑框眼镜" in text and "深蓝色西装" in text, text
    # The first shot's background lives in 【场景】 and is not repeated per shot.
    assert text.count("工业厂房") == 1, text

    persona_text = remake_spec.render_generation(remake_spec.build_spec(
        _run(scope="product", persona={"gender": "female", "age": "youth", "body_type": "standard"}), skeleton, _script()
    ))
    assert "戴黑框眼镜" not in persona_text, "persona must replace the reference look"
    assert "【场景】" in persona_text, "background survives a persona swap"

    replaced_text = remake_spec.render_generation(remake_spec.build_spec(_run(scope="person"), skeleton, _script()))
    assert "戴黑框眼镜" not in replaced_text, "a replaced person must not inherit the reference look"
    assert "工业厂房" in replaced_text, "only the person is replaced, the background stays"


def check_h3_prompt() -> None:
    skeleton = _skeleton()
    run = _run(scope="both")
    text = remake.build_h3_replace_prompt(run, skeleton, product_count=1, person_count=1)
    assert "1名男子" in text, text
    assert "戴黑框眼镜" not in text, "appearance must not leak into a replaced person"
    assert "不要沿用原片人物的外貌" in text, text
    assert "背景" in text and "光线" in text, text


def check_segment_fields() -> None:
    skeleton = _skeleton()
    rows = segment._segments_for(_run(), skeleton, _script(), 8.0)
    row = rows[0]
    assert row["background"] == BACKGROUND, row
    assert row["scene"] == "货车旁", row
    assert row["cast"] and row["cast"][0]["description"], row
    assert row["expression"] == "期待微笑", row


def main() -> None:
    check_vision_normalize()
    check_aggregate_merge()
    check_plan_fields()
    check_generation_prompt()
    check_h3_prompt()
    check_segment_fields()
    print("adclip analysis detail: ok")


if __name__ == "__main__":
    main()
