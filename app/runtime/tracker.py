"""Wrapper around :mod:`modules.tracker.tracker` exposing an ``update`` method."""

from __future__ import annotations

from modules.tracker.tracker import Tracker as _BaseTracker


class Tracker(_BaseTracker):
    """Expose ``update`` method compatible with expected pipeline API."""

    def update(self, detections, frame=None):
        return super().update_tracks(detections, frame=frame)
