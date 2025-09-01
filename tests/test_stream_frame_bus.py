"""Tests for modules.stream.frame_bus."""

import numpy as np

from modules.stream import frame_bus


def setup_function() -> None:
    frame_bus._buffers.clear()


def test_register_and_publish() -> None:
    q = frame_bus.register("cam1", "cons1", maxlen=2)
    frame = np.zeros((1, 1), dtype=np.uint8)
    frame_bus.publish("cam1", frame, 123)
    assert len(q) == 1
    out_frame, ts = q[0]
    assert ts == 123
    np.testing.assert_array_equal(out_frame, frame)


def test_publish_to_multiple_consumers() -> None:
    q1 = frame_bus.register("cam1", "cons1")
    q2 = frame_bus.register("cam1", "cons2")
    frame = np.zeros((1, 1), dtype=np.uint8)
    frame_bus.publish("cam1", frame, 1)
    assert len(q1) == 1
    assert len(q2) == 1


def test_unregister_stops_delivery() -> None:
    q = frame_bus.register("cam1", "cons1")
    frame_bus.unregister("cam1", "cons1")
    frame_bus.publish("cam1", np.zeros((1, 1), dtype=np.uint8), 1)
    assert len(q) == 0


def test_publish_drops_oldest() -> None:
    q = frame_bus.register("cam1", "cons1", maxlen=2)
    frame_bus.publish("cam1", np.array([[1]], dtype=np.uint8), 1)
    frame_bus.publish("cam1", np.array([[2]], dtype=np.uint8), 2)
    frame_bus.publish("cam1", np.array([[3]], dtype=np.uint8), 3)
    assert len(q) == 2
    frames = [f[0, 0] for f, _ in q]
    assert frames == [2, 3]
