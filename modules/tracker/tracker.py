"""Tracking utilities for the tracker package."""

from __future__ import annotations

import time
from typing import Iterable, List, MutableMapping, Tuple

from app.core.prof import profiled

try:  # optional heavy dependency
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None


Detection = Tuple[Tuple[float, float, float, float], float, str]


class Tracker:
    """Wrapper around ``DeepSort`` with simple ID bookkeeping.

    The wrapper maintains a ``last_seen`` map of track IDs to the timestamp in
    milliseconds when they were last returned by ``DeepSort``.  Stale IDs are
    pruned on every update to keep memory bounded for long running processes.
    """

    ttl_ms = 120_000

    def __init__(self, use_gpu_embedder: bool, max_age: int = 10) -> None:
        if DeepSort is None:  # pragma: no cover - DeepSort optional
            raise RuntimeError("DeepSort not available")
        self._tracker = DeepSort(max_age=max_age, embedder_gpu=use_gpu_embedder)
        self.last_seen: dict[int, int] = {}

    @profiled("trk")
    def update_tracks(
        self,
        detections: List[Detection],
        frame=None,
        aux: Iterable[MutableMapping] | None = None,
    ):
        """Update tracks and prune stale bookkeeping.

        Parameters
        ----------
        detections:
            Iterable of ``(x1, y1, x2, y2, conf, class)`` tuples.  The bounding
            box may already be in ``xyxy`` format; it will be converted to the
            ``xywh`` format expected by ``DeepSort``.
        frame:
            Optional frame passed through to ``DeepSort``.
        aux:
            Optional iterable of dictionaries keyed by track IDs (or tuples
            whose first element is the track ID).  Entries for tracks not seen
            within ``ttl_ms`` are removed.
        """

        # Convert detections from xyxy to xywh for DeepSort
        ds_dets: List[Detection] = []
        for bbox, conf, label in detections:
            x1, y1, x2, y2 = bbox
            if x2 > x1 and y2 > y1:
                bbox_xywh = (x1, y1, x2 - x1, y2 - y1)
            else:  # already in xywh
                bbox_xywh = (x1, y1, x2, y2)
            ds_dets.append((bbox_xywh, conf, label))

        tracks = self._tracker.update_tracks(ds_dets, frame=frame)

        now_ms = int(time.time() * 1000)
        for trk in tracks:
            if trk.is_confirmed():
                self.last_seen[trk.track_id] = now_ms

        cutoff = now_ms - self.ttl_ms
        stale = [tid for tid, ts in self.last_seen.items() if ts < cutoff]
        if stale:
            for tid in stale:
                self.last_seen.pop(tid, None)
                if aux:
                    for d in aux:
                        keys = [
                            k
                            for k in list(d.keys())
                            if k == tid or (isinstance(k, tuple) and k and k[0] == tid)
                        ]
                        for k in keys:
                            d.pop(k, None)

        return tracks


__all__ = ["Tracker"]
