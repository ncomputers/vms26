"""Tests for FrameBus ring buffer."""

import time

import numpy as np

from modules.frame_bus import FrameBus


def test_frame_bus_put_get():
    bus = FrameBus()
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    bus.put(frame)
    out = bus.get_latest(100)
    assert out is not None
    assert out.shape == (2, 3, 3)


def test_frame_bus_timeout():
    bus = FrameBus()
    start = time.time()
    out = bus.get_latest(100)
    end = time.time()
    assert out is None
    assert end - start >= 0.09


def test_frame_bus_drop_old():
    bus = FrameBus()
    bus.put(np.ones((1, 1, 3), dtype=np.uint8))
    bus.put(np.full((1, 1, 3), 2, dtype=np.uint8))
    bus.put(np.full((1, 1, 3), 3, dtype=np.uint8))
    out = bus.get_latest(0)
    assert out[0, 0, 0] == 3


def test_frame_bus_info():
    bus = FrameBus()
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    bus.put(frame)
    time.sleep(0.01)
    bus.put(frame)
    info = bus.info()
    assert info.w == 20
    assert info.h == 10
    assert info.fps > 0
