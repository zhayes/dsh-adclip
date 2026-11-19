"""Pydantic contracts for AdClip.

The service deliberately keeps one user-visible object: a Run. A Run owns its
storyboard, segments, versions and artifacts. There is no project/version/shot
or quote object in this service.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Asset(BaseModel):
    id: str
    name: str
    kind: Literal["video", "image", "audio", "file"]
    path: str
    sha256: str
    bytes: int
    mime: str = "application/octet-stream"
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    source: str = "upload"
    created_at: str
    original_name: str = ""


class Persona(BaseModel):
    id: str
    name: str
    type: Literal["ai", "real", "group"] = "ai"
    gender: Literal["male", "female", "any"] = "any"
    age: Literal["teenager", "youth", "middle_aged", "senior"] = "youth"
    ethnicity: Literal[
        "caucasian", "asian", "latino", "african", "middle_eastern", "any"
    ] = "asian"
    body_type: Literal["slim", "standard", "athletic", "chubby"] = "standard"
    exact_age: Optional[int] = None
    height_cm: Optional[int] = None
    hair: str = ""
    outfit: str = ""
    temperament: str = ""
    voice_tone: str = ""
    reference_audio_asset_id: Optional[str] = None
    reference_images: list[str] = Field(default_factory=list)
    role: Literal["A", "B", "both", "group"] = "both"
    locks: dict[str, bool] = Field(default_factory=dict)
    consent: dict[str, Any] = Field(default_factory=lambda: {"confirmed": False, "note": ""})
    created_at: str
    used_in_runs: list[str] = Field(default_factory=list)


class RunStep(BaseModel):
    name: str
    label: str
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    progress: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class StoryboardSegment(BaseModel):
    id: str
    index: int
    start_s: float
    end_s: float
    function: str = "beat"
    source: Literal["one_shot_slice", "generated"] = "one_shot_slice"
    thumbnail: Optional[str] = None
    dialogue: str = ""
    action: str = ""
    product: str = ""
    status: Literal["ok", "warn", "fail"] = "ok"
    asset_id: Optional[str] = None
    take: int = 1
    note: str = ""


class Run(BaseModel):
    id: str
    scenario: str
    title: str = "未命名"
    status: Literal["queued", "running", "awaiting_confirm", "succeeded", "failed", "canceled", "interrupted"] = "queued"
    step: str = "queued"
    progress: float = 0.0
    generation_mode: Literal["fast", "fine"] = "fast"
    inputs: dict[str, Any] = Field(default_factory=dict)
    advanced: dict[str, Any] = Field(default_factory=dict)
    persona_map: dict[str, str] = Field(default_factory=dict)
    persona_snapshot: dict[str, Any] = Field(default_factory=dict)
    steps: list[RunStep] = Field(default_factory=list)
    storyboard: list[StoryboardSegment] = Field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    selection: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    last_edit_error: Optional[str] = None
    demo: bool = False
    cancel_requested: bool = False
    created_at: str = ""
    finished_at: Optional[str] = None
    parent_run_id: Optional[str] = None
    version: int = 1
    changes: list[dict[str, Any]] = Field(default_factory=list)
    segment_edits: list[dict[str, Any]] = Field(default_factory=list)


class StitchClip(BaseModel):
    asset_id: str
    in_s: float = 0.0
    out_s: Optional[float] = None


class StitchRequest(BaseModel):
    clips: list[StitchClip]
    output: dict[str, Any] = Field(default_factory=dict)
    transition: str = "cut"
    audio: str = "keep"
    fit: str = "blur_pad"


class AssistantRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    selected_segment_id: Optional[str] = None
    assets: list[dict[str, Any]] = Field(default_factory=list)
    personas: list[dict[str, Any]] = Field(default_factory=list)
