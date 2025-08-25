import importlib
import sys
from pathlib import Path

# Add app directory to path so ``vision`` package can be imported without
# interfering with existing ``app.py`` module.
APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

counting = importlib.import_module("vision.counting")


def test_side_of_line():
    line = (0, 0, 0, 2)
    assert counting.side_of_line((1, 0, 3, 2), line) == -1
    assert counting.side_of_line((-3, 0, -1, 2), line) == 1
    assert counting.side_of_line((-1, 0, 1, 2), line) == 0


def test_cross_events():
    assert counting.cross_events(-1, 1) == ["in"]
    assert counting.cross_events(1, -1) == ["out"]
    assert counting.cross_events(0, 1) == []


def test_count_update_single_cross():
    state = {}
    line_cfg = {"id": "L1", "line": (0, 0, 0, 2)}
    tracks = {1: {"bbox": (1, -1, 2, 1), "group": "person", "ts_ms": 0}}
    state, events = counting.count_update(state, tracks, line_cfg)
    assert events == []

    tracks = {1: {"bbox": (-2, -1, -1, 1), "group": "person", "ts_ms": 1}}
    state, events = counting.count_update(state, tracks, line_cfg)
    assert [e.kind for e in events] == ["in"]
    # second crossing should not emit again
    tracks = {1: {"bbox": (1, -1, 2, 1), "group": "person", "ts_ms": 2}}
    state, events = counting.count_update(state, tracks, line_cfg)
    assert events == []
