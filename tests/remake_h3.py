"""H3 reference pipeline offline integration check.

The H3 provider is replaced with a local copy of the reference clip and the
MiniMax Files API is not called, so this verifies the run branch, prompt,
post and QA without a paid request.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_h3.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-h3-run-")
os.environ.pop("ADCLIP_TEST_MODE", None)
os.environ["MINIMAX_API_KEY"] = "test-key"
os.environ["ADSTUDIO_ASR"] = "0"
os.environ["ADSTUDIO_VISION"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from adclip.api import app  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.pipeline import script  # noqa: E402
from adclip.providers.minimax import MiniMaxProvider  # noqa: E402

# Keep the text model out of this offline test; the script falls back locally.
script.llm.chat_json = lambda *args, **kwargs: None


def make_video(path: Path) -> None:
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "5", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True)


def poll(client: TestClient, run_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/runs/{run_id}").json()["run"]
        if run["status"] == "awaiting_confirm":
            client.post(f"/runs/{run_id}/confirm")
        if run["status"] in {"succeeded", "failed", "canceled"}:
            return run
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} timed out")


def main() -> None:
    def fake_generate(self, prompt, *, images=None, duration=6, resolution="768P", aspect="9:16", model="", output, reference_video=None, reference_audio=None, ratio=None, generate_audio=True):
        assert reference_video is not None, "H3 branch must pass the reference video"
        assert "参考视频1" in prompt, prompt
        if "保留参考视频1的原声" in prompt:
            assert ffmpeg.probe(reference_video)["has_audio"] is True, "preserve must keep reference audio"
        else:
            assert "按时间顺序逐句念" in prompt, prompt
            assert ffmpeg.probe(reference_video)["has_audio"] is False, "regenerate must strip reference audio"
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reference_video, output)
        return output

    MiniMaxProvider.generate = fake_generate
    try:
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "ref.mp4"
            make_video(clip)
            client = TestClient(app)
            asset = client.post(
                "/assets/upload?kind=video&name=ref.mp4",
                content=clip.read_bytes(),
                headers={"content-type": "video/mp4"},
            ).json()["asset"]
            created = client.post("/runs", json={
                "scenario": "viral-remake",
                "inputs": {"reference_asset_id": asset["id"], "brief": "「豆豆云朵被，当前折扣价七十多」只换商品，保留原片"},
                "advanced": {"replace_scope": "product", "person_scope": "main", "duration": 30},
            })
            assert created.status_code == 202, created.text
            run = poll(client, created.json()["run"]["id"])
            assert run["status"] == "succeeded", run.get("error")
            assert run["selection"]["mode"] == "h3_reference", run.get("selection")
            assert run["result"]["video"].endswith("final.mp4"), run.get("result")
            assert run["result"].get("audio_source") == "h3", run.get("result")
            assert abs(float(run["result"]["duration_s"]) - 5.0) <= 0.3, run["result"]
            analysis = client.get(f"/runs/{run['id']}/analysis").json()
            assert analysis["available"] is True
            assert analysis["remake_plan"]["shots"], analysis

            parent_id = run["id"]
            parent_version = run["version"]
            edited = client.post(f"/runs/{parent_id}/segments/s0/edit", json={"instruction": "把这个镜头换成近景，价格念清楚"})
            assert edited.status_code == 202, edited.text
            child = edited.json()["run"]
            assert child["id"] != parent_id
            assert child["parent_run_id"] == parent_id
            assert child["selection"]["mode"] == "h3_reference", child.get("selection")
            assert child["inputs"]["explicit_overrides"], child["inputs"]
            parent = client.get(f"/runs/{parent_id}").json()["run"]
            assert parent["status"] == "succeeded", parent
            assert parent["version"] == parent_version
            child = poll(client, child["id"])
            assert child["status"] == "succeeded", child.get("error")

            preserved = client.post("/runs", json={
                "scenario": "viral-remake",
                "inputs": {"reference_asset_id": asset["id"], "brief": "「豆豆云朵被，七十多」只换商品"},
                "advanced": {"replace_scope": "person", "person_scope": "main", "audio_mode": "preserve", "duration": 30},
            })
            assert preserved.status_code == 202, preserved.text
            preserved_run = poll(client, preserved.json()["run"]["id"])
            assert preserved_run["status"] == "succeeded", preserved_run.get("error")
            assert preserved_run["result"].get("audio_source") == "reference", preserved_run.get("result")
            assert abs(float(preserved_run["result"]["duration_s"]) - 5.0) <= 0.3, preserved_run["result"]
    finally:
        # The provider class is process-local; restore is unnecessary for this
        # isolated test process, but keep the assignment explicit.
        pass
    print("adclip remake h3: ok")


if __name__ == "__main__":
    main()
