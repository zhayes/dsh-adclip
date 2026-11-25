"""Per-shot remake sequence: mask, carry the character, stitch.

Ark refuses a photoreal face in any reference material, so a remake through Ark
regenerates the person on every shot. The character only survives because Ark
trusts its own last frame, which makes shot N+1 depend on shot N.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_sequence.py
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-seq-")
os.environ["ADCLIP_TEST_MODE"] = "0"
os.environ.pop("MINIMAX_API_KEY", None)
os.environ["ARK_API_KEY"] = "test-key"

from adclip import store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import generate  # noqa: E402


def main() -> None:
    store.ensure_dirs()
    work = Path(tempfile.mkdtemp(prefix="adclip-seq-src-"))
    source = work / "reference.mp4"
    ffmpeg.make_synthetic_clip(None, source, duration=6, width=360, height=640)

    run = Run(
        id=store.new_id("run"),
        scenario="viral-remake",
        title="sequence",
        inputs={"reference_asset_id": "a_seq", "product_asset_ids": []},
        advanced={"replace_scope": "product", "aspect": "9:16", "resolution": "720p"},
        steps=[RunStep(name="generate", label="生成")],
        created_at=store.now(),
        selection={"mode": "keyframe", "rung": "keyframe", "model": "ark.seedance-2.0-fast"},
    )
    store.write_run(run)
    artifacts = store.run_dir(run.id) / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    store.atomic_write_json(artifacts / "skeleton.json", {
        "source": {"duration_s": 6.0, "aspect": "9:16"},
        "beats": [{"id": "b1", "start_s": 0.0, "end_s": 3.0}, {"id": "b2", "start_s": 3.0, "end_s": 6.0}],
        "remake_plan": {
            "shots": [
                {"start_s": 0.0, "end_s": 3.0, "description": "人物站在货车前指向镜头"},
                {"start_s": 3.0, "end_s": 6.0, "description": "人物弯腰拆开纸箱"},
            ]
        },
    })
    # Dialogue comes from the script, matched to the skeleton beat by id.
    store.atomic_write_json(artifacts / "script.json", {
        "beats": [
            {"id": "b1", "lines": [{"text": "第一镜的台词"}]},
            {"id": "b2", "lines": [{"text": "第二镜的台词"}]},
        ]
    })

    calls: list[dict] = []

    class Fake:
        id = "ark"

        def generate(self, prompt, *, images=None, duration=4, resolution="720p",
                     aspect="9:16", model="", output, return_last_frame=False, meta=None):
            calls.append({"images": list(images or []), "duration": duration, "prompt": prompt})
            output.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg.make_synthetic_clip(None, output, duration=float(duration), width=180, height=320)
            last = output.with_name(f"last_frame_{len(calls)}.jpg")
            ffmpeg.extract_frame(output, 0.05, last, width=180)
            if meta is not None:
                meta["last_frame_url"] = "https://example.com/last.jpg"
                meta["last_frame_path"] = str(last)
            return output

    original_adapter = generate._adapter
    original_media = store.asset_media_path
    generate._adapter = lambda model_id: Fake()
    store.asset_media_path = lambda asset_id: source
    try:
        result = generate.generate(run.id)
    finally:
        generate._adapter = original_adapter
        store.asset_media_path = original_media

    assert result["shot_count"] == 2, result
    assert len(calls) == 2, calls
    assert len(result["segments"]) == 2, result
    assert Path(result["path"]).is_file(), result

    # Shot 1 has no predecessor, so it sends only its own masked anchor.
    first = [str(item) for item in calls[0]["images"]]
    assert first and first[0].endswith("anchor_0.jpg"), first
    assert all("last_frame" not in item for item in first), first
    assert "图片2=本片固定的主持人" not in calls[0]["prompt"], calls[0]["prompt"]

    # Shot 2 receives shot 1's last frame as the character, and the prompt says so.
    second = [str(item) for item in calls[1]["images"]]
    assert second and second[0].endswith("anchor_1.jpg"), second
    # The hand-off is the URL Ark returned, never a local re-save: a re-encoded
    # frame loses the trust that lets a face through at all.
    assert second[-1] == "https://example.com/last.jpg", second
    assert "图片2=本片固定的主持人" in calls[1]["prompt"], calls[1]["prompt"]

    # Every picture must be claimed exactly once: the ordinals in the text have
    # to cover 1..len(images) with no gap and no overflow. A wrong ordinal is a
    # semantic error — the model reads that picture as something it is not.
    for call in calls:
        used = sorted({int(n) for n in re.findall(r"图片(\d+)", call["prompt"])})
        assert used == list(range(1, len(call["images"]) + 1)), (
            used, len(call["images"]), call["prompt"]
        )

    # Both shots are asked for a provider duration, never a fractional one.
    assert all(isinstance(call["duration"], int) and call["duration"] >= 4 for call in calls), calls

    # Dialogue rides in each shot's own prompt: no dubbing step exists, so the
    # model has to say that shot's lines and must not inherit its neighbour's.
    assert "第一镜的台词" in calls[0]["prompt"], calls[0]["prompt"]
    assert "第二镜的台词" not in calls[0]["prompt"], calls[0]["prompt"]
    assert "第二镜的台词" in calls[1]["prompt"], calls[1]["prompt"]
    assert "第一镜的台词" not in calls[1]["prompt"], calls[1]["prompt"]
    assert "【台词】" in calls[0]["prompt"], calls[0]["prompt"]
    # A one-shot prompt must not talk about cut points it does not have.
    assert "这一镜" in calls[0]["prompt"], calls[0]["prompt"]

    # A single-shot reference keeps the single-clip path.
    store.atomic_write_json(artifacts / "skeleton.json", {
        "source": {"duration_s": 3.0, "aspect": "9:16"},
        "remake_plan": {"shots": [{"start_s": 0.0, "end_s": 3.0, "description": "一镜到底"}]},
    })
    assert generate.generate_sequence(run.id, run.selection) is None, "single-shot runs keep the single-clip path"
    print("adclip remake sequence: ok")


if __name__ == "__main__":
    main()
