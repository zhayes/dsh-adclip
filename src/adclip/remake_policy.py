"""Remake rung policy: eligibility, selection and degradation.

The user never picks a model for a viral remake. Selection walks the ladder in
`catalog.remake_chain()` and stops at the first rung whose model can really do
what the rung promises. Every skip is recorded with a reason, so the UI and the
DSH tools can explain *why* a run is not a full replication instead of silently
downgrading.

Rungs, strongest first:

1. `full`      — the reference video itself is sent (H3).
2. `reference` — a direct-video model is available and its adapter is wired.
3. `keyframe`  — first-frame anchoring (declared, adapter not wired yet).
4. `generation`— the model only sees our analysis prompt.
5. `analysis_only` — no video model; the run returns the breakdown only.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from . import catalog, store

H3_MIN_S = 4.0
H3_MAX_S = 15.0
H3_MAX_BYTES = 50 * 1024 * 1024


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number or None


def _facts(
    run: Any,
    source_duration: float | None,
    source_aspect: str,
    source_size_bytes: int | None,
) -> tuple[str, float | None, int | None, str]:
    inputs = dict(getattr(run, "inputs", None) or {})
    asset_id = str(inputs.get("reference_asset_id") or "")
    record = store.get_asset(asset_id) if asset_id else None
    duration = _as_float(source_duration) if source_duration is not None else None
    if duration is None and record:
        duration = _as_float(record.get("duration_s"))
    size = source_size_bytes
    if size is None and record:
        raw = record.get("size_bytes")
        size = int(raw) if isinstance(raw, (int, float)) else None
    aspect = str(source_aspect or (record or {}).get("aspect") or "")
    return asset_id, duration, size, aspect


def h3_gate(asset_id: str, duration: float | None, size: int | None) -> tuple[bool, str]:
    """Whether H3 may take this reference at all."""
    if not asset_id:
        return False, "缺少参考视频"
    if duration is not None and not (H3_MIN_S <= duration <= H3_MAX_S):
        return False, f"参考片 {duration:.1f}s 超出 H3 的 4–15 秒"
    if size is not None and size > H3_MAX_BYTES:
        return False, "参考片超过 MiniMax 50MB 上限"
    return True, ""


def _allowed_duration(entry: dict[str, Any], target: float, *, upper: int) -> int:
    allowed = sorted(int(value) for value in (entry.get("durations") or []) if int(value) <= upper)
    if not allowed:
        return max(4, min(upper, round(target)))
    for value in allowed:
        if value >= target:
            return value
    return allowed[-1]


def _params_for(entry: dict[str, Any], target: float) -> dict[str, Any]:
    params = dict(entry.get("params") or {})
    rung = str(entry.get("rung") or "")
    if rung == "full":
        resolution = str(params.get("resolution") or "768P")
        configured = params.get("duration")
        duration = configured if isinstance(configured, int) else round(target)
        return {**params, "resolution": resolution, "duration": max(4, min(15, duration))}
    upper = 30 if rung == "reference" else 15
    configured = params.get("duration")
    wanted = float(configured) if isinstance(configured, int) else target
    return {**params, "duration": _allowed_duration(entry, wanted, upper=upper)}


def _analysis_only(
    *,
    reason: str,
    duration: float | None,
    aspect: str,
    chain: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "mode": "analysis_only",
        "tier": "analysis",
        "rung": "analysis",
        "model": "",
        "model_label": "",
        "provider": "",
        "reason": reason,
        "fallback": True,
        "params": {},
        "source_duration_s": duration,
        "source_aspect": aspect,
        "chain": chain,
        "history": history,
    }


def select(
    run: Any,
    *,
    source_duration: float | None = None,
    source_aspect: str = "",
    source_size_bytes: int | None = None,
    exclude_rungs: tuple[str, ...] | list[str] = (),
    exclude_models: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Pick the strongest usable rung for a run-like object."""
    advanced = dict(getattr(run, "advanced", None) or {})
    asset_id, duration, size, aspect = _facts(run, source_duration, source_aspect, source_size_bytes)
    target = duration or _as_float(advanced.get("duration")) or 12.0
    skipped = {str(value) for value in exclude_rungs}
    skipped_models = {str(value) for value in exclude_models}
    chain = catalog.remake_chain()
    history: list[dict[str, Any]] = []
    notes: list[str] = []

    for entry in chain:
        rung = str(entry.get("rung") or "")
        if rung in skipped:
            continue
        model_id = str(entry.get("model") or "")
        if model_id and model_id in skipped_models:
            continue
        if not entry.get("available"):
            reason = str(entry.get("reason") or "不可用")
            history.append({"rung": rung, "model": model_id, "status": "skipped", "reason": reason})
            notes.append(f"{rung}: {reason}")
            continue
        if rung == "full":
            ok, why = h3_gate(asset_id, duration, size)
            if not ok:
                history.append({"rung": rung, "model": model_id, "status": "skipped", "reason": why})
                notes.append(f"H3: {why}")
                continue
        if rung == "keyframe":
            scope = str(advanced.get("replace_scope") or "both")
            if scope in {"both", "product"}:
                why = "换商品需要商品参考图，首帧锚定档只能传一张首帧"
                history.append({"rung": rung, "model": model_id, "status": "skipped", "reason": why})
                notes.append(f"首帧锚定: {why}")
                continue
            limit = max([int(value) for value in (entry.get("durations") or [])] or [0])
            if duration and limit and duration > limit + 0.5:
                why = f"参考片 {duration:.1f}s 超过 {model_id} 的 {limit}s 上限"
                history.append({"rung": rung, "model": model_id, "status": "skipped", "reason": why})
                notes.append(f"首帧锚定: {why}")
                continue
        mode = str(entry.get("mode") or rung)
        reason = {
            "full": f"{model_id} 是完整复刻模型，优先选它",
            "reference": f"退到参考复刻模型 {model_id}（参考视频直传）",
            "keyframe": f"退到首帧锚定模型 {model_id}",
            "generation": f"没有可用的参考直传模型，按拆解生成 {model_id}",
        }.get(rung, f"选中 {model_id}")
        if notes:
            reason += "；已跳过：" + "、".join(notes)
        return {
            "mode": mode,
            "tier": rung,
            "rung": rung,
            "model": model_id,
            "model_label": str(entry.get("model_label") or model_id),
            "provider": str(entry.get("provider") or ""),
            "reason": reason,
            "fallback": rung != "full",
            "params": _params_for(entry, target),
            "source_duration_s": duration,
            "source_aspect": aspect,
            "chain": chain,
            "history": history,
            "excluded_rungs": sorted(skipped),
            "excluded_models": sorted(skipped_models),
        }

    return _analysis_only(
        reason="当前没有可用的视频生成模型；只返回参考片拆解" + (f"（已跳过：{'、'.join(notes)}）" if notes else ""),
        duration=duration,
        aspect=aspect,
        chain=chain,
        history=history,
    )


def selection_for(scenario: str, inputs: dict[str, Any], advanced: dict[str, Any]) -> dict[str, Any]:
    """Choose before the Run object exists (used by POST /runs)."""
    if str(scenario) != "viral-remake":
        return {}
    return select(SimpleNamespace(scenario=scenario, inputs=inputs, advanced=advanced))


def degrade(
    run: Any,
    selection: dict[str, Any],
    *,
    reason: str,
    source_duration: float | None = None,
    source_aspect: str = "",
    source_size_bytes: int | None = None,
) -> dict[str, Any]:
    """Step one rung down after a failure, keeping the attempt history."""
    rung = str(selection.get("rung") or selection.get("tier") or "")
    excluded = list(selection.get("excluded_rungs") or [])
    if rung and rung not in {"analysis", "analysis_only"}:
        excluded.append(rung)
    models = list(selection.get("excluded_models") or [])
    model_id = str(selection.get("model") or "")
    if model_id:
        models.append(model_id)
    degraded = select(
        run,
        source_duration=source_duration if source_duration is not None else selection.get("source_duration_s"),
        source_aspect=source_aspect or str(selection.get("source_aspect") or ""),
        source_size_bytes=source_size_bytes,
        exclude_rungs=excluded,
        exclude_models=models,
    )
    history = list(selection.get("history") or [])
    history.append({
        "rung": rung,
        "mode": str(selection.get("mode") or ""),
        "model": model_id,
        "status": "failed",
        "reason": str(reason)[:300],
    })
    degraded["history"] = history + list(degraded.get("history") or [])
    degraded["degraded_from"] = rung
    return degraded
