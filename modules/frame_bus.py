"""Thread-safe ring buffer for camera frames."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class FrameInfo:
    """Lightweight structure with frame metadata."""

    w: int = 0
    h: int = 0
    fps: float = 0.0


class FrameBus:
    """Ring buffer holding at most two frames.

    The buffer keeps only the most recent frames to minimise latency. ``put``
    drops the oldest frame when the capacity is exceeded. ``get_latest`` waits
    up to ``timeout_ms`` for a frame and returns ``None`` on timeout.
    """

    def __init__(self) -> None:
        self._buf: deque[np.ndarray] = deque(maxlen=2)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._info = FrameInfo()
        self._last_ts: Optional[float] = None

    # ------------------------------------------------------------------
    def put(self, frame: np.ndarray) -> None:
        """Insert ``frame`` into the buffer, dropping older ones."""
        if frame is None:
            return
        with self._cond:
            self._buf.append(frame)
            h, w = frame.shape[:2]
            if self._info.w != w or self._info.h != h:
                self._info.w, self._info.h = w, h
            now = time.time()
            if self._last_ts is not None:
                dt = now - self._last_ts
                if dt > 0:
                    self._info.fps = 1.0 / dt
            self._last_ts = now
            self._cond.notify_all()

    # ------------------------------------------------------------------
    def get_latest(self, timeout_ms: int) -> Optional[np.ndarray]:
        """Return the newest frame or ``None`` if none arrives in time."""
        deadline = time.time() + timeout_ms / 1000.0
        with self._cond:
            while not self._buf:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            return self._buf[-1].copy()

    # ------------------------------------------------------------------
    def info(self) -> FrameInfo:
        """Return the latest frame metadata."""
        with self._lock:
            return FrameInfo(self._info.w, self._info.h, self._info.fps)
