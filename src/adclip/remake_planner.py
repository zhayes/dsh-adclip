"""Compatibility facade over `remake_policy`.

The remake ladder used to be ranked here. It now lives in `remake_policy` and
`catalog.remake_chain()` so the planner, the engine, the DSH tools and the
Settings page all report the same decision. This module keeps the old call
sites (`runner`, `api`, tests) working.
"""
from __future__ import annotations

from typing import Any

from . import catalog, remake_policy


def catalog_tier_order(tier: str) -> int:
    return {"full": 3, "reference": 2, "generation": 1}.get(str(tier), 0)


def select(
    run: Any,
    *,
    source_duration: float | None = None,
    source_aspect: str = "",
    source_size_bytes: int | None = None,
) -> dict[str, Any]:
    """Choose the remake path for a run-like object (scenario/inputs/advanced)."""
    if str(getattr(run, "scenario", "") or "") != "viral-remake":
        return {}
    return remake_policy.select(
        run,
        source_duration=source_duration,
        source_aspect=source_aspect,
        source_size_bytes=source_size_bytes,
    )


def selection_for(scenario: str, inputs: dict[str, Any], advanced: dict[str, Any]) -> dict[str, Any]:
    """Choose before the Run object exists (used by POST /runs)."""
    return remake_policy.selection_for(scenario, inputs, advanced)


def chain() -> list[dict[str, Any]]:
    return catalog.remake_chain()
