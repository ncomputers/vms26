from __future__ import annotations

import time
from collections import deque
from typing import Deque, Optional

import numpy as np

from app.core.lifecycle import StoppableThread, lifecycle_manager
from app.core.utils import getenv_num

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

from utils.jpeg import encode_jpeg


class CaptureLoop(StoppableThread):
    """Dummy capture loop generating blank frames.

    This minimal implementation avoids external dependencies while still
    exercising the threading behaviour expected by the server."""

    def __init__(self, pipeline: "Pipeline") -> None:
        cam_id = pipeline.cam_cfg.get("id", id(pipeline))
        super().__init__(daemon=True, name=f"cap-{cam_id}")
        self.pipeline = pipeline

    def run(self) -> None:  # pragma: no cover - simple loop
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        while self.running:
            if len(self.pipeline.queue) == self.pipeline.queue.maxlen:
                try:
                    self.pipeline.queue.popleft()
                except IndexError:
                    pass
            self.pipeline.queue.append(frame.copy())
            time.sleep(0.05)


class ProcessLoop(StoppableThread):
    """Encode frames from the capture loop to JPEG bytes."""

    def __init__(self, pipeline: "Pipeline") -> None:
        cam_id = pipeline.cam_cfg.get("id", id(pipeline))
        super().__init__(daemon=True, name=f"proc-{cam_id}")
        self.pipeline = pipeline
        self.target_fps = getenv_num("VMS26_TARGET_FPS", 15, int)
        self.last_processed_ts = time.time()

    def run(self) -> None:  # pragma: no cover - simple loop
        min_interval = 1.0 / float(self.target_fps) if self.target_fps > 0 else 0.0
        while self.running:
            if not self.pipeline.queue:
                time.sleep(0.005)
                continue
            now = time.time()
            dt = now - self.last_processed_ts
            if min_interval and dt < min_interval:
                time.sleep(min_interval - dt)
            try:
                frame = self.pipeline.queue.popleft()
            except IndexError:
                continue
            if cv2 is None or not hasattr(cv2, "imencode"):
                continue
            q = getenv_num("VMS26_JPEG_QUALITY", 80, int)
            self.pipeline._frame_bytes = encode_jpeg(frame, q)
            self.last_processed_ts = time.time()


class Pipeline:
    """Simple demo pipeline with capture and process loops."""

    def __init__(self, cam_cfg: dict) -> None:
        self.cam_cfg = cam_cfg
        maxlen = getenv_num("VMS26_QUEUE_MAX", 2, int)
        self.queue: Deque[np.ndarray] = deque(maxlen=maxlen)
        self._frame_bytes: bytes | None = None
        self.capture = CaptureLoop(self)
        self.process = ProcessLoop(self)

    def start(self) -> None:
        """Start capture and processing threads."""
        lifecycle_manager.register_signal_handlers()
        lifecycle_manager.register_pipeline(self)
        self.capture.start()
        self.process.start()

    def stop(self) -> None:
        """Stop all threads."""
        lifecycle_manager.unregister_pipeline(self)
        self.capture.stop()
        self.process.stop()
        self.capture.join(timeout=2.0)
        self.process.join(timeout=2.0)

    def get_frame_bytes(self) -> Optional[bytes]:
        """Return latest encoded frame bytes."""
        return self._frame_bytes
