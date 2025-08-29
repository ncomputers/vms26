from __future__ import annotations

"""HTTP MJPEG frame source."""

import io
import logging
import queue
import threading

import numpy as np
import requests
from PIL import Image

from utils.logging import log_capture_event
from utils.logx import log_throttled

from .base import Backoff, FrameSourceError, IFrameSource

logger = logging.getLogger(__name__)


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
        self._backoff = Backoff()

    def open(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        while not self._stop.is_set():
            buffer = b""
            try:
                resp = requests.get(self.uri, stream=True, timeout=5)
                if resp.status_code == 406:
                    raise RuntimeError("NO_VIDEO_STREAM")
                if resp.status_code >= 400:
                    raise RuntimeError(f"STATUS_{resp.status_code}")
                self._resp = resp
                log_capture_event(self.cam_id, "opened", backend="http", uri=self.uri)
                for chunk in resp.iter_content(chunk_size=1024):
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
                self._backoff.reset()
            except Exception as exc:
                log_throttled(
                    logger.warning,
                    f"[cap:{self.cam_id}] mjpeg reconnect: {exc}",
                    key=f"cap:{self.cam_id}:reconnect",
                    interval=5,
                )
                if self._resp:
                    self._resp.close()
                    self._resp = None
                self._backoff.sleep()
            finally:
                if self._resp:
                    self._resp.close()
                    self._resp = None

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
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        if self._resp:
            self._resp.close()
            self._resp = None
        log_capture_event(self.cam_id, "closed", backend="http")
