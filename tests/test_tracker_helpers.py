import queue
import sys
import types
from types import SimpleNamespace
from typing import Any

import numpy as np

sys.modules.setdefault("cv2", types.SimpleNamespace())
import modules.tracker.manager as manager


def test_infer_batch(monkeypatch):
    calls: list[tuple[list[np.ndarray], tuple[str, ...]]] = []

    def detect_batch(batch, groups):
        calls.append((batch, tuple(groups)))
        return [["d1"], ["d2"]]

    tracker = SimpleNamespace(
        detector=SimpleNamespace(detect_batch=detect_batch),
        groups=["person"],
        det_queue=queue.Queue(maxsize=2),
        cam_id="1",
    )

    frames = [np.zeros((1, 1, 3)), np.ones((1, 1, 3))]
    res = manager.infer_batch(tracker, frames, frames)
    assert res == [["d1"], ["d2"]]
    assert calls and calls[0][0] == frames
    assert tracker.det_queue.qsize() == 2
    assert tracker.det_queue.get() == (frames[0], ["d1"])


def test_process_frame(monkeypatch):
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    detections = [((0.0, 0.0, 1.0, 1.0), 0.9, "person")]
    q = queue.Queue()
    update_calls: list[tuple[list[tuple], np.ndarray]] = []

    def update_tracks(dets, frame=None):
        update_calls.append((dets, frame))
        return []

    tracker = SimpleNamespace(
        _purge_counted=lambda: None,
        face_tracking_enabled=False,
        tracker=SimpleNamespace(update_tracks=update_tracks),
        line_orientation="horizontal",
        line_ratio=0.5,
        tasks=["in_count", "out_count"],
        tracks={},
        in_counts={},
        out_counts={},
        in_count=0,
        out_count=0,
        update_callback=None,
        show_lines=False,
        show_ids=False,
        show_track_lines=False,
        show_counts=False,
        renderer=None,
        out_queue=q,
        output_frame=None,
        cam_id="c1",
        reverse=False,
        count_cooldown=0,
        groups=["person"],
    )

    manager.process_frame(tracker, frame, detections)
    assert update_calls == [(detections, frame)]
    assert tracker.output_frame is None
    assert q.qsize() == 1


def test_process_frame_filters_invalid(monkeypatch):
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    det = SimpleNamespace(label="vehicle", bbox=[0, 0, 1, 1], score=0.9, feature=None)
    calls: list[list[Any]] = []

    def update_tracks(dets, frame=None):  # type: ignore[unused-argument]
        calls.append(dets)
        raise ValueError("bad det")

    tracker = SimpleNamespace(
        _purge_counted=lambda: None,
        face_tracking_enabled=False,
        tracker=SimpleNamespace(update_tracks=update_tracks),
        line_orientation="horizontal",
        line_ratio=0.5,
        tasks=[],
        tracks={},
        in_counts={},
        out_counts={},
        in_count=0,
        out_count=0,
        update_callback=None,
        show_lines=False,
        show_ids=False,
        show_track_lines=False,
        show_counts=False,
        renderer=None,
        out_queue=queue.Queue(),
        output_frame=None,
        cam_id="c1",
        reverse=False,
        count_cooldown=0,
        groups=["person"],
    )

    manager.process_frame(tracker, frame, [det])
    assert calls == [[]]
    assert tracker.tracks == {}


def test_process_frame_reinitializes_renderer_on_shape_change():
    q = queue.Queue()
    tracker = SimpleNamespace(
        _purge_counted=lambda: None,
        face_tracking_enabled=False,
        tracker=None,
        line_orientation="horizontal",
        line_ratio=0.5,
        tasks=[],
        tracks={},
        in_counts={},
        out_counts={},
        in_count=0,
        out_count=0,
        update_callback=None,
        show_lines=True,
        show_ids=False,
        show_track_lines=False,
        show_counts=False,
        renderer=None,
        out_queue=q,
        output_frame=None,
        cam_id="c1",
        reverse=False,
        count_cooldown=0,
        groups=["person"],
    )
    frame1 = np.zeros((2, 2, 3), dtype=np.uint8)
    manager.process_frame(tracker, frame1, [])
    r1 = tracker.renderer
    assert r1 is not None
    assert r1.frame.shape == frame1.shape
    frame2 = np.zeros((4, 4, 3), dtype=np.uint8)
    manager.process_frame(tracker, frame2, [])
    assert tracker.renderer is not None
    assert tracker.renderer.frame.shape == frame2.shape
    assert tracker.renderer is not r1
    tracker.renderer.queue.put(None)
    tracker.renderer.process.join()
    assert tracker.renderer.output.any()
    tracker.renderer.close()
