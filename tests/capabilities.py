"""Capability registry and automatic remake selection checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/capabilities.py
"""
from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-cap-")
os.environ["ADCLIP_TEST_MODE"] = "0"
os.environ.pop("MINIMAX_API_KEY", None)
os.environ.pop("ARK_API_KEY", None)

from adclip import capabilities, catalog, params, remake_planner, settings  # noqa: E402
from adclip.pipeline import remake  # noqa: E402


def check_registry() -> None:
    rows = {row["id"]: row for row in catalog.rows()}
    assert "minimax.h3" in rows and rows["minimax.h3"]["remake"]["tier"] == "full"
    assert rows["minimax.h3"]["resolutions"] == ["768P", "2K"]
    assert "reference_to_video" in rows["minimax.h3"]["capabilities"]
    assert rows["ark.seedance-2.0-fast"]["resolutions"] == ["480p", "720p"]
    assert rows["ark.seedance-2.0-mini"]["resolutions"] == ["480p", "720p"]
    assert rows["minimax.hailuo-2.3-fast"]["remake"]["tier"] == "image_only"
    assert rows["minimax.hailuo-2.3-fast"]["native_audio"] is False
    for row in rows.values():
        assert row.get("io") is not None, row["id"]
        assert row.get("params") is not None, row["id"]
        assert row.get("remake", {}).get("tier") in {
            "full", "reference", "generation", "image_only", "none",
        }, row["id"]
        assert "cost_weight" in row["remake"], row["id"]
        assert "price" not in row and "pricing" not in row and "cost" not in row, row["id"]


def check_text_models() -> None:
    """Doubao-Seed-2.1 rows and the vision ladder are exposed but separate."""
    ids = [row["id"] for row in catalog.rows()]
    assert len(ids) == 13, ids
    assert not any(row.startswith("ark.doubao") for row in ids), ids

    os.environ.pop("ARK_API_KEY", None)
    os.environ.pop("MINIMAX_API_KEY", None)
    os.environ.pop("ADSTUDIO_DSH_CHAT_URL", None)
    rows = catalog.text_rows()
    assert [row["id"] for row in rows] == [
        "ark.doubao-seed-2.1-pro",
        "ark.doubao-seed-2.1-turbo",
        "ark.doubao-seed-2.1-lite",
    ], rows
    for row in rows:
        assert row["tags"] == ["多模态模型", "深度思考", "视觉理解"], row
        assert row["available"] is False, row
        assert row["endpoint"].endswith("/chat/completions"), row
        assert "vision" in row["capabilities"] and "thinking" in row["capabilities"], row

    chain = catalog.vision_chain()
    assert [row["id"] for row in chain] == [
        "minimax.m3",
        "ark.doubao-seed-2.1-lite",
        "ark.doubao-seed-2.1-turbo",
        "ark.doubao-seed-2.1-pro",
        "dsh.vision",
        "heuristic",
    ], chain
    assert chain[-1]["available"] is True

    os.environ["ARK_API_KEY"] = "test-key"
    try:
        manifest = capabilities.manifest(
            catalog.rows(),
            text_models=catalog.text_rows(),
            vision_chain=catalog.vision_chain(),
        )
        assert len(manifest["models"]) == 13
        assert [row["id"] for row in manifest["text_models"]] == [row["id"] for row in rows]
        assert manifest["text_models"][0]["available"] is True
        assert [row["id"] for row in manifest["scheduling"]["vision"]] == [row["id"] for row in chain]
        assert all(row["id"] in {r["id"] for r in manifest["models"]} | {r["id"] for r in manifest["text_models"]}
                   for row in manifest["scheduling"]["vision"] if row["provider"] == "ark")
    finally:
        os.environ.pop("ARK_API_KEY", None)


def check_params() -> None:
    assert capabilities.validate_params("minimax.h3", {"resolution": "2K", "duration": "reference"}) == {
        "resolution": "2K",
        "duration": "reference",
    }
    for bad in ({"resolution": "1080p"}, {"duration": 99}, {"unknown": 1}):
        try:
            capabilities.validate_params("minimax.h3", bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid params accepted: {bad}")
    saved = settings.set_model_params("minimax.h3", {"resolution": "2K"})
    assert saved["resolution"] == "2K"
    assert settings.model_params_for("minimax.h3")["resolution"] == "2K"
    merged = catalog.get("minimax.h3")
    assert merged["default_params"]["resolution"] == "2K", merged["default_params"]


def check_audio_policy() -> None:
    forced = params.enforce_remake_audio({"replace_scope": "both", "audio_mode": "preserve"})
    assert forced["audio_mode"] == "regenerate" and forced.get("audio_mode_forced") is True, forced
    kept = params.enforce_remake_audio({"replace_scope": "person", "audio_mode": "preserve"})
    assert kept["audio_mode"] == "preserve" and not kept.get("audio_mode_forced"), kept


def check_selection() -> None:
    os.environ.pop("ADCLIP_TEST_MODE", None)
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["ARK_API_KEY"] = "test-key"
    pick = remake_planner.selection_for(
        "viral-remake",
        {"reference_asset_id": "a_x"},
        {"duration": 11, "replace_scope": "both", "person_scope": "main"},
    )
    assert pick["mode"] == "h3_reference", pick
    assert pick["model"] == "minimax.h3", pick
    assert pick["params"]["duration"] == 11, pick

    os.environ.pop("MINIMAX_API_KEY", None)
    os.environ.pop("ARK_API_KEY", None)
    none = remake_planner.selection_for("viral-remake", {"reference_asset_id": "a_x"}, {"duration": 11})
    assert none["mode"] == "analysis_only", none
    assert none["model"] == "", none


def check_prompt() -> None:
    run = SimpleNamespace(
        inputs={"brief": "换成鹰嘴豆，活动价 9.9", "explicit_overrides": "把背景换成厨房"},
        advanced={"replace_scope": "both", "person_scope": "main", "persona": {"gender": "female", "age": "youth"}},
    )
    skeleton = {
        "remake_plan": {
            "shots": [{
                "product": {"name": "原味瓜子"},
                "cast": [{"description": "蓝衬衫男"}],
            }],
            "global": {"preserve": ["镜头", "场景", "动作", "原声"]},
        }
    }
    text = remake.build_h3_replace_prompt(run, skeleton, product_count=1, person_count=1)
    assert "参考视频1" in text and "图片1" in text and "图片2" in text, text
    assert "保持不变" in text and "不要新增镜头" in text, text
    assert "厨房" in text and "鹰嘴豆" in text, text
    assert len(text) <= 7000, len(text)


def main() -> None:
    check_registry()
    check_text_models()
    check_params()
    check_audio_policy()
    check_selection()
    check_prompt()
    print("adclip capabilities: ok")


if __name__ == "__main__":
    main()
