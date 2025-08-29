import asyncio
import sys
import types

tracker_mod = types.ModuleType("modules.tracker")


class PersonTracker:  # minimal stub for type checking
    pass


tracker_mod.PersonTracker = PersonTracker
modules_pkg = types.ModuleType("modules")
modules_pkg.tracker = tracker_mod
sys.modules.setdefault("modules", modules_pkg)
sys.modules.setdefault("modules.tracker", tracker_mod)
sys.modules.setdefault("cv2", types.ModuleType("cv2"))

from routers.detections import _build_payload


class FakeTracker:
    def __init__(self, in_count=0, out_count=0, in_counts=None, out_counts=None):
        self.in_count = in_count
        self.out_count = out_count
        self.in_counts = in_counts
        self.out_counts = out_counts
        self.cfg = {}


def test_counts_from_simple_tracker():
    tracker = FakeTracker(in_count=3, out_count=2)
    payload = asyncio.run(_build_payload(1, tracker, {}, set()))
    assert payload["counts"] == {"entered": 3, "exited": 2, "inside": 1}


def test_counts_classwise_preferred():
    tracker = FakeTracker(in_counts={"person": 5}, out_counts={"person": 1})
    payload = asyncio.run(_build_payload(1, tracker, {}, set()))
    assert payload["counts"] == {"entered": 5, "exited": 1, "inside": 4}


def test_counts_without_tracker():
    payload = asyncio.run(_build_payload(1, None, {}, set()))
    assert payload["counts"] == {"entered": 0, "exited": 0, "inside": 0}
