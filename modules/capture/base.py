from __future__ import annotations

"""Common base classes for frame sources."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np


class FrameSourceError(Exception):
    """Raised when a frame source encounters a fatal error."""


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
