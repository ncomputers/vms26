"""Minimal test for GStreamer stream using mocked backend."""

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.gstreamer_stream import GstCameraStream  # noqa: E402


def _check_stream(monkeypatch, cls):
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    monkeypatch.setattr(cls, "_start_backend", lambda self: None)

    def fake_read(self):
        self._stop = True
        return frame

    monkeypatch.setattr(cls, "_read_frame", fake_read)
    stream = cls("demo", width=1, height=1)
    time.sleep(0.05)
    ok, out = stream.read()
    assert ok
    assert out.shape == (1, 1, 3)
    stream.release()


def test_gst_stream(monkeypatch):
    _check_stream(monkeypatch, GstCameraStream)
