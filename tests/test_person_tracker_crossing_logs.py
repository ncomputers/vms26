import json
import queue
import sys
import time
from datetime import datetime
from pathlib import Path

import fakeredis
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from types import SimpleNamespace

import modules.tracker.manager as manager_mod
from modules.tracker import InferWorker, PersonTracker, PostProcessWorker
from routers import reports


def test_crossing_logged_and_reported(monkeypatch, tmp_path):
    r = fakeredis.FakeRedis()
    cfg = {"track_objects": ["person"], "ppe_classes": ["helmet"]}
    reports.init_context(cfg, {}, r, str(tmp_path), [])

    tracker = PersonTracker.__new__(PersonTracker)
    tracker.cam_id = 1
    tracker.line_orientation = "vertical"
    tracker.line_ratio = 0.5
    tracker.reverse = False
    tracker.groups = ["person"]
    tracker.in_counts = {}
    tracker.out_counts = {}
    tracker.tracks = {}
    tracker.track_states = {}
    tracker.track_state_ttl = 120.0
    tracker.stream_error = ""
    tracker.frame_queue = queue.Queue()
    tracker.det_queue = queue.Queue()
    tracker.out_queue = queue.Queue()
    tracker.running = False
    tracker.viewers = 0
    tracker.snap_dir = Path(tmp_path)
    tracker.redis = r
    tracker.ppe_classes = ["helmet"]
    tracker.cfg = {}
    tracker.debug_stats = {}
    tracker.device = None
    tracker.batch_size = 1
    tracker.cross_hysteresis = 15
    tracker.cross_min_travel_px = -1
    tracker.cross_min_frames = 0
    tracker.update_callback = None

    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = np.zeros((100, 100, 3), dtype=np.uint8)
    tracker.frame_queue.put(frame1)
    tracker.frame_queue.put(frame2)

    tracker.model_person = type("M", (), {"names": {0: "person"}})()

    dets = [
        [((10, 10, 20, 20), 0.9, "person")],
        [((70, 10, 20, 20), 0.9, "person")],
    ]

    def fake_detect_batch(frames, groups):
        return [dets.pop(0) for _ in frames]

    tracker.detector = SimpleNamespace(detect_batch=fake_detect_batch)

    class StubTrack:
        def __init__(self, bbox):
            self._bbox = bbox
            self.track_id = 1
            self.det_class = "person"
            self.det_conf = 0.9
            self.age = 2

        def is_confirmed(self):
            return True

        def to_ltrb(self):
            return self._bbox

    bboxes = [(10, 10, 30, 30), (70, 10, 90, 30)]

    class StubDS:
        def __init__(self):
            self.i = 0

        def update_tracks(self, detections, frame=None):
            bbox = bboxes[self.i]
            self.i += 1
            return [StubTrack(bbox)]

    tracker.tracker = StubDS()

    def fake_imwrite(path, img):
        Path(path).write_bytes(b"data")
        return True

    monkeypatch.setattr(manager_mod.cv2, "imwrite", fake_imwrite, raising=False)

    inf = InferWorker(tracker)
    post = PostProcessWorker(tracker)
    inf.run()
    post.run()

    logs = [json.loads(x) for x in r.zrange("person_logs", 0, -1)]
    assert logs and logs[0]["direction"] == "out"
    assert any(l.get("needs_ppe") for l in logs)
