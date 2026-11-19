"""Doubao-Seed-2.1 (Ark) text/vision adapter checks.

Runs offline: every HTTP hop is monkeypatched, and the local data dir is a
temporary directory so the activation cache never touches the live app.

Run with:
  PYTHONPATH=src .venv/bin/python tests/ark_text.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-arktext-")
os.environ["ADCLIP_TEST_MODE"] = "0"
os.environ["ADSTUDIO_VISION"] = "1"
os.environ.pop("MINIMAX_API_KEY", None)
os.environ.pop("ADSTUDIO_DSH_CHAT_URL", None)
os.environ.pop("ADSTUDIO_DSH_VISION_URL", None)

from PIL import Image  # noqa: E402

from adclip import catalog, llm  # noqa: E402
from adclip.media import vision  # noqa: E402
from adclip.providers import ark_text  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self._payload = payload
        import json as _json
        self.text = _json.dumps(payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


def _chat_payload(text: str, *, reasoning: str = "", usage: dict | None = None) -> dict:
    message: dict = {"content": text}
    if reasoning:
        message["reasoning_content"] = reasoning
    return {"choices": [{"message": message}], "usage": usage or {"total_tokens": 12}}


def check_rows() -> None:
    os.environ.pop("ARK_API_KEY", None)
    rows = ark_text.models()
    assert [row["id"] for row in rows] == [
        "ark.doubao-seed-2.1-pro",
        "ark.doubao-seed-2.1-turbo",
        "ark.doubao-seed-2.1-lite",
    ], rows
    for row in rows:
        assert row["tags"] == ["多模态模型", "深度思考", "视觉理解"], row
        assert row["context"] == "1M"
        assert row["available"] is False and row["status"] == "no_key", row
    os.environ["ARK_API_KEY"] = "test-key"
    assert ark_text.available() is True
    assert all(row["available"] for row in ark_text.models())
    assert [row["id"] for row in catalog.text_rows()] == [row["id"] for row in rows]
    # Text rows stay out of the generation registry.
    assert len(catalog.rows()) == 13


def check_chat_payload() -> None:
    seen: list[dict] = []

    def fake_post(payload, *, timeout=90.0):
        seen.append(dict(payload))
        return FakeResponse(200, _chat_payload('{"ok":true}', reasoning="先想一下"))

    original = ark_text._post
    ark_text._post = fake_post
    try:
        result = ark_text.chat("系统", [{"role": "user", "content": "你好"}], model="ark.doubao-seed-2.1-lite", thinking=False)
    finally:
        ark_text._post = original
    assert seen[0]["thinking"] == {"type": "disabled"}, seen[0]
    assert seen[0]["model"] == os.environ.get("ARK_MODEL_DOUBAO_LITE", "doubao-seed-2-1-lite-260915"), seen[0]
    assert result["text"] == '{"ok":true}', result
    assert result["provider"] == "ark"
    assert ark_text.status_of("ark.doubao-seed-2.1-lite")["status"] == "ok"


def check_think_stripped() -> None:
    original = ark_text._post
    ark_text._post = lambda payload, *, timeout=90.0: FakeResponse(200, _chat_payload("<think>想想</think>\n结果"))
    try:
        result = ark_text.chat("", [{"role": "user", "content": "x"}], model="pro")
    finally:
        ark_text._post = original
    assert result["text"] == "结果", result


def check_not_open() -> None:
    body = {"error": {"code": "ModelNotOpen", "message": "Your account has not activated the model"}}
    ark_text.record("ark.doubao-seed-2.1-pro", "unknown")
    original = ark_text._post
    ark_text._post = lambda payload, *, timeout=90.0: FakeResponse(404, body)
    try:
        try:
            ark_text.chat("", [{"role": "user", "content": "x"}], model="ark.doubao-seed-2.1-pro")
        except ark_text.ArkTextError as exc:
            assert "未开通" in str(exc), exc
            assert exc.kind == "not_open", exc.kind
        else:
            raise AssertionError("ModelNotOpen did not raise")
        assert ark_text.status_of("ark.doubao-seed-2.1-pro")["status"] == "not_open"
        assert ark_text.models()[0]["available"] is False
        # Cached closed models are skipped by the vision order.
        short = [row["short"] for row in ark_text.vision_models()]
        assert "pro" not in short and short == ["turbo", "lite"], short
    finally:
        ark_text._post = original
    # A single flap must not downgrade a proven-open model.
    ark_text.record("ark.doubao-seed-2.1-pro", "ok")
    ark_text.record("ark.doubao-seed-2.1-pro", "not_open")
    assert ark_text.status_of("ark.doubao-seed-2.1-pro")["status"] == "ok"


def check_retry_without_thinking() -> None:
    calls: list[dict] = []

    def fake_post(payload, *, timeout=90.0):
        calls.append(dict(payload))
        if "thinking" in payload:
            return FakeResponse(400, {"error": {"code": "InvalidParameter", "message": "unknown field thinking"}})
        return FakeResponse(200, _chat_payload('{"ok":1}'))

    original = ark_text._post
    ark_text._post = fake_post
    try:
        result = ark_text.chat("", [{"role": "user", "content": "x"}], model="turbo", thinking=True)
    finally:
        ark_text._post = original
    assert len(calls) == 2 and "thinking" not in calls[1], calls
    assert result["text"] == '{"ok":1}'


def check_vision_ark() -> None:
    frame = Path(tempfile.mkdtemp(prefix="adclip-arkframe-")) / "b0.jpg"
    Image.new("RGB", (120, 68), (30, 60, 120)).save(frame, format="JPEG")
    frames = [{"id": "b0", "beat_id": "b0", "start_s": 0, "end_s": 1, "path": str(frame)}]
    original = ark_text._post
    ark_text._post = lambda payload, *, timeout=90.0: FakeResponse(200, _chat_payload(
        '{"frames":[{"id":"b0","shot_size":"近景","action":"拿起产品","product":"红色包装","scene":"室内","on_screen_text":"SALE 99"}]}'
    ))
    try:
        rows = vision._analyze_ark(frames)
    finally:
        ark_text._post = original
    assert set(rows) == {"b0"}, rows
    assert rows["b0"]["on_screen_text"] == "SALE 99", rows
    assert vision.LAST_PROVIDER == "ark", vision.LAST_PROVIDER
    assert vision.LAST_MODEL.startswith("doubao-seed-2-1-"), vision.LAST_MODEL


def check_llm_ark_first() -> None:
    os.environ["ADSTUDIO_TEXT_PROVIDER"] = "auto"
    seen: list[str] = []

    def fake_post(payload, *, timeout=90.0):
        seen.append(str(payload.get("model")))
        return FakeResponse(200, _chat_payload('{"beats":[]}'))

    original_post = ark_text._post
    original_dsh = llm._chat_dsh
    ark_text._post = fake_post

    def failing_dsh(*args, **kwargs):
        raise RuntimeError("dsh down")

    llm._chat_dsh = failing_dsh
    try:
        text = llm.chat(
            "system",
            "user",
            text_model={"provider": "ark", "model": "ark.doubao-seed-2.1-lite"},
        )
        assert text == '{"beats":[]}', text
        assert seen and seen[0].startswith("doubao-seed-2-1-"), seen
        value = llm.chat_json(
            "system",
            "user",
            text_model={"provider": "ark", "model": "ark.doubao-seed-2.1-lite"},
        )
        assert value == {"beats": []}, value
    finally:
        ark_text._post = original_post
        llm._chat_dsh = original_dsh
        os.environ["ADSTUDIO_TEXT_PROVIDER"] = "minimax"


def check_vision_chain() -> None:
    os.environ["MINIMAX_API_KEY"] = ""
    os.environ["ADSTUDIO_DSH_CHAT_URL"] = ""
    chain = catalog.vision_chain()
    ids = [row["id"] for row in chain]
    assert ids == [
        "minimax.m3",
        "ark.doubao-seed-2.1-lite",
        "ark.doubao-seed-2.1-turbo",
        "ark.doubao-seed-2.1-pro",
        "dsh.vision",
        "heuristic",
    ], ids
    assert chain[0]["available"] is False
    assert chain[-1]["available"] is True
    os.environ.pop("MINIMAX_API_KEY", None)


def main() -> None:
    # Keep the offline suite fast: retry delays are exercised by the live probe.
    ark_text.NOT_OPEN_RETRIES = (0, 0)
    check_rows()
    check_chat_payload()
    check_think_stripped()
    check_not_open()
    check_retry_without_thinking()
    check_vision_ark()
    check_llm_ark_first()
    check_vision_chain()
    print("adclip ark text/vision: ok")


if __name__ == "__main__":
    main()
