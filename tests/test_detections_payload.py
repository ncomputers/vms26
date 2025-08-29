import asyncio
import sys
import types

# minimal stubs for modules.tracker and cv2 dependencies
tracker_mod = types.ModuleType("modules.tracker")


class PersonTracker:  # pragma: no cover - stub
    pass


tracker_mod.PersonTracker = PersonTracker
modules_pkg = types.ModuleType("modules")
modules_pkg.tracker = tracker_mod
sys.modules.setdefault("modules", modules_pkg)
sys.modules.setdefault("modules.tracker", tracker_mod)
sys.modules.setdefault("cv2", types.ModuleType("cv2"))

from routers.detections import _build_payload


class FakeTracker:
    def __init__(self, tracks):
        self.tracks = tracks
        self.cfg = {}


def test_build_payload_tracks_box():
    tracker = FakeTracker({1: {"bbox": (0, 0, 10, 10)}})
    payload = asyncio.run(_build_payload(1, tracker, {}, set()))
    assert payload["tracks"] == [{"id": 1, "box": [0, 0, 10, 10], "label": "", "conf": 0.0}]


def test_build_payload_includes_face_box():
    tracker = FakeTracker({1: {"bbox": (0, 0, 10, 10), "face": (2, 2, 4, 4)}})
    payload = asyncio.run(_build_payload(1, tracker, {}, set()))
    assert payload["tracks"][0]["face"] == [2, 2, 4, 4]


def test_build_payload_no_fake_ppe():
    tracker = FakeTracker({})
    payload = asyncio.run(_build_payload(1, tracker, {}, {"helmet"}))
    assert payload["ppe"] == []
