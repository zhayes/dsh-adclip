"""MiniMax -> DSH vision fallback checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/vision_fallback.py
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-vision-")
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "1"
os.environ.pop("MINIMAX_API_KEY", None)

from PIL import Image  # noqa: E402

from adclip.media import vision  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        describe = "分镜描述器" in body.decode("utf-8", "ignore")
        text = (
            json.dumps({"beats": [{"id": "b0", "description": "先抬头示意，再把袋子举到胸前。"}]}, ensure_ascii=False)
            if describe else
            json.dumps({
                "frames": [{
                    "id": "b0",
                    "shot_size": "中景",
                    "action": "人物拿着苹果",
                    "people": "一名女性",
                    "product": "苹果",
                    "scene": "室内",
                    "on_screen_text": "",
                }]
            }, ensure_ascii=False)
        )
        payload = {
            "dsh": {
                "provider": "deepseek-official",
                "model": "deepseek-flash",
                "text": text,
            }
        }
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        vision.DSH_VISION_URL = f"http://127.0.0.1:{server.server_port}/adplus/api/dsh/vision"
        frame = Path(tempfile.mkdtemp()) / "b0.jpg"
        Image.new("RGB", (64, 64), (200, 50, 50)).save(frame, format="JPEG")
        rows = vision.analyze_frames([{"id": "b0", "start_s": 0, "end_s": 2, "path": frame}])
        assert rows["b0"]["product"] == "苹果", rows
        assert vision.LAST_PROVIDER == "dsh", vision.LAST_PROVIDER
        assert vision.LAST_MODEL == "deepseek-flash", vision.LAST_MODEL
        assert vision.LAST_ERROR == "", vision.LAST_ERROR

        described = vision.describe_beats(
            [{"id": "b0", "beat_id": "b0", "start_s": 0, "end_s": 2, "path": frame}],
            [{"id": "b0", "start_s": 0, "end_s": 2, "dialogue_text": "看这袋苹果"}],
        )
        assert described["b0"].startswith("先抬头示意"), described
        assert vision.LAST_PROVIDER == "dsh", vision.LAST_PROVIDER
        assert vision.LAST_ERROR == "", vision.LAST_ERROR
    finally:
        server.shutdown()
        server.server_close()
    print("adclip vision fallback: ok")


if __name__ == "__main__":
    main()
