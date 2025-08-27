from __future__ import annotations

"""Helpers for managing application lifecycle and thread shutdown."""

import logging
import signal
import threading
import time
from typing import TYPE_CHECKING, Dict, Set

if TYPE_CHECKING:  # pragma: no cover
    from modules.pipeline import Pipeline


# Global event signalling application shutdown
shutdown_event = threading.Event()


class StoppableThread(threading.Thread):
    """Thread with a ``stop_event`` for graceful termination."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stop_event = threading.Event()

    def stop(self) -> None:
        """Request the thread to stop."""
        self.stop_event.set()

    @property
    def running(self) -> bool:
        """Whether the thread should keep running."""
        return not (self.stop_event.is_set() or shutdown_event.is_set())


_signals_registered = False


def _handle_stop_signal(signum, frame) -> None:  # pragma: no cover - simple handler
    shutdown_event.set()


def register_signal_handlers() -> None:
    """Register SIGINT/SIGTERM handlers to set the global stop flag."""
    global _signals_registered
    if _signals_registered:
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_stop_signal)
    _signals_registered = True


# --- Watchdog ---------------------------------------------------------------

_pipelines: Dict[int, Pipeline] = {}
_watchdog: Watchdog | None = None


class Watchdog(StoppableThread):
    """Monitor camera pipelines and log stalled processing."""

    def __init__(self, *, interval: float = 5.0, stale_after: float = 10.0) -> None:
        super().__init__(daemon=True, name="watchdog")
        self.interval = interval
        self.stale_after = stale_after
        self._warned: Set[int | str] = set()

    def run(self) -> None:  # pragma: no cover - simple loop
        while self.running:
            now = time.time()
            for pipeline in list(_pipelines.values()):
                last_ts = getattr(pipeline.process, "last_processed_ts", 0.0)
                cam_id = pipeline.cam_cfg.get("id", id(pipeline))
                if now - last_ts > self.stale_after:
                    if cam_id not in self._warned:
                        logging.warning("Camera %s processing stalled", cam_id)
                        self._warned.add(cam_id)
                else:
                    self._warned.discard(cam_id)
            self.stop_event.wait(self.interval)


def register_pipeline(pipeline: Pipeline) -> None:
    """Add a pipeline to be monitored by the watchdog."""
    _pipelines[id(pipeline)] = pipeline
    global _watchdog
    if _watchdog is None or not _watchdog.is_alive():
        _watchdog = Watchdog()
        _watchdog.start()


def unregister_pipeline(pipeline: Pipeline) -> None:
    """Remove a pipeline from watchdog monitoring."""
    _pipelines.pop(id(pipeline), None)
