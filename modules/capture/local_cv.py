from __future__ import annotations

"""OpenCV based local camera capture."""

from typing import TYPE_CHECKING

import numpy as np

from utils.logging import log_capture_event

from .base import FrameSourceError, IFrameSource

if TYPE_CHECKING:  # pragma: no cover - optional dependency
    import cv2


class LocalCvSource(IFrameSource):
    """Capture frames from a local camera using OpenCV."""

    def __init__(self, device: int | str = 0, *, cam_id: int | str | None = None) -> None:
        super().__init__(str(device), cam_id=cam_id)
        self.cap: "cv2.VideoCapture | None" = None

    def open(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self.uri)
        # minimize internal buffering
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            log_capture_event(self.cam_id, "open_failed", uri=self.uri)
            raise FrameSourceError("CONNECT_TIMEOUT")
        self.cap = cap
        log_capture_event(self.cam_id, "opened", uri=self.uri)

    def read(self, timeout: float | None = None) -> np.ndarray:
        if self.cap is None:
            raise FrameSourceError("NOT_OPEN")
        # drop-old behaviour: grab all pending frames and keep the latest
        for _ in range(2):
            self.cap.grab()
        ret, frame = self.cap.read()
        if not ret or frame is None:
            log_capture_event(self.cam_id, "read_timeout")
            raise FrameSourceError("READ_TIMEOUT")
        return frame

    def info(self) -> dict[str, float | int]:
        if not self.cap:
            return {}
        import cv2

        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        return {"w": w, "h": h, "fps": fps}

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            log_capture_event(self.cam_id, "closed")
