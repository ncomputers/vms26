from __future__ import annotations

"""Overlay rendering helpers."""

import io
from typing import Dict, List

import numpy as np
from PIL import Image

from utils.overlay import draw_boxes_np


def render_from_legacy(
    frame: bytes,
    dets: List[Dict],
    *,
    thickness: int = 2,
    labels: bool = True,
) -> bytes:
    """Render overlays on ``frame`` using legacy numpy path."""
    img = Image.open(io.BytesIO(frame)).convert("RGB")
    arr = np.asarray(img, dtype=np.uint8)
    if not labels:
        dets = [{**d, "label": ""} for d in dets]
    arr = draw_boxes_np(arr, dets, thickness=thickness)
    bio = io.BytesIO()
    Image.fromarray(arr).save(bio, "JPEG", quality=80)
    return bio.getvalue()

__all__ = ["render_from_legacy"]
