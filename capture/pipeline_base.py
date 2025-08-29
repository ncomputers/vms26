from __future__ import annotations

"""Abstract base class for camera capture pipelines.

The :class:`PipelineBase` defines a minimal interface for capture
pipelines used by the application. Subclasses are expected to handle the
actual capture/encode logic while this base class manages runtime
metrics and exposes lifecycle helpers.

All URL strings logged by this module have credentials redacted to avoid
accidental disclosure.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Dict, Optional
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


class PipelineBase(ABC):
    """Common functionality shared by capture pipelines.

    Subclasses must implement :meth:`start`, :meth:`stop`,
    :meth:`get_snapshot`, and :meth:`metrics`. The default
    :meth:`frames` generator yields JPEG-encoded frames only when at
    least one client is connected.
    """

    def __init__(self, uri: str | None = None) -> None:
        self.uri = self._redact(uri) if uri else None
        self._lock = threading.Lock()
        self._restart_guard = asyncio.Event()
        self._restart_guard.set()
        self._running = False
        self._clients = 0
        self.connect_since: float | None = None
        self.reconnect_count = 0
        self.codec: Optional[str] = None
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.pipeline: Optional[str] = None
        self.transport: Optional[str] = None
        self._last_frame_ts = 0.0
        self._in_count = 0
        self._out_count = 0

    # ------------------------------------------------------------------
    # lifecycle helpers
    def _on_start(self) -> None:
        """Mark the pipeline as running.

        Subclasses should call this at the beginning of ``start`` after
        successfully allocating resources.
        """

        with self._lock:
            if self._running:
                logger.debug("start() called while already running")
                return
            self._restart_guard.clear()
            self._running = True
            self.connect_since = time.time()
            logger.info("pipeline started")

    def _on_stop(self) -> None:
        """Mark the pipeline as stopped.

        Subclasses should call this at the end of ``stop`` after releasing
        any resources.
        """

        with self._lock:
            if not self._running:
                logger.debug("stop() called while not running")
                return
            self._running = False
            self._restart_guard.set()
            logger.info("pipeline stopped")

    # ------------------------------------------------------------------
    # abstract API
    @abstractmethod
    def start(self) -> None:
        """Start the capture pipeline."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the capture pipeline."""

    @abstractmethod
    def get_snapshot(self) -> bytes:
        """Return a single JPEG encoded frame."""

    # ------------------------------------------------------------------
    def frames(self) -> Generator[bytes, None, None]:
        """Yield JPEG frames for connected clients.

        The generator automatically tracks connected client count and
        updates throughput metrics. Subclasses may override this method
        but should call ``super().frames()`` to maintain metrics.
        """

        self._clients += 1
        logger.debug("client connected: total=%d", self._clients)
        try:
            while self._running:
                frame = self.get_snapshot()
                if frame:
                    self._out_count += 1
                    self._last_frame_ts = time.time()
                    yield frame
                else:
                    time.sleep(0.05)
        finally:
            self._clients -= 1
            logger.debug("client disconnected: total=%d", self._clients)

    # ------------------------------------------------------------------
    # metrics helpers
    def _record_input_frame(self) -> None:
        self._in_count += 1
        self._last_frame_ts = time.time()

    def metrics(self) -> Dict[str, object]:
        with self._lock:
            now = time.time()
            elapsed = (now - self.connect_since) if self.connect_since else 0.0
            in_fps = self._in_count / elapsed if elapsed > 0 else 0.0
            out_fps = self._out_count / elapsed if elapsed > 0 else 0.0
            last_age = (now - self._last_frame_ts) * 1000 if self._last_frame_ts else None
            return {
                "connected": self._running,
                "connect_since": self.connect_since,
                "in_fps": in_fps,
                "out_fps": out_fps,
                "last_frame_age_ms": last_age,
                "reconnect_count": self.reconnect_count,
                "codec": self.codec,
                "width": self.width,
                "height": self.height,
                "pipeline": self.pipeline,
                "transport": self.transport,
            }

    # ------------------------------------------------------------------
    @staticmethod
    def _redact(url: str) -> str:
        """Return ``url`` with credentials removed."""

        if "@" not in url:
            return url
        parts = urlsplit(url)
        netloc = parts.hostname or ""
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
