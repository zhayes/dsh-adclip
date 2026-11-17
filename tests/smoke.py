"""End-to-end smoke test for the generation pipeline.

Run with:
  PYTHONPATH=src .venv/bin/python tests/smoke.py
It creates a temporary test video with ffmpeg, uploads it, runs the synthetic
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
os.environ["ADCLIP_TEST_MODE"] = "1"
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


VIDEO_CAPS = {"text_to_video", "image_to_video", "reference_to_video"}
IMAGE_CAPS = {"text_to_image", "image_to_image"}


def check_catalogue(client: TestClient) -> None:
    """Every model carries kind + capabilities; kinds, aliases and keys agree."""
    rows = client.get("/models").json()["models"]
    ids = [row["id"] for row in rows]
    assert ids and len(ids) == len(set(ids)), "model ids must be unique"
    for row in rows:
        assert row["kind"] in {"video", "image"}, row
        caps = set(row.get("capabilities") or [])
        assert caps, row["id"]
        allowed = VIDEO_CAPS if row["kind"] == "video" else IMAGE_CAPS
        assert caps <= allowed, (row["id"], caps - allowed)

    image_ids = {row["id"] for row in rows if row["kind"] == "image"}
    alias_ids = {row["id"] for row in client.get("/image/models").json()["models"]}
    assert alias_ids == image_ids, (alias_ids, image_ids)

    seedream = next(row for row in rows if row["id"] == "ark.seedream-4.0")
    assert seedream["kind"] == "image" and "text_to_image" in seedream["capabilities"]
    assert seedream["available"] == bool(os.environ.get("ARK_API_KEY", "").strip())

    settings_rows = client.get("/settings/models").json()["models"]
    assert "ark.seedream-4.0" in {row["id"] for row in settings_rows}
    assert any(row["kind"] == "image" for row in settings_rows)

    # The production view ships no local placeholder model.
    os.environ.pop("ADCLIP_TEST_MODE", None)
    try:
        production = {row["id"] for row in client.get("/models").json()["models"]}
        assert "demo" not in production and "test.synthetic" not in production
    finally:
        os.environ["ADCLIP_TEST_MODE"] = "1"


def main() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["ok"] is True
    assert client.get("/models").json()["models"]
    assert client.get("/scenarios").json()["scenarios"]
    check_catalogue(client)

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

        # Subtitles default to off: no SRT, and QA says so instead of warning.
        assert run["result"].get("srt") is None, run["result"].get("srt")
        checks = {check["id"]: check for check in run["result"]["qa"]["checks"]}
        assert checks["subtitles"]["status"] == "pass", checks["subtitles"]
        assert "未启用" in checks["subtitles"].get("note", "")

        # Turning them on delivers the sidecar SRT.
        with_srt = client.post("/runs", json={
            "scenario": "viral-remake",
            "inputs": {"reference_asset_id": a["id"], "brief": "同一条片子，带字幕交付。"},
            "advanced": {"duration": 5, "aspect": "9:16", "resolution": "720p", "generation_mode": "fast", "subtitle": "sidecar"},
        })
        assert with_srt.status_code == 202, with_srt.text
        srt_run = poll(client, with_srt.json()["run"]["id"])
        assert srt_run["status"] == "succeeded", srt_run.get("error")
        assert (srt_run["result"].get("srt") or "").endswith("subtitles.srt")

        # A post-only derive toggles it back off, then on again.
        off = client.post(f"/runs/{srt_run['id']}/derive", json={"changes": [
            {"field": "post.subtitle", "to": "off", "stage": "post"},
        ]})
        assert off.status_code == 200, off.text
        off_run = off.json()["run"]
        assert off_run["result"].get("srt") is None
        assert any("字幕" in note for note in off_run["result"].get("post_notes") or [])

        back_on = client.post(f"/runs/{off_run['id']}/derive", json={"changes": [
            {"field": "post.subtitle", "to": "sidecar", "stage": "post"},
        ]})
        assert back_on.status_code == 200, back_on.text
        assert (back_on.json()["run"]["result"].get("srt") or "").endswith("subtitles.srt")

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
