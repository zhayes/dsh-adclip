"""Pick the remake path for a run from the capability registry.

The user never chooses a model for a viral remake. The planner ranks the
currently available catalogue rows by hard capability tier first and internal
cost/quality weight second, then records the decision on the run so the UI,
tool and pipeline all report the same choice.
"""
from __future__ import annotations

import os
from typing import Any

from . import catalog, store


def _source_duration(inputs: dict[str, Any]) -> float | None:
    asset_id = str((inputs or {}).get("reference_asset_id") or "")
    if not asset_id:
        return None
    record = store.get_asset(asset_id)
    if not record:
        return None
    try:
        value = float(record.get("duration_s") or 0)
    except (TypeError, ValueError):
        return None
    return value or None


def _allowed_duration(model: dict[str, Any], target: float, *, upper: int) -> int:
    allowed = sorted(int(value) for value in (model.get("durations") or []) if int(value) <= upper)
    if not allowed:
        return max(4, min(upper, int(round(target))))
    for value in allowed:
        if value >= target:
            return value
    return allowed[-1]


def _ordered(rows: list[dict[str, Any]], *, only_tier: str | None = None) -> list[dict[str, Any]]:
    def rank(row: dict[str, Any]) -> tuple[int, float, int, str]:
        remake = row.get("remake") or {}
        tier = str(remake.get("tier") or "generation")
        return (
            float(remake.get("cost_weight") or 1.0),
            -int(remake.get("priority") or 0),
            -int(catalog_tier_order(tier)),
            str(row.get("id") or ""),
        )

    candidates = []
    for row in rows:
        remake = row.get("remake") or {}
        tier = str(remake.get("tier") or "")
        if tier not in {"full", "reference", "generation"}:
            continue
        if only_tier is not None and tier != only_tier:
            continue
        candidates.append(row)
    return sorted(candidates, key=rank)


def catalog_tier_order(tier: str) -> int:
    return {"full": 3, "reference": 2, "generation": 1}.get(str(tier), 0)


def _base_selection(run: Any, *, source_duration: float | None = None, source_aspect: str = "") -> dict[str, Any]:
    advanced = dict((getattr(run, "advanced", None) or {}))
    inputs = dict((getattr(run, "inputs", None) or {}))
    rows = [
        row for row in catalog.for_kind("video")
        if row.get("available") and row.get("enabled", True)
    ]
    if os.environ.get("ADCLIP_TEST_MODE", "").strip() == "1":
        rows = [row for row in rows if row.get("provider") == "synthetic"] or rows
    duration = source_duration or _source_duration(inputs)
    target = duration or float(advanced.get("duration") or 12)

    for tier, mode in (("full", "h3_reference"), ("reference", "reference_fallback"), ("generation", "generation_fallback")):
        candidates = _ordered(rows, only_tier=tier)
        if tier == "full" and duration is not None and not (4 <= duration <= 15):
            candidates = []
        if not candidates:
            continue
        model = candidates[0]
        model_id = str(model.get("id"))
        params = {**(model.get("default_params") or {})}
        if tier == "full":
            resolution = str(params.get("resolution") or "768P")
            configured_duration = params.get("duration")
            if isinstance(configured_duration, int):
                gen_duration = configured_duration
            else:
                gen_duration = int(round(target))
            gen_duration = max(4, min(15, int(gen_duration)))
            mode = "h3_reference" if model_id == "minimax.h3" else "reference_fallback"
            params = {**params, "resolution": resolution, "duration": gen_duration}
        elif tier == "reference":
            configured = params.get("duration")
            wanted = float(configured) if isinstance(configured, int) else target
            params = {**params, "duration": _allowed_duration(model, wanted, upper=30)}
        else:
            configured = params.get("duration")
            wanted = float(configured) if isinstance(configured, int) else target
            params = {**params, "duration": _allowed_duration(model, wanted, upper=15)}
        if tier == "reference":
            mode = "generation_fallback"
        reason = {
            "full": f"{model_id} 是完整复刻模型，优先选它",
            "reference": f"H3 不可用，退到生成模型 {model_id}（参考视频不发给该模型）",
            "generation": f"没有完整/参考复刻模型，退到生成模型 {model_id}",
        }[tier]
        return {
            "mode": mode,
            "tier": tier,
            "model": model_id,
            "model_label": str(model.get("label") or model_id),
            "reason": reason,
            "fallback": tier != "full",
            "params": params,
            "source_duration_s": duration,
            "source_aspect": source_aspect,
        }

    return {
        "mode": "analysis_only",
        "tier": "analysis",
        "model": "",
        "model_label": "",
        "reason": "当前没有可用的视频生成模型；只返回参考片拆解",
        "fallback": True,
        "params": {},
        "source_duration_s": duration,
        "source_aspect": source_aspect,
    }


def select(run: Any, *, source_duration: float | None = None, source_aspect: str = "") -> dict[str, Any]:
    """Choose the remake path for a run-like object (scenario/inputs/advanced)."""
    scenario = str(getattr(run, "scenario", "") or "")
    if scenario != "viral-remake":
        return {}
    return _base_selection(run, source_duration=source_duration, source_aspect=source_aspect)


def selection_for(scenario: str, inputs: dict[str, Any], advanced: dict[str, Any]) -> dict[str, Any]:
    """Choose before the Run object exists (used by POST /runs)."""
    if str(scenario) != "viral-remake":
        return {}
    class _RunLike:
        pass

    value = _RunLike()
    value.scenario = scenario
    value.inputs = inputs
    value.advanced = advanced
    return _base_selection(value)
