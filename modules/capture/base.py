from __future__ import annotations

"""Common base classes for frame sources."""

import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np


class FrameSourceError(Exception):
    """Raised when a frame source encounters a fatal error."""


class Backoff:
    """Simple exponential backoff helper."""

    def __init__(self, base: float = 0.5, max_sleep: float | None = None) -> None:
        self.base = base
        self.max_sleep = max_sleep or float(os.getenv("VMS26_RECONNECT_MAXSLEEP", "8"))
        self._n = 0

    def reset(self) -> None:
        self._n = 0

    def next(self) -> float:
        delay = min(self.base * (2**self._n), self.max_sleep)
        self._n += 1
        return delay

    def sleep(self) -> None:
        time.sleep(self.next())


class IFrameSource(ABC):
    """Interface implemented by all frame capture sources."""

    def __init__(self, uri: str, *, cam_id: int | str | None = None) -> None:
        self.uri = uri
        self.cam_id = cam_id

    @abstractmethod
    def open(self) -> None:
        """Allocate underlying resources and start the capture."""

    @abstractmethod
    def read(self, timeout: float | None = None) -> np.ndarray:
        """Return the latest frame as a BGR ``ndarray``."""

    @abstractmethod
    def info(self) -> Dict[str, Any]:
        """Return basic stream information such as width/height/fps."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the source."""
