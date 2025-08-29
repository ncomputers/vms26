#!/usr/bin/env python3
"""Soak test for the PersonTracker logging logic.

The script simulates a camera stream for a configurable duration
and verifies that Redis keys remain unique and counts stay
consistent. It is intended to be run manually for long running
validation (e.g. an hour).
"""

from __future__ import annotations

import argparse
import json
import queue
import time
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import numpy as np

from modules.tracker import InferWorker, PersonTracker, PostProcessWorker


def _make_tracker(tmpdir: Path, r) -> PersonTracker:
    t = PersonTracker.__new__(PersonTracker)
    t.cam_id = 1
    t.line_orientation = "vertical"
    t.line_ratio = 0.5
    t.reverse = False
    t.groups = ["person"]
    t.in_counts = {}
    t.out_counts = {}
    t.tracks = {}
    t.frame_queue = queue.Queue()
    t.det_queue = queue.Queue()
    t.out_queue = queue.Queue()
    t.running = False
    t.viewers = 0
    t.snap_dir = tmpdir
    t.redis = r
    t.ppe_classes = []
    t.cfg = {}
    t.debug_stats = {}
    t.device = None
    t.batch_size = 1
    t.count_cooldown = 2
    t.cross_hysteresis = 15
    t.model_person = type("M", (), {"names": {0: "person"}})()
    return t


def _simulate_pass(tracker: PersonTracker) -> None:
    bboxes = [(10, 10, 30, 30), (70, 10, 90, 30)]
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


def main(seconds: int) -> None:
    r = fakeredis.FakeRedis()
    tmpdir = Path("/tmp/soak")
    tmpdir.mkdir(exist_ok=True)
    tracker = _make_tracker(tmpdir, r)
    end = time.time() + seconds
    while time.time() < end:
        _simulate_pass(tracker)
        time.sleep(0.01)

    logs = r.zrange("person_logs", 0, -1)
    assert len(logs) == tracker.in_counts.get("person", 0)
    assert len(logs) == len({json.loads(x)["track_id"] for x in logs})
    print(f"Logged {len(logs)} events without duplicates")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PersonTracker soak test")
    parser.add_argument("--seconds", type=int, default=3600, help="Duration of the test")
    args = parser.parse_args()
    main(args.seconds)
