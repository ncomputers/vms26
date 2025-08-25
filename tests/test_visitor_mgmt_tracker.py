import fakeredis

import core.tracker_manager as tm


def test_visitor_mgmt_starts_tracker(monkeypatch):
    created = {}

    class DummyWorker:
        def run(self):
            pass

    class DummyTracker:
        def __init__(self, cam_id, url, obj_classes, cfg, tasks, cam_type, **kwargs):
            created["tasks"] = tasks
            self.capture_worker = DummyWorker()
            self.infer_worker = DummyWorker()
            self.post_worker = DummyWorker()

    monkeypatch.setattr(tm, "PersonTracker", DummyTracker)

    class DummyThread:
        def __init__(self, target, daemon=True):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(tm.threading, "Thread", DummyThread)

    r = fakeredis.FakeRedis()
    cam = {"id": 1, "url": "rtsp://", "tasks": ["visitor_mgmt"]}
    cfg = {}
    trackers = {}

    tr = tm.start_tracker(cam, cfg, trackers, r)

    assert tr is not None
    assert trackers[1] is tr
    assert created["tasks"] == ["visitor_mgmt"]
