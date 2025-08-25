from __future__ import annotations

"""Core data models used by the overlay module."""

import numpy as np
from pydantic import BaseModel, ConfigDict


class FrameMeta(BaseModel):
    camera_id: str
    ts_ms: int
    src_w: int
    src_h: int
    seq: int


class Detection(BaseModel):
    cls: str
    box: tuple[float, float, float, float]
    score: float


class Track(BaseModel):
    track_id: int
    cls: str
    box: tuple[float, float, float, float]


class Counts(BaseModel):
    entered: int
    exited: int
    inside: int


class OverlayInput(BaseModel):
    frame_np: np.ndarray
    meta: FrameMeta
    detections: list[Detection]
    tracks: list[Track]
    counts: Counts
    ppe: list[Detection] | None = None
    line_cfg: dict | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
