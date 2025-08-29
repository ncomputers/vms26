"""Video processing pipeline helpers."""

from __future__ import annotations

import os
from typing import Any, List, Tuple

from . import counting
from .tracker import Tracker

_EVENT_LOG: List[Any] = []


def get_event_log() -> List[Any]:
    """Return accumulated counting events."""
    return _EVENT_LOG


def _legacy_process_loop(person_detections, state, line_cfg):
    """Placeholder for the legacy counting path."""
    # Legacy logic would be invoked here.  For now we simply return the state
    # unchanged and emit no events.
    return state, []


def ProcessLoop(person_detections, state, line_cfg) -> Tuple[Any, List[Any]]:
    """Process detections and update counting state.

    When environment variable ``VMS21_COUNTING_PURE`` is set to ``"1"`` the
    new counting pipeline is used.  Otherwise the legacy implementation is
    executed.
    """

    if os.getenv("VMS21_COUNTING_PURE") == "1":
        tracker = Tracker(use_gpu_embedder=False)
        tracks = tracker.update(person_detections)
        state, events = counting.count_update(state, tracks, line_cfg)
        _EVENT_LOG.extend(events)
        return state, events

    return _legacy_process_loop(person_detections, state, line_cfg)
