from __future__ import annotations

import platform
from typing import Optional

import cv2
import numpy as np

from .base_stream import BaseStream


class OpenCVCameraStream(BaseStream):
    def __init__(
        self,
        url: str | int,
        width: int | None = None,
        height: int | None = None,
        transport: str = "tcp",
        start_thread: bool = True,
        **kwargs,
    ) -> None:
        self.cap: Optional[cv2.VideoCapture] = None
        super().__init__(
            url=str(url),
            width=width,
            height=height,
            transport=transport,
            queue_size=1,
            start_thread=start_thread,
        )

    # ------------------------------------------------------------------
    def _start_backend(self) -> None:
        src = int(self.url) if str(self.url).isdigit() else self.url
        if platform.system() == "Windows":
            self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(src)

    def _read_frame(self) -> Optional[np.ndarray]:
        if not self.cap:
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def _release_backend(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None
