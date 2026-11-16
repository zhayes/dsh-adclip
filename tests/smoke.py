"""End-to-end smoke test for the demo pipeline.

Run with:
  PYTHONPATH=src .venv/bin/python tests/smoke.py
It creates a temporary test video with ffmpeg, uploads it, runs the demo
pipeline, reads the storyboard, creates a persona, derives a version and
stitches two clips.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

# Keep smoke runs out of the user's Ad+ data directory.
_TEST_DATA = tempfile.mkdtemp(prefix="adclip-smoke-")
os.environ["ADSTUDIO_DATA_DIR"] = _TEST_DATA
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from adclip.api import app  # noqa: E402


def make_video(path: Path, freq: int = 440) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000", "-t", "3", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True)


def poll(client: TestClient, run_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/runs/{run_id}").json()["run"]
        if run["status"] in {"succeeded", "failed", "canceled"}:
            return run
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} timed out")


def main() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["ok"] is True
    assert client.get("/models").json()["models"]
    assert client.get("/scenarios").json()["scenarios"]

    with tempfile.TemporaryDirectory() as tmp:
        one = Path(tmp) / "one.mp4"
        two = Path(tmp) / "two.mp4"
        make_video(one, 440)
        make_video(two, 660)

        def upload(path: Path) -> dict:
            res = client.post(
                f"/assets/upload?kind=video&name={path.name}",
                content=path.read_bytes(),
                headers={"content-type": "video/mp4"},
            )
            assert res.status_code == 200, res.text
            return res.json()["asset"]

        a = upload(one)
        b = upload(two)

        res = client.post("/runs", json={
            "scenario": "viral-remake",
            "inputs": {"reference_asset_id": a["id"], "brief": "这个产品现在活动价 19.9，卖点是不油腻，最后引导下单。"},
            "advanced": {"duration": 6, "aspect": "9:16", "resolution": "720p", "generation_mode": "fast"},
        })
        assert res.status_code == 202, res.text
        run = poll(client, res.json()["run"]["id"])
        assert run["status"] == "succeeded", run.get("error")
        assert run["result"]["video"].endswith("final.mp4")

        storyboard = client.get(f"/runs/{run['id']}/storyboard")
        assert storyboard.status_code == 200
        assert len(storyboard.json()["segments"]) >= 1

        persona = client.post("/personas", json={
            "name": "测试女主", "type": "ai", "gender": "female", "age": "middle_aged",
            "ethnicity": "asian", "body_type": "standard", "outfit": "职场",
            "consent": {"confirmed": True, "note": "smoke test"},
        })
        assert persona.status_code == 200, persona.text
        assert persona.json()["persona"]["gender"] == "female"

        assistant = client.post("/assistant", json={
            "message": "改成横屏1080p，模特换成女性，年龄大一点，字幕大一点",
            "context": {"advanced": {"aspect": "9:16", "resolution": "720p", "persona": {"gender": "any", "age": "youth", "body_type": "standard"}}, "post": {"subtitle_size": 32}},
        })
        assert assistant.status_code == 200
        fields = {item["field"] for item in assistant.json()["changes"]}
        assert "advanced.aspect" in fields and "persona.gender" in fields

        derived = client.post(f"/runs/{run['id']}/derive", json={"changes": [
            {"field": "advanced.aspect", "to": "16:9", "stage": "generate"},
            {"field": "advanced.duration", "to": 5, "stage": "generate"},
        ]})
        assert derived.status_code == 200
        derived_run = poll(client, derived.json()["run"]["id"])
        assert derived_run["status"] == "succeeded"

        plan = client.post("/stitch/plan", json={
            "clips": [{"asset_id": a["id"]}, {"asset_id": b["id"]}],
            "output": {"aspect": "9:16", "resolution": "720p"},
            "fit": "blur_pad", "transition": "cut", "audio": "keep",
        })
        assert plan.status_code == 200, plan.text
        stitched = client.post("/stitch", json={
            "clips": [{"asset_id": a["id"]}, {"asset_id": b["id"]}],
            "output": {"aspect": "9:16", "resolution": "720p"},
            "fit": "blur_pad", "transition": "cut", "audio": "keep",
        })
        assert stitched.status_code == 200, stitched.text
        assert stitched.json()["run"]["status"] == "succeeded"

        media = client.get("/media", params={"path": run["result"]["video"]})
        assert media.status_code == 200 and media.content
        export = client.get(f"/runs/{run['id']}/export")
        assert export.status_code == 200 and export.content

        post = client.post(f"/runs/{run['id']}/derive", json={"changes": [
            {"field": "post.export_bitrate", "to": "4M", "stage": "post"},
        ]})
        assert post.status_code == 200, post.text
        post_run = post.json()["run"]
        assert post_run["status"] == "succeeded"
        assert post_run["result"]["post_only"] is True
        assert [step["name"] for step in post_run["steps"]] == ["post"]

    print("adclip smoke: ok")


if __name__ == "__main__":
    main()
