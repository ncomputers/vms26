"""RTSP capture via GStreamer pipelines."""

from __future__ import annotations

import os
import time

import cv2
import numpy as np

from utils.logging import log_capture_event

from .base import FrameSourceError, IFrameSource


def ensure_gst() -> bool:
    """Return True if OpenCV has GStreamer support."""
    try:
        _ = cv2.getBuildInformation()
        return "GStreamer" in _
    except Exception:
        return False


class RtspGstSource(IFrameSource):
    """Capture RTSP using GStreamer appsink with drop-old behaviour."""

    def __init__(
        self,
        uri: str,
        *,
        tcp: bool = True,
        latency_ms: int = 200,
        use_nv: bool = False,
        cam_id: int | str | None = None,
    ) -> None:
        super().__init__(uri, cam_id=cam_id)
        env_tcp = os.getenv("VMS26_RTSP_TCP") == "1"
        self.tcp = tcp or env_tcp
        self.latency_ms = latency_ms
        self.use_nv = use_nv
        self.cap: cv2.VideoCapture | None = None
        self.restarts = 0
        self.last_frame_ts = 0.0

    def _build_pipeline(self) -> str:
        proto = "tcp" if self.tcp else "udp"
        if self.use_nv:
            decode = "rtph264depay ! h264parse ! nvv4l2decoder ! videoconvert"
        else:
            decode = "rtph264depay ! h264parse ! avdec_h264 ! videoconvert"
        latency = int(self.latency_ms)
        if latency < 0:
            latency = 0
        pipeline = (
            "rtspsrc location="
            f"{self.uri} protocols={proto} do-rtsp-keep-alive=true latency={latency} ! "
            f"{decode} ! appsink drop=true max-buffers=1 sync=false"
        )
        return pipeline

    def open(self) -> None:
        if not ensure_gst():
            raise FrameSourceError("UNSUPPORTED_CODEC")
        pipeline = self._build_pipeline()
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            log_capture_event(self.cam_id, "open_failed", backend="gst", uri=self.uri)
            raise FrameSourceError("CONNECT_TIMEOUT")
        self.cap = cap
        log_capture_event(self.cam_id, "opened", backend="gst", uri=self.uri)

    def read(self, timeout: float | None = None) -> np.ndarray:
        if self.cap is None:
            raise FrameSourceError("NOT_OPEN")
        # appsink drop=true ensures only latest frame is returned
        ret, frame = self.cap.read()
        if not ret:
            log_capture_event(self.cam_id, "read_timeout", backend="gst")
            self.restarts += 1
            self.close()
            time.sleep(0.1)
            self.open()
            ret, frame = self.cap.read()
            if not ret:
                raise FrameSourceError("READ_TIMEOUT")
        self.last_frame_ts = time.time()
        return frame

    def info(self) -> dict[str, int | float]:
        if not self.cap:
            return {}
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        return {"w": w, "h": h, "fps": fps}

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            log_capture_event(self.cam_id, "closed", backend="gst")
