from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np


class BaseStream(ABC):
    """Generic threaded frame reader with a small queue."""

    def __init__(
        self,
        url: str,
        width: int | None = None,
        height: int | None = None,
        transport: str = "tcp",
        queue_size: int = 30,
        start_thread: bool = True,
    ) -> None:
        self.url = url
        self.width = width
        self.height = height
        self.transport = transport
        self.queue: Deque[np.ndarray] = deque(maxlen=queue_size)
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        if start_thread:
            self.start()

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start backend and reader thread."""
        self._start_backend()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self) -> None:
        while not self._stop:
            frame = self._read_frame()
            if frame is None:
                break
            self.queue.append(frame)

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        return (True, self.queue.popleft()) if self.queue else (False, None)

    def release(self) -> None:
        self._stop = True
        self._release_backend()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    # ------------------------------------------------------------------
    @abstractmethod
    def _start_backend(self) -> None:
        """Start the underlying capture backend."""

    @abstractmethod
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from the backend."""

    @abstractmethod
    def _release_backend(self) -> None:
        """Clean up backend resources."""
