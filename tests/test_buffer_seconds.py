"""Purpose: Test buffer seconds module."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import types


class DummyCap:
    def isOpened(self):
        return True


sys.modules["cv2"] = types.SimpleNamespace(CAP_GSTREAMER=0, VideoCapture=lambda *a, **k: DummyCap())
import importlib

import modules.gstreamer_stream as gst_mod

importlib.reload(gst_mod)

from modules.gstreamer_stream import GstCameraStream


def test_gst_pipeline_simple():
    stream = GstCameraStream("rtsp://x", buffer_seconds=10, start_thread=False)
    assert "latency=100" in stream.pipeline
    assert "avdec_h264" in stream.pipeline
    assert "queue max-size-buffers=1" in stream.pipeline
    assert "drop=true" in stream.pipeline
