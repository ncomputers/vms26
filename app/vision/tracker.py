from __future__ import annotations

"""DeepSort tracker wrapper for vision module."""

from dataclasses import dataclass
from typing import Any, List, Sequence

import numpy as np

try:  # optional heavy dependency
    from deep_sort_realtime.deep_sort.track import Track  # type: ignore
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None  # type: ignore[assignment]
    Track = Any  # type: ignore


@dataclass
class Detection:
    """Detection with bbox in ``(x1, y1, x2, y2)`` format."""

    bbox: Sequence[float]
    confidence: float
    class_id: str | int | None = None


class Tracker:
    """Wraps :class:`deep_sort_realtime.DeepSort` with fixed parameters.

    Parameters are read from environment variables with sensible defaults.
    One instance should be created per camera to ensure a consistent track ID
    lifecycle.
    """

    def __init__(self) -> None:
        if DeepSort is None:  # pragma: no cover - DeepSort optional
            raise RuntimeError("DeepSort not available")

        from app.core.utils import getenv_num

        max_age = getenv_num("TRACKER_MAX_AGE", 30, int)
        n_init = getenv_num("TRACKER_N_INIT", 3, int)
        max_iou_distance = getenv_num("TRACKER_MAX_IOU_DISTANCE", 0.7, float)

        self._tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_iou_distance=max_iou_distance,
            embedder=None,
        )

    def update(self, detections: List[Detection]) -> List[Track]:
        """Update tracked objects from the provided detections.

        Bounding boxes are converted from ``(x1, y1, x2, y2)`` to
        ``(x, y, w, h)`` before invoking DeepSort.
        """

        ds_dets = []
        embeds = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            ltwh = [x1, y1, x2 - x1, y2 - y1]
            ds_dets.append((ltwh, det.confidence, det.class_id))
            embeds.append(np.zeros(1, dtype=np.float32))

        return self._tracker.update_tracks(ds_dets, embeds=embeds)
