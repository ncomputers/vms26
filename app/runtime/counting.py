from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Tuple

from app.vision.counting import CountEvent
from app.vision.counting import count_update as _count_update


def _tracks_to_dict(tracks: Iterable[Any]) -> Dict[int, Dict[str, Any]]:
    norm: Dict[int, Dict[str, Any]] = {}
    now_ms = int(time.time() * 1000)
    for tr in tracks or []:
        tid = None
        if hasattr(tr, "track_id"):
            tid = tr.track_id
        elif isinstance(tr, dict):
            tid = tr.get("track_id")
        if tid is None:
            continue

        bbox = None
        if hasattr(tr, "to_tlbr"):
            try:
                x1, y1, x2, y2 = tr.to_tlbr()
                bbox = (float(x1), float(y1), float(x2), float(y2))
            except Exception:
                pass
        if bbox is None and isinstance(tr, dict) and "bbox" in tr:
            bbox = tuple(tr["bbox"])
        if bbox is None:
            continue

        norm[int(tid)] = {
            "bbox": bbox,
            "group": "person",
            "ts_ms": now_ms,
        }
    return norm


def count_update(
    state: Dict[str, Dict[int, Dict[str, int | bool]]] | None,
    tracks: Iterable[Any],
    line_cfg: Dict[str, Any] | None,
) -> Tuple[Dict[str, Dict[int, Dict[str, int | bool]]], List[CountEvent]]:
    state = state or {}
    line_cfg = line_cfg or {"id": "line", "line": (0.5, 0.0, 0.5, 1.0)}
    tracks_map = _tracks_to_dict(tracks)
    return _count_update(state, tracks_map, line_cfg)
