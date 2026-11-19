"""Remake rung policy checks: ladder shape, eligibility, degradation.

Run with:
  PYTHONPATH=src .venv/bin/python tests/remake_policy.py
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADSTUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="adclip-policy-")
os.environ["ADCLIP_TEST_MODE"] = "0"
os.environ.pop("MINIMAX_API_KEY", None)
os.environ.pop("ARK_API_KEY", None)

from adclip import catalog, remake_policy, store  # noqa: E402
from adclip.media import ffmpeg  # noqa: E402
from adclip.models import Run, RunStep  # noqa: E402
from adclip.pipeline import generate  # noqa: E402


def _run_like(duration: float = 11.0, size: int | None = None, scope: str = "both") -> Run:
    return Run(
        id="run_policy_probe",
        scenario="viral-remake",
        title="policy",
        inputs={"reference_asset_id": "a_probe", "brief": "换成鱿鱼须，49 块 8"},
        advanced={"duration": duration, "aspect": "9:16", "replace_scope": scope},
        steps=[RunStep(name="analyze", label="拆解")],
        created_at=store.now(),
    )


def check_chain() -> None:
    os.environ["ARK_API_KEY"] = "test-key"
    try:
        chain = catalog.remake_chain()
        assert [entry["rung"] for entry in chain] == ["full", "reference", "keyframe", "generation"], chain
        by_rung = {entry["rung"]: entry for entry in chain}
        assert by_rung["full"]["available"] is False, by_rung["full"]
        assert "MINIMAX_API_KEY" in by_rung["full"]["reason"], by_rung["full"]
        # A direct-video rung is only usable when the adapter can send the video.
        assert by_rung["reference"]["available"] is False, by_rung["reference"]
        assert "暂不启用" in by_rung["reference"]["reason"], by_rung["reference"]
        assert by_rung["keyframe"]["available"] is False, by_rung["keyframe"]
        assert by_rung["generation"]["available"] is True, by_rung["generation"]
        assert by_rung["generation"]["model"].startswith("ark."), by_rung["generation"]
    finally:
        os.environ.pop("ARK_API_KEY", None)


def check_no_models() -> None:
    pick = remake_policy.select(_run_like(), source_duration=11.0)
    assert pick["mode"] == "analysis_only", pick
    assert pick["rung"] == "analysis", pick
    assert pick["model"] == "", pick
    failed = [row for row in pick["history"] if row["status"] == "skipped"]
    assert failed and any("MINIMAX_API_KEY" in row["reason"] for row in failed), pick["history"]


def check_h3_selected() -> None:
    os.environ["MINIMAX_API_KEY"] = "test-key"
    try:
        pick = remake_policy.select(_run_like(), source_duration=11.0)
        assert pick["mode"] == "h3_reference", pick
        assert pick["rung"] == "full", pick
        assert pick["model"] == "minimax.h3", pick
        assert pick["params"]["duration"] == 11, pick
        assert pick["fallback"] is False, pick
    finally:
        os.environ.pop("MINIMAX_API_KEY", None)


def check_h3_gates() -> None:
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["ARK_API_KEY"] = "test-key"
    try:
        long_pick = remake_policy.select(_run_like(duration=20.0), source_duration=20.0)
        assert long_pick["mode"] == "generation", long_pick
        assert long_pick["model"].startswith("ark."), long_pick
        assert any("4–15" in (row.get("reason") or "") for row in long_pick["history"]), long_pick["history"]

        big_pick = remake_policy.select(_run_like(), source_duration=11.0, source_size_bytes=60 * 1024 * 1024)
        assert big_pick["mode"] == "generation", big_pick
        assert any("50MB" in (row.get("reason") or "") for row in big_pick["history"]), big_pick["history"]
    finally:
        os.environ.pop("MINIMAX_API_KEY", None)
        os.environ.pop("ARK_API_KEY", None)


def check_degrade() -> None:
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["ARK_API_KEY"] = "test-key"
    try:
        selection = remake_policy.select(_run_like(), source_duration=11.0)
        assert selection["mode"] == "h3_reference", selection
        degraded = remake_policy.degrade(_run_like(), selection, reason="RuntimeError: boom")
        assert degraded["mode"] == "generation", degraded
        assert degraded["degraded_from"] == "full", degraded
        assert degraded["history"][0]["status"] == "failed", degraded["history"]
        assert degraded["source_duration_s"] == 11.0, degraded
    finally:
        os.environ.pop("MINIMAX_API_KEY", None)
        os.environ.pop("ARK_API_KEY", None)


def check_candidates_skip_h3() -> None:
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["ARK_API_KEY"] = "test-key"
    try:
        rows = generate._video_candidates(_run_like())
        assert rows, rows
        assert all(str((row.get("remake") or {}).get("tier")) != "full" for row in rows), [
            row.get("id") for row in rows
        ]
        assert any(row.get("id") == "minimax.h3" for row in catalog.for_kind("video")), "H3 must stay in the registry"
    finally:
        os.environ.pop("MINIMAX_API_KEY", None)
        os.environ.pop("ARK_API_KEY", None)


def check_keyframe_rung() -> None:
    os.environ["KLING_API_KEY"] = "test-key"
    try:
        chain = {entry["rung"]: entry for entry in catalog.remake_chain()}
        assert chain["keyframe"]["available"] is True, chain["keyframe"]
        assert chain["keyframe"]["model"] == "kling.v3", chain["keyframe"]

        person = remake_policy.select(_run_like(scope="person"), source_duration=8.0)
        assert person["mode"] == "keyframe", person
        assert person["model"] == "kling.v3", person

        # Kling only offers 5/10s; a longer reference must not be silently cut.
        long_person = remake_policy.select(_run_like(scope="person"), source_duration=11.0)
        assert long_person["mode"] == "generation", long_person
        assert any("上限" in (row.get("reason") or "") for row in long_person["history"]), long_person["history"]

        both = remake_policy.select(_run_like(scope="both"), source_duration=8.0)
        assert both["mode"] == "generation", both
        assert any(row["rung"] == "keyframe" and row["status"] == "skipped" for row in both["history"]), both["history"]
    finally:
        os.environ.pop("KLING_API_KEY", None)


def check_h3_failure_degrades_in_run() -> None:
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["ARK_API_KEY"] = "test-key"
    original_h3 = generate.generate_h3_reference
    original_candidates = generate._video_candidates
    original_adapter = generate._adapter

    class Ok:
        def generate(self, prompt, *, images=None, duration=4, resolution="720p", aspect="9:16", model="", output):
            output.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg.make_synthetic_clip(None, output, duration=2, width=320, height=240)
            return output

    def boom(run_id: str):
        raise RuntimeError("MiniMax 任务 failed: quota")

    try:
        run = _run_like()
        run.id = store.new_id("run")
        run.selection = remake_policy.select(run, source_duration=11.0)
        assert run.selection["mode"] == "h3_reference", run.selection
        # The probe run has no uploaded asset; selection already happened, so drop
        # the placeholder id before generation reads the media path.
        run.inputs["reference_asset_id"] = ""
        store.run_dir(run.id).mkdir(parents=True, exist_ok=True)
        (store.run_dir(run.id) / "artifacts").mkdir(parents=True, exist_ok=True)
        store.atomic_write_json(store.run_dir(run.id) / "artifacts" / "script.json", {"beats": []})
        store.write_run(run)

        generate.generate_h3_reference = boom
        generate._video_candidates = lambda current: [
            {"id": "ark.seedance-2.0-mini", "provider": "ark", "remake": {"tier": "generation"}}
        ]
        generate._adapter = lambda model_id: Ok()

        result = generate.generate(run.id)
        assert result["model"] == "ark.seedance-2.0-mini", result
        assert result["attempts"] and result["attempts"][0]["rung"] == "full", result
        assert any("完整复刻失败" in warning for warning in result["warnings"]), result
        saved = store.read_run(run.id)
        assert saved is not None and saved.status != "failed", saved
        assert saved.selection["mode"] == "generation", saved.selection
        assert saved.selection["history"][0]["status"] == "failed", saved.selection
    finally:
        generate.generate_h3_reference = original_h3
        generate._video_candidates = original_candidates
        generate._adapter = original_adapter
        os.environ.pop("MINIMAX_API_KEY", None)
        os.environ.pop("ARK_API_KEY", None)


def main() -> None:
    check_chain()
    check_no_models()
    check_h3_selected()
    check_h3_gates()
    check_degrade()
    check_candidates_skip_h3()
    check_keyframe_rung()
    check_h3_failure_degrades_in_run()
    print("adclip remake policy: ok")


if __name__ == "__main__":
    main()
