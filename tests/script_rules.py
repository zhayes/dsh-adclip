"""The brief is an instruction sheet: it must never reach the spoken lines.

Run with:
  PYTHONPATH=src .venv/bin/python tests/script_rules.py
"""
from __future__ import annotations

import os
import tempfile

# Keep the shot-rewrite check out of the repository's data directory.
os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-rules-")

from types import SimpleNamespace  # noqa: E402

from adclip import store  # noqa: E402
from adclip.intents import analyze  # noqa: E402
from adclip.models import AssistantRequest  # noqa: E402
from adclip.pipeline import script  # noqa: E402

BRIEF = (
    "请将原视频中的棉被全部替换为豆豆云朵被，并围绕豆豆云朵被重新调整广告视频脚本和画面内容。"
    "画面需保留原视频棉被替换为豆豆云朵被的修改意图，明确产品名称为豆豆云朵被，"
    "突出只需 70 多一件的高性价比卖点。"
)
QUOTED_BRIEF = BRIEF + "固定台词用「只需七十多，就能盖得很暖」。"
BEATS = [{"id": "b0", "start_s": 0.0, "end_s": 2.0, "len_s": 2.0, "function": "hook", "visual": {"action": ""}}]
SKELETON = {"beats": BEATS, "source": {"duration_s": 2.0}}


def build(brief: str, lines: list[dict] | None) -> dict:
    script.llm.chat_json = lambda *a, **k: None if lines is None else {"beats": [{"id": "b0", "lines": lines, "shot": "中景"}]}
    run = SimpleNamespace(scenario="viral-remake", inputs={"brief": brief}, advanced={})
    return script.build_script(run, SKELETON, {"must_keep": []})


def texts(doc: dict) -> list[str]:
    return [line["text"] for beat in doc["beats"] for line in beat["lines"]]


def review_doc(lines: list[dict], drop: list[dict] | None) -> dict:
    """Script pass returns `lines`; the review pass returns `drop` (None = reviewer down)."""
    def fake(system, *a, **k):
        if "台词审核" in system:
            return None if drop is None else {"drop": drop}
        return {"beats": [{"id": "b0", "lines": lines, "shot": "中景"}]}
    script.llm.chat_json = fake
    run = SimpleNamespace(scenario="viral-remake", inputs={"brief": BRIEF}, advanced={})
    return script.build_script(run, SKELETON, {"must_keep": []})


def check_rewrite() -> None:
    run = SimpleNamespace(id="run_rules", inputs={"brief": BRIEF}, advanced={})
    path = store.run_dir(run.id) / "artifacts" / "script.json"
    store.atomic_write_json(path, {"source": {"model": "stub", "degraded": False}, "beats": [
        {"id": "b0", "function": "hook", "len_s": 2.0, "lines": [{"speaker": "A", "text": "旧台词", "chars": 3}], "shot": "中景"},
    ]})
    script.llm.chat_json = lambda *a, **k: {"lines": [
        {"speaker": "A", "text": "请将原视频中的棉被替换"},
        {"speaker": "B", "text": "这款被子蓬松又暖和"},
    ], "shot": "近景"}
    script.rewrite_shot(run, 0, "说明产品质感")
    doc = store.read_json(path)
    assert [line["text"] for line in doc["beats"][0]["lines"]] == ["这款被子蓬松又暖和"], doc
    assert doc["beats"][0]["shot"] == "近景"
    assert doc["source"]["line_review"].startswith("llm"), doc["source"]

    # A note on a selected shot becomes one rewrite card instead of a dead end.
    asked = analyze(AssistantRequest(message="说明产品质感", selected_segment_id="s0", context={"brief": BRIEF}))
    assert [c["field"] for c in asked["changes"]] == ["segment.rewrite"], asked
    assert asked["changes"][0]["to"] == "说明产品质感"
    # Parameter edits still win, and no selection keeps the generic prompt.
    param = analyze(AssistantRequest(message="换成女性", selected_segment_id="s0", context={}))
    assert [c["field"] for c in param["changes"]] == ["persona.gender"], param
    plain = analyze(AssistantRequest(message="说明产品质感", context={}))
    assert not plain["changes"] and plain["questions"], plain


def main() -> None:
    # No text model: quote what the operator fixed, never split the brief.
    assert texts(build(BRIEF, None)) == [], build(BRIEF, None)
    assert texts(build(QUOTED_BRIEF, None)) == ["只需七十多，就能盖得很暖"]

    # A model that echoes the brief loses those lines; real dialogue survives.
    echoed = texts(build(BRIEF, [
        {"speaker": "A", "text": "请将原视频中的棉被全部替换为豆豆云朵被"},
        {"speaker": "B", "text": "这款被子蓬松又暖和"},
    ]))
    assert echoed == ["这款被子蓬松又暖和"], echoed
    assert texts(build(BRIEF, [{"speaker": "A", "text": "画面需保留原视频棉被替换为豆豆云朵被的修改意图"}])) == []

    # Semantic review drops a rewritten instruction the word list cannot see.
    paraphrased = review_doc([
        {"speaker": "A", "text": "旧的棉被整个换掉"},
        {"speaker": "B", "text": "这款被子蓬松又暖和"},
    ], [{"index": 1, "reason": "制作要求"}])
    assert texts(paraphrased) == ["这款被子蓬松又暖和"], paraphrased
    assert paraphrased["source"]["line_review"].startswith("llm"), paraphrased["source"]

    # Reviewer down: keep the lines (the structural guard already ran) and say so.
    blind = review_doc([{"speaker": "A", "text": "这款被子蓬松又暖和"}], None)
    assert texts(blind) == ["这款被子蓬松又暖和"]
    assert blind["source"]["line_review"].startswith("skipped"), blind["source"]

    check_rewrite()
    print("adclip script rules: ok")


if __name__ == "__main__":
    main()
