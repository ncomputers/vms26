from __future__ import annotations

import queue
import threading
import time
from os import getenv
from typing import Optional

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

from utils.jpeg import encode_jpeg


class CaptureLoop(threading.Thread):
    """Dummy capture loop generating blank frames.

    This minimal implementation avoids external dependencies while still
    exercising the threading behaviour expected by the server."""

    def __init__(self, pipeline: "Pipeline") -> None:
        super().__init__(daemon=True)
        self.pipeline = pipeline
        self.running = True

    def run(self) -> None:  # pragma: no cover - simple loop
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        while self.running:
            if self.pipeline.queue.full():
                try:
                    self.pipeline.queue.get_nowait()
                except queue.Empty:
                    pass
            self.pipeline.queue.put(frame.copy())
            time.sleep(0.05)


class ProcessLoop(threading.Thread):
    """Encode frames from the capture loop to JPEG overlays."""

    def __init__(self, pipeline: "Pipeline") -> None:
        super().__init__(daemon=True)
        self.pipeline = pipeline
        self.running = True

    def run(self) -> None:  # pragma: no cover - simple loop
        while self.running:
            try:
                frame = self.pipeline.queue.get(timeout=1)
            except queue.Empty:
                continue
            if cv2 is None:
                continue
            q = int(getenv("VMS26_JPEG_QUALITY", 80))
            self.pipeline._overlay_bytes = encode_jpeg(frame, q)


class Pipeline:
    """Simple demo pipeline with capture and process loops."""

    def __init__(self, cam_cfg: dict) -> None:
        self.cam_cfg = cam_cfg
        self.queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)
        self._overlay_bytes: bytes | None = None
        self.capture = CaptureLoop(self)
        self.process = ProcessLoop(self)

    def start(self) -> None:
        """Start capture and processing threads."""
        self.capture.start()
        self.process.start()

    def stop(self) -> None:
        """Stop all threads."""
        self.capture.running = False
        self.process.running = False

    def get_overlay_bytes(self) -> Optional[bytes]:
        """Return latest encoded overlay frame bytes."""
        return self._overlay_bytes
