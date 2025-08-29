import queue
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import numpy as np

import modules.tracker.manager as manager_mod
from modules.tracker import PersonTracker


def test_letterbox_unscale_counts(monkeypatch, tmp_path):
    r = fakeredis.FakeRedis()
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
    tracker.snap_dir = Path(tmp_path)
    tracker.out_queue = queue.Queue()
    tracker.redis = r
    tracker.ppe_classes = []
    tracker.cfg = {}
    tracker.debug_stats = {}
    tracker.device = None
    tracker.batch_size = 1
    tracker.cross_hysteresis = 15
    tracker.side_eps = 2.0
    tracker.scale = 0.5
    tracker.pad_x = 5
    tracker.pad_y = 10
    tracker.update_callback = None

    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = np.zeros((100, 100, 3), dtype=np.uint8)

    tracker.model_person = type("M", (), {"names": {0: "person"}})()

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

    bboxes = [(10, 15, 20, 25), (35, 15, 45, 25)]

    class StubDS:
        def __init__(self):
            self.i = 0

        def update_tracks(self, detections, frame=None):
            bbox = bboxes[self.i]
            self.i += 1
            return [StubTrack(bbox)]

    tracker.tracker = StubDS()
    monkeypatch.setattr(manager_mod.cv2, "imwrite", lambda path, img: True, raising=False)

    det1 = [((10, 15, 10, 10), 0.9, "person")]
    det2 = [((35, 15, 10, 10), 0.9, "person")]
    manager_mod.process_frame(tracker, frame1, det1)
    manager_mod.process_frame(tracker, frame2, det2)

    assert tracker.in_counts.get("person", 0) == 0
    assert tracker.out_counts.get("person", 0) == 1
    bbox = tracker.tracks[1]["bbox"]
    assert bbox == (60, 10, 80, 30)
