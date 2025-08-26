import json
import queue
import sys
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.tracker import InferWorker, PersonTracker, PostProcessWorker


def _make_tracker(tmp_path, redis_client):
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
    tracker.redis = redis_client
    tracker.ppe_classes = []
    tracker.cfg = {}
    tracker.debug_stats = {}
    tracker.device = None
    tracker.batch_size = 1
    tracker.count_cooldown = 2
    tracker.cross_hysteresis = 15
    tracker.cross_min_travel_px = 10
    tracker.cross_min_frames = 2
    tracker.model_person = type("M", (), {"names": {0: "person"}})()
    return tracker


def _run_tracker(tracker, bboxes):
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    for _ in bboxes:
        tracker.frame_queue.put(frame)

    dets = [[((10, 10, 20, 20), 0.9, "person")] for _ in bboxes]

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

    class StubDS:
        def __init__(self):
            self.i = 0

        def update_tracks(self, detections, frame=None):
            bbox = bboxes[self.i]
            self.i += 1
            return [StubTrack(bbox)]

    tracker.tracker = StubDS()

    inf = InferWorker(tracker)
    post = PostProcessWorker(tracker)
    inf.run()
    post.run()


def test_multiple_crossings_count_once(tmp_path):
    r = fakeredis.FakeRedis()
    tracker = _make_tracker(tmp_path, r)

    def box(cx):
        return (cx - 10, 10, cx + 10, 30)

    centers = [
        20,
        80,
        20,
        80,
        20,
    ]
    bboxes = [box(c) for c in centers]

    _run_tracker(tracker, bboxes)

    assert tracker.in_counts.get("person", 0) == 1
    assert tracker.out_counts.get("person", 0) == 1
