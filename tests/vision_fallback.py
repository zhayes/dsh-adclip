"""MiniMax -> DSH vision fallback checks.

Covers the budgeted DSH bridge: per-frame rows across batches, bisect recovery
when a whole batch fails, the total deadline keeping partial labels, and the
describe pass batching by shot.

Run with:
  PYTHONPATH=src .venv/bin/python tests/vision_fallback.py
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-vision-")
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "1"
os.environ.pop("MINIMAX_API_KEY", None)

from PIL import Image  # noqa: E402

from adclip.media import vision  # noqa: E402

STATE = {"mode": "ok", "delay": 0.0, "calls": []}


def _rows(ids: list[str]) -> str:
    return json.dumps({"frames": [{
        "id": frame_id,
        "shot_size": "中景",
        "action": "人物拿着苹果",
        "people": "一名女性",
        "cast": [{"key": "A", "role": "主角", "appearance": "短黑发女性", "wardrobe": "白色上衣"}],
        "product": "苹果",
        "scene": "室内",
        "on_screen_text": "",
    } for frame_id in ids]}, ensure_ascii=False)


def _beats(ids: list[str]) -> str:
    # The describe contract is keyed by shot id, the request carries frame ids.
    beat_ids = list(dict.fromkeys(frame_id.split("_f")[0] for frame_id in ids))
    return json.dumps({"beats": [{"id": beat_id, "description": f"先抬头示意，再把袋子举到胸前（{beat_id}）。"} for beat_id in beat_ids]}, ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        raw_body = self.rfile.read(length)
        body = json.loads(raw_body.decode("utf-8", "ignore") or "{}")
        ids = [str(frame.get("id") or "") for frame in body.get("frames") or []]
        describe = "分镜描述器" in str(body.get("prompt") or "")
        STATE["calls"].append({"frames": ids, "maxTokens": body.get("maxTokens"), "describe": describe})
        mode = STATE["mode"]
        if STATE["delay"]:
            time.sleep(float(STATE["delay"]))
        if mode == "fail_multi" and len(ids) > 1:
            self._json(500, {"error": {"code": "dsh_vision_failed", "message": "Response incomplete: length"}})
            return
        text = _beats(ids) if describe else _rows(ids)
        self._json(200, {"dsh": {"provider": "deepseek-official", "model": "deepseek-flash", "text": text}})

    def _json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


def _frame(directory: Path, name: str, beat_id: str) -> dict:
    path = directory / f"{name}.jpg"
    Image.new("RGB", (64, 64), (200, 50, 50)).save(path, format="JPEG")
    return {"id": name, "beat_id": beat_id, "start_s": 0, "end_s": 2, "path": path}


def check_single_frame(directory: Path) -> None:
    STATE.update({"mode": "ok", "delay": 0.0, "calls": []})
    rows = vision.analyze_frames([_frame(directory, "b0_f0", "b0")])
    assert rows["b0_f0"]["product"] == "苹果", rows
    assert vision.LAST_PROVIDER == "dsh", vision.LAST_PROVIDER
    assert vision.LAST_MODEL == "deepseek-flash", vision.LAST_MODEL
    assert vision.LAST_ERROR == "", vision.LAST_ERROR
    call = STATE["calls"][-1]
    assert call["maxTokens"] >= 4000, call


def check_batches_and_budget(directory: Path) -> None:
    """Seven frames must not travel in one request, and budget scales with frames."""
    STATE.update({"mode": "ok", "delay": 0.0, "calls": []})
    os.environ["ADSTUDIO_DSH_VISION_BATCH"] = "4"
    try:
        frames = [_frame(directory, f"b0_f{index}", "b0") for index in range(7)]
        rows = vision.analyze_frames(frames, max_frames=7)
    finally:
        os.environ.pop("ADSTUDIO_DSH_VISION_BATCH", None)
    assert set(rows) == {frame["id"] for frame in frames}, sorted(rows)
    sizes = [len(call["frames"]) for call in STATE["calls"]]
    assert sizes == [4, 3], sizes
    assert STATE["calls"][0]["maxTokens"] == 12000, STATE["calls"][0]
    assert STATE["calls"][1]["maxTokens"] == 9000, STATE["calls"][1]
    assert all(item["status"] == "ok" for item in vision.LAST_ATTEMPTS), vision.LAST_ATTEMPTS


def check_bisect_recovers(directory: Path) -> None:
    """A batch that fails as a whole is split instead of losing every label."""
    STATE.update({"mode": "fail_multi", "delay": 0.0, "calls": []})
    frames = [_frame(directory, f"b0_f{index}", "b0") for index in range(4)]
    rows = vision.analyze_frames(frames, max_frames=4)
    assert set(rows) == {frame["id"] for frame in frames}, sorted(rows)
    assert STATE["calls"][0]["frames"] == ["b0_f0", "b0_f1", "b0_f2", "b0_f3"], STATE["calls"][0]
    failed = [item for item in vision.LAST_ATTEMPTS if item["status"] == "failed"]
    assert failed and failed[0]["frames"] == 4, vision.LAST_ATTEMPTS
    assert vision.LAST_ERROR == "", vision.LAST_ERROR


def check_deadline_keeps_partial(directory: Path) -> None:
    """After the total deadline, labelled frames survive and the rest are skipped."""
    STATE.update({"mode": "ok", "delay": 1.5, "calls": []})
    os.environ["ADSTUDIO_DSH_VISION_BATCH"] = "1"
    os.environ["ADSTUDIO_DSH_VISION_TIMEOUT"] = "10"
    os.environ["ADSTUDIO_DSH_VISION_DEADLINE"] = "1"
    try:
        frames = [_frame(directory, f"b1_f{index}", "b1") for index in range(2)]
        rows = vision.analyze_frames(frames, max_frames=2)
    finally:
        os.environ.pop("ADSTUDIO_DSH_VISION_BATCH", None)
        os.environ.pop("ADSTUDIO_DSH_VISION_TIMEOUT", None)
        os.environ.pop("ADSTUDIO_DSH_VISION_DEADLINE", None)
    assert list(rows) == ["b1_f0"], sorted(rows)
    statuses = [item["status"] for item in vision.LAST_ATTEMPTS]
    assert "skipped" in statuses, statuses
    assert len(STATE["calls"]) == 1, STATE["calls"]


def check_describe_groups_by_shot(directory: Path) -> None:
    """Describe keeps a shot's frames together and returns one paragraph per shot."""
    STATE.update({"mode": "ok", "delay": 0.0, "calls": []})
    os.environ["ADSTUDIO_DSH_DESCRIBE_BATCH"] = "2"
    try:
        frames = [
            _frame(directory, "s0_f0", "s0"),
            _frame(directory, "s0_f1", "s0"),
            _frame(directory, "s1_f0", "s1"),
            _frame(directory, "s1_f1", "s1"),
        ]
        beats = [
            {"id": "s0", "start_s": 0, "end_s": 2, "dialogue_text": "看这袋苹果"},
            {"id": "s1", "start_s": 2, "end_s": 4, "dialogue_text": "九块九"},
        ]
        described = vision.describe_beats(frames, beats)
    finally:
        os.environ.pop("ADSTUDIO_DSH_DESCRIBE_BATCH", None)
    assert set(described) == {"s0", "s1"}, described
    assert described["s0"].startswith("先抬头示意"), described
    assert [call["frames"] for call in STATE["calls"]] == [["s0_f0", "s0_f1"], ["s1_f0", "s1_f1"]], STATE["calls"]
    assert vision.LAST_ERROR == "", vision.LAST_ERROR


def check_ark_disabled_is_reported(directory: Path) -> None:
    """A rung with no enabled model must name itself instead of returning silence."""
    from adclip import settings

    settings.set_enabled_text_models([])
    try:
        rows = vision._analyze_ark([_frame(directory, "b2_f0", "b2")])
    finally:
        settings.MODEL_PREFS.unlink(missing_ok=True)
    assert rows == {}, rows
    assert "未启用" in vision.LAST_ERROR, vision.LAST_ERROR


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    directory = Path(tempfile.mkdtemp())
    try:
        vision.DSH_VISION_URL = f"http://127.0.0.1:{server.server_port}/adplus/api/dsh/vision"
        check_single_frame(directory)
        check_batches_and_budget(directory)
        check_bisect_recovers(directory)
        check_deadline_keeps_partial(directory)
        check_describe_groups_by_shot(directory)
        check_ark_disabled_is_reported(directory)
    finally:
        server.shutdown()
        server.server_close()
    print("adclip vision fallback: ok")


if __name__ == "__main__":
    main()
