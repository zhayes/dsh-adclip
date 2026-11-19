"""ASR status, dialogue timeline and beat snapping checks.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_timeline.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-timeline-")
os.environ["ADCLIP_TEST_MODE"] = "1"
os.environ["ADSTUDIO_VISION"] = "0"
os.environ.pop("ADSTUDIO_ASR", None)

from adclip import store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import analyze  # noqa: E402

TRANSCRIPT = [
    {"start_s": 0.4, "end_s": 2.6, "text": "第一句跨过第一个切点"},
    {"start_s": 2.8, "end_s": 3.6, "text": "第二句"},
    {"start_s": 4.2, "end_s": 5.4, "text": "第三句跨过第二个切点"},
]


def _beats(count: int = 3) -> list[dict]:
    """Explicit beats so assignment can be tested without the cut detector."""
    length = 6.0 / count
    return [
        {"id": f"b{i}", "start_s": round(i * length, 3), "end_s": round((i + 1) * length, 3),
         "len_s": round(length, 2), "dialogue": [], "dialogue_rows": []}
        for i in range(count)
    ]


def check_single_take() -> None:
    # Motion is not a shot boundary: no validated cuts means one beat.
    assert len(analyze._beats(6.0, [])) == 1, analyze._beats(6.0, [])
    assert len(analyze._beats(11.238, [2.267, 8.767])) == 3, analyze._beats(11.238, [2.267, 8.767])


def check_dialogue_gaps() -> None:
    beats = analyze._beats(6.0, [], transcript=TRANSCRIPT)
    assert len(beats) == 2, beats
    assert any(abs(float(beat["start_s"]) - 3.9) < 0.35 for beat in beats), beats


def check_assignment() -> None:
    beats = _beats()
    assert len(beats) == 3, beats
    analyze._assign_transcript(beats, TRANSCRIPT)
    rows = [row for beat in beats for row in beat.get("dialogue_rows") or []]
    assert len(rows) == len(TRANSCRIPT), rows
    assert [row["text"] for row in rows] == [item["text"] for item in TRANSCRIPT], rows
    assert all(float(row["start_s"]) < float(row["end_s"]) for row in rows), rows
    assert any(row["crosses_boundary"] for row in rows), rows
    assert [line for beat in beats for line in beat["dialogue"]] == [item["text"] for item in TRANSCRIPT]


def check_snapping() -> None:
    beats = [
        {"id": "b0", "start_s": 0.0, "end_s": 2.0, "len_s": 2.0, "dialogue_rows": [{"start_s": 1.0, "end_s": 2.25, "text": "a", "crosses_boundary": True}]},
        {"id": "b1", "start_s": 2.0, "end_s": 4.0, "len_s": 2.0, "dialogue_rows": [{"start_s": 2.4, "end_s": 3.0, "text": "b", "crosses_boundary": False}]},
    ]
    analyze._snap_beats(beats)
    assert beats[0]["end_s"] == 2.25, beats
    assert beats[1]["start_s"] == 2.25, beats
    assert beats[1]["len_s"] == 1.75, beats
    rows = [row for beat in beats for row in beat["dialogue_rows"]]
    assert all(not row["crosses_boundary"] for row in rows), rows


def _source_asset() -> str:
    store.ensure_dirs()
    media = store.ASSETS / "a_timeline.mp4"
    if not media.is_file():
        ffmpeg.make_synthetic_clip(None, media, duration=6, width=240, height=426, fps=24)
    asset_id = "a_timeline"
    store.atomic_write_json(store.ASSETS / f"{asset_id}.json", {
        "id": asset_id,
        "kind": "video",
        "name": "timeline.mp4",
        "path": "assets/a_timeline.mp4",
    })
    return asset_id


def _run(asset_id: str) -> Run:
    run = Run(
        id=store.new_id("run"),
        scenario="viral-remake",
        title="timeline",
        inputs={"reference_asset_id": asset_id, "brief": ""},
        advanced={"duration": 6, "aspect": "9:16"},
        steps=[RunStep(name="analyze", label="拆解")],
        created_at=store.now(),
    )
    store.write_run(run)
    return run


def _stub_asr(*, available: bool, disabled: bool = False, transcript=None, error: str = ""):
    class Stub:
        LAST_ERROR = error
        LAST_MODEL = "stub"

        @staticmethod
        def available() -> bool:
            return available

        @staticmethod
        def disabled() -> bool:
            return disabled

        @staticmethod
        def transcribe(path, *, max_seconds=60.0, prompt_hint=""):
            Stub.LAST_ERROR = error
            return list(transcript or [])

    return Stub


def check_missing_asr(asset_id: str) -> None:
    original = analyze.asr
    analyze.asr = _stub_asr(available=False)
    try:
        skeleton = analyze.analyze(_run(asset_id).id)
    finally:
        analyze.asr = original
    info = skeleton["analysis"]["asr"]
    assert info["source"] == "not_installed", info
    assert info["lines"] == 0, info
    assert any("ASR 未安装" in warning for warning in skeleton["analysis"]["warnings"]), skeleton["analysis"]["warnings"]
    assert all(beat["dialogue_source"] == "not_installed" for beat in skeleton["beats"]), skeleton["beats"]


def check_failed_asr(asset_id: str) -> None:
    original = analyze.asr
    analyze.asr = _stub_asr(available=True, transcript=[], error="模型下载超时")
    try:
        skeleton = analyze.analyze(_run(asset_id).id)
    finally:
        analyze.asr = original
    info = skeleton["analysis"]["asr"]
    assert info["source"] == "failed", info
    assert "模型下载超时" in info["error"], info
    assert any("ASR 转写失败" in warning for warning in skeleton["analysis"]["warnings"]), skeleton["analysis"]["warnings"]


def check_timeline_in_skeleton(asset_id: str) -> None:
    original = analyze.asr
    analyze.asr = _stub_asr(available=True, transcript=TRANSCRIPT)
    try:
        skeleton = analyze.analyze(_run(asset_id).id)
    finally:
        analyze.asr = original
    assert skeleton["analysis"]["asr"]["source"] == "asr", skeleton["analysis"]["asr"]
    assert skeleton["analysis"]["asr"]["lines"] == len(TRANSCRIPT), skeleton["analysis"]["asr"]
    assert len(skeleton["transcript"]) == len(TRANSCRIPT), skeleton["transcript"]
    rows = [row for beat in skeleton["beats"] for row in beat.get("dialogue_rows") or []]
    assert len(rows) == len(TRANSCRIPT), rows
    shots = skeleton["remake_plan"]["shots"]
    assert shots and any(shot.get("dialogue_rows") for shot in shots), shots
    assert all(beat["dialogue_source"] == "asr" for beat in skeleton["beats"]), skeleton["beats"]


def main() -> None:
    check_single_take()
    check_dialogue_gaps()
    check_assignment()
    check_snapping()
    asset_id = _source_asset()
    check_missing_asr(asset_id)
    check_failed_asr(asset_id)
    check_timeline_in_skeleton(asset_id)
    print("adclip remake timeline: ok")


if __name__ == "__main__":
    main()
