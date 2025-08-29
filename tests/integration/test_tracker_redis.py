import json
import queue
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import numpy as np
import pytest

from modules.tracker import InferWorker, PersonTracker, PostProcessWorker
from utils.redis import trim_sorted_set
from utils.redis_facade import RedisFacade


@pytest.fixture(scope="session")
def redis_server():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def redis_client(redis_server):
    redis_server.flushdb()
    return redis_server


def test_trim_sorted_set_removes_old_entries(redis_client):
    now = int(time.time())
    redis_client.zadd("logs", {"old": now - 100, "new": now})
    trim_sorted_set(RedisFacade(redis_client), "logs", now, retention_secs=50)
    assert redis_client.zrange("logs", 0, -1) == ["new"]


def test_person_tracker_logs_to_redis(redis_client, monkeypatch, tmp_path):
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
    tracker.count_cooldown = 2
    tracker._counted = {}
    tracker.detector_fps = 0

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    for _ in range(3):
        tracker.frame_queue.put(frame)

    tracker.model_person = SimpleNamespace(names={0: "person"})

    detections = [
        [((10, 10, 20, 20), 0.9, "person")],
        [((70, 10, 20, 20), 0.9, "person")],
        [((10, 10, 20, 20), 0.9, "person")],
    ]

    def fake_detect_batch(frames, groups):
        return [detections.pop(0) for _ in frames]

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

    boxes = [
        (10, 10, 30, 30),
        (70, 10, 90, 30),
        (10, 10, 30, 30),
    ]

    class StubDS:
        def __init__(self):
            self.i = 0

        def update_tracks(self, detections, frame=None):
            box = boxes[self.i]
            self.i += 1
            return [StubTrack(box)]

    tracker.tracker = StubDS()

    import modules.tracker.manager as manager_mod

    monkeypatch.setattr(manager_mod.cv2, "imwrite", lambda path, img: True, raising=False)

    inf = InferWorker(tracker)
    post = PostProcessWorker(tracker)
    inf.run()
    post.run()

    raw_logs = redis_client.zrange("person_logs", 0, -1)
    logs = [json.loads(l) for l in raw_logs]
    assert len(logs) == 2
    directions = {e["direction"] for e in logs}
    assert directions == {"in", "out"}
