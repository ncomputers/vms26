"""Lightweight runtime video processing pipeline.

This module decouples frame capture from processing. Frames are pushed
into a small in-memory queue by :class:`CaptureLoop` and consumed by
:class:`ProcessLoop`. Under load the queue drops older frames to keep
processing responsive.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, MutableMapping, Optional

import cv2

try:  # pragma: no cover - optional import during tests
    from app.runtime.config import get_config  # type: ignore
except Exception:  # pragma: no cover - fallback for legacy layout
    from types import SimpleNamespace
    from config import config as _CONFIG

    def get_config() -> SimpleNamespace:  # type: ignore
        return SimpleNamespace(**_CONFIG)

CFG = get_config()
TARGET_FPS: int = getattr(CFG, "target_fps", 24)
JPEG_QUALITY: int = getattr(CFG, "jpeg_quality", 55)


class FrameQueue:
    """Thread safe bounded queue for frames."""

    def __init__(self, maxlen: int = 3) -> None:
        self._dq: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def push(self, item: Dict[str, Any]) -> None:
        """Append ``item`` dropping the oldest element if full."""
        with self._lock:
            if len(self._dq) == self._dq.maxlen:
                self._dq.popleft()
            self._dq.append(item)

    def pop_latest(self) -> Optional[Dict[str, Any]]:
        """Return the newest frame dropping any stale entries."""
        with self._lock:
            if not self._dq:
                return None
            item = self._dq.pop()
            self._dq.clear()
            return item


class CaptureLoop(threading.Thread):
    """Continuously grab frames from ``source`` and push to ``queue``."""

    def __init__(self, source: Callable[[], Any], queue: FrameQueue) -> None:
        super().__init__(daemon=True)
        self.source = source
        self.queue = queue
        self.seq = 0
        self.period = 1.0 / float(TARGET_FPS)
        self._running = threading.Event()

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:  # pragma: no cover - simple loop
        self._running.set()
        while self._running.is_set():
            start = time.time()
            frame = self.source()
            self.seq += 1
            ts_ms = int(start * 1000)
            self.queue.push({"frame": frame, "ts_ms": ts_ms, "seq": self.seq})
            delay = self.period - (time.time() - start)
            if delay > 0:
                time.sleep(delay)


@dataclass
class Models:
    person: Callable[[Any], Any]
    ppe: Optional[Callable[[Any], Any]] = None


class ProcessLoop(threading.Thread):
    """Consume frames from queue and perform detection/overlay."""

    def __init__(
        self,
        queue: FrameQueue,
        models: Models,
        tracker: Any,
        count_fn: Callable[[Any], Dict[str, int]],
        overlay: Any,
        state: MutableMapping[str, Any],
    ) -> None:
        super().__init__(daemon=True)
        self.queue = queue
        self.models = models
        self.tracker = tracker
        self.count_fn = count_fn
        self.overlay = overlay
        self.state = state
        self._running = threading.Event()

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:  # pragma: no cover - simple loop
        self._running.set()
        while self._running.is_set():
            item = self.queue.pop_latest()
            if item is None:
                time.sleep(0.001)
                continue

            frame = item["frame"]
            start_total = time.time()

            start = time.time()
            boxes = self.models.person(frame)
            detect_ms = int((time.time() - start) * 1000)

            ppe_ms = 0
            ppe_meta = []
            if self.models.ppe:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box)
                    crop = frame[y1:y2, x1:x2]
                    t0 = time.time()
                    ppe_meta.append(self.models.ppe(crop))
                    ppe_ms += int((time.time() - t0) * 1000)

            tracks = self.tracker.update(boxes, ppe_meta)
            counts = self.count_fn(tracks)

            if os.getenv("VMS21_OVERLAY_PURE") == "1":
                try:
                    self.overlay.render_from_legacy(frame, tracks, counts)
                except Exception:  # pragma: no cover - optional overlay
                    logging.exception("overlay rendering failed")

            try:
                ok, enc = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                )
                if ok:
                    self.state.clear()
                    self.state.update(
                        {
                            "jpg": enc.tobytes(),
                            "ts_ms": item["ts_ms"],
                            "seq": item["seq"],
                            "counts": counts,
                        }
                    )
            except Exception:  # pragma: no cover - jpeg encoding optional
                logging.exception("jpeg encode failed")

            total_ms = int((time.time() - start_total) * 1000)
            logging.info(
                "dur_ms detect=%d ppe=%d total=%d", detect_ms, ppe_ms, total_ms
            )
