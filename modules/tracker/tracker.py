"""Tracking utilities for the tracker package."""

from __future__ import annotations

from typing import Any, List, Tuple

try:  # optional heavy dependency
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None


Detection = Tuple[Tuple[float, float, float, float], float, str]


class Tracker:
    """Thin wrapper around ``DeepSort`` to allow easy substitution in tests."""

    def __init__(self, use_gpu_embedder: bool, max_age: int = 10) -> None:
        if DeepSort is None:  # pragma: no cover - DeepSort optional
            raise RuntimeError("DeepSort not available")
        self._tracker = DeepSort(max_age=max_age, embedder_gpu=use_gpu_embedder)

    def update_tracks(self, detections: List[Detection], frame=None):
        """Proxy to :meth:`DeepSort.update_tracks`."""
        return self._tracker.update_tracks(detections, frame=frame)


__all__ = ["Tracker"]
