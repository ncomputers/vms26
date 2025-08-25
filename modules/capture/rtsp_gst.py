from __future__ import annotations

"""RTSP capture via GStreamer pipelines."""

import cv2
import numpy as np

from .base import IFrameSource, FrameSourceError
from utils.logging import log_capture_event


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
        latency_ms: int = 100,
        use_nv: bool = False,
        cam_id: int | str | None = None,
    ) -> None:
        super().__init__(uri, cam_id=cam_id)
        self.tcp = tcp
        self.latency_ms = latency_ms
        self.use_nv = use_nv
        self.cap: cv2.VideoCapture | None = None

    def _build_pipeline(self) -> str:
        proto = "tcp" if self.tcp else "udp"
        if self.use_nv:
            decode = "nvv4l2decoder ! videoconvert"
        else:
            decode = "rtph264depay ! h264parse ! avdec_h264 ! videoconvert"
        pipeline = (
            f"rtspsrc location={self.uri} protocols={proto} latency={self.latency_ms} ! "
            f"{decode} ! appsink sync=false drop=true max-buffers=1"
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
            raise FrameSourceError("READ_TIMEOUT")
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
