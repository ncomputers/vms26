"""Line-crossing counting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class CountEvent:
    """Structured line-crossing event."""

    kind: str  # 'in' or 'out'
    group: str  # 'person' or 'vehicle'
    track_id: int
    ts_ms: int
    line_id: str


def side_of_line(
    box_xyxy: Tuple[float, float, float, float], line: Tuple[float, float, float, float]
) -> int:
    """Return which side of ``line`` the centre of ``box_xyxy`` lies on.

    Parameters
    ----------
    box_xyxy:
        Bounding box in ``(x1, y1, x2, y2)`` format.
    line:
        Line represented as ``(x1, y1, x2, y2)``.

    Returns
    -------
    int
        ``-1`` if the centre lies on one side, ``1`` on the other, and ``0`` if
        the point is exactly on the line.
    """

    cx = (box_xyxy[0] + box_xyxy[2]) / 2.0
    cy = (box_xyxy[1] + box_xyxy[3]) / 2.0
    x1, y1, x2, y2 = line
    val = (x2 - x1) * (cy - y1) - (y2 - y1) * (cx - x1)
    if val > 0:
        return 1
    if val < 0:
        return -1
    return 0


def cross_events(prev_side: int | None, new_side: int) -> List[str]:
    """Return crossing events from ``prev_side`` to ``new_side``.

    A transition from ``-1`` to ``1`` yields ``['in']`` while the reverse yields
    ``['out']``.  All other transitions return an empty list.
    """

    if prev_side is None or prev_side == 0 or new_side == 0:
        return []
    if prev_side == -1 and new_side == 1:
        return ["in"]
    if prev_side == 1 and new_side == -1:
        return ["out"]
    return []


def count_update(
    state: Dict[str, Dict[int, Dict[str, int | bool]]],
    tracks: Dict[int, Dict],
    line_cfg: Dict,
) -> Tuple[Dict[str, Dict[int, Dict[str, int | bool]]], List[CountEvent]]:
    """Update ``state`` with ``tracks`` and emit :class:`CountEvent` objects.

    ``state`` keeps per-``line_id`` and per-``track_id`` information with
    ``last_side`` and ``counted`` flags.  Each track produces at most one event
    per line configuration.
    """

    line_id = line_cfg.get("id", "line")
    line = line_cfg["line"]
    line_state = {tid: info.copy() for tid, info in state.get(line_id, {}).items()}
    events: List[CountEvent] = []

    for tid, tr in tracks.items():
        side = side_of_line(tr["bbox"], line)
        info = line_state.get(tid, {"last_side": side, "counted": False})
        prev_side = info.get("last_side")  # type: ignore[assignment]
        counted = bool(info.get("counted"))
        for ev in cross_events(prev_side, side):
            if not counted:
                events.append(
                    CountEvent(
                        kind=ev,
                        group=tr.get("group", "person"),
                        track_id=tid,
                        ts_ms=int(tr.get("ts_ms", 0)),
                        line_id=line_id,
                    )
                )
                counted = True
        line_state[tid] = {"last_side": side, "counted": counted}

    new_state = state.copy()
    new_state[line_id] = line_state
    return new_state, events


__all__ = [
    "CountEvent",
    "side_of_line",
    "cross_events",
    "count_update",
]
