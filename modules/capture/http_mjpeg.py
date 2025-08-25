from __future__ import annotations

"""HTTP MJPEG frame source."""

import io
import queue
import threading
from typing import Optional

import numpy as np
import requests
from PIL import Image

from .base import IFrameSource, FrameSourceError
from utils.logging import log_capture_event


class HttpMjpegSource(IFrameSource):
    """Parse multipart JPEG streams over HTTP."""

    def __init__(
        self,
        uri: str,
        *,
        max_queue: int = 1,
        cam_id: int | str | None = None,
    ) -> None:
        super().__init__(uri, cam_id=cam_id)
        self.max_queue = max_queue
        self._resp: requests.Response | None = None
        self._thread: threading.Thread | None = None
        self._q: queue.Queue[bytes] = queue.Queue(max_queue)
        self._stop = threading.Event()

    def open(self) -> None:
        resp = requests.get(self.uri, stream=True, timeout=5)
        if resp.status_code == 406:
            raise FrameSourceError("NO_VIDEO_STREAM")
        if resp.status_code >= 400:
            raise FrameSourceError("CONNECT_TIMEOUT")
        self._resp = resp
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        log_capture_event(self.cam_id, "opened", backend="http", uri=self.uri)

    def _reader(self) -> None:
        assert self._resp is not None
        buffer = b""
        for chunk in self._resp.iter_content(chunk_size=1024):
            if self._stop.is_set():
                break
            buffer += chunk
            while True:
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9")
                if start != -1 and end != -1 and end > start:
                    jpg = buffer[start : end + 2]
                    buffer = buffer[end + 2 :]
                    if self._q.full():
                        try:
                            self._q.get_nowait()
                        except queue.Empty:
                            pass
                    self._q.put(jpg)
                else:
                    break

    def read(self, timeout: float | None = None) -> np.ndarray:
        try:
            jpg = self._q.get(timeout=timeout)
        except queue.Empty:
            log_capture_event(self.cam_id, "read_timeout", backend="http")
            raise FrameSourceError("READ_TIMEOUT")
        img = Image.open(io.BytesIO(jpg)).convert("RGB")
        arr = np.array(img)[:, :, ::-1]
        return arr

    def info(self) -> dict[str, int | float]:
        return {}

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        if self._resp:
            self._resp.close()
            self._resp = None
        log_capture_event(self.cam_id, "closed", backend="http")
