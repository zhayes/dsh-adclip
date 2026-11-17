"""Segment-edit failure handling and historical repair checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/segment_edit.py
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-segment-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"
os.environ["ADSTUDIO_TEXT_PROVIDER"] = "minimax"

from fastapi.testclient import TestClient  # noqa: E402

from adclip import store  # noqa: E402
from adclip.api import app  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402


def make_video(path: Path) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True)


def poll(client: TestClient, run_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/runs/{run_id}").json()["run"]
        if run["status"] in {"succeeded", "failed", "canceled"}:
            return run
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} timed out")


def check_missing_script_keeps_success(client: TestClient, tmp: Path) -> None:
    clip = tmp / "ref.mp4"
    make_video(clip)
    asset = client.post(
        "/assets/upload?kind=video&name=ref.mp4",
        content=clip.read_bytes(),
        headers={"content-type": "video/mp4"},
    ).json()["asset"]
    created = client.post("/runs", json={
        "scenario": "viral-remake",
        "inputs": {"reference_asset_id": asset["id"], "brief": "保留原片"},
    })
    run = poll(client, created.json()["run"]["id"])
    assert run["status"] == "succeeded", run.get("error")
    script_path = store.run_dir(run["id"]) / "artifacts" / "script.json"
    script_path.unlink()
    res = client.post(f"/runs/{run['id']}/segments/s0/edit", json={"instruction": "改成近景"})
    assert res.status_code == 409, res.text
    after = client.get(f"/runs/{run['id']}").json()["run"]
    assert after["status"] == "succeeded", after
    assert not after.get("error"), after


def check_repair(tmp: Path) -> None:
    run_id = store.new_id("run")
    store.run_dir(run_id).mkdir(parents=True, exist_ok=True)
    final = store.run_dir(run_id) / "artifacts" / "final.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(final),
    ], check=True)
    run = Run(
        id=run_id,
        scenario="viral-remake",
        title="repair fixture",
        status="failed",
        step="segment",
        progress=0.05,
        steps=[RunStep(name="qa", label="检查", status="done")],
        result={
            "video": store.rel_to_data(final),
            "qa": {"summary": {"shippable": True, "pass": 3, "warn": 0, "fail": 0}},
        },
        error="ValueError: segment not found",
        created_at=store.now(),
        finished_at=store.now(),
        demo=False,
    )
    store.write_run(run)
    repaired = store.repair_segment_edit_failures()
    assert run_id in repaired, repaired
    after = store.read_run(run_id)
    assert after is not None and after.status == "succeeded", after
    assert after.error is None
    assert "segment not found" in str(after.last_edit_error), after.last_edit_error


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        check_missing_script_keeps_success(TestClient(app), Path(tmp))
    check_repair(Path(tempfile.mkdtemp()))
    print("adclip segment edit: ok")


if __name__ == "__main__":
    main()
