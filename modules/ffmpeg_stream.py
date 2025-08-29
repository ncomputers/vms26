from __future__ import annotations

import subprocess
from typing import Optional

import ffmpeg
import numpy as np

from .base_stream import BaseStream


class FFmpegCameraStream(BaseStream):
    def __init__(
        self,
        url: str,
        width: int | None = None,
        height: int | None = None,
        transport: str = "tcp",
        start_thread: bool = True,
        downscale: int = 1,
        **kwargs,
    ) -> None:
        self.url = url
        self.width = width
        self.height = height
        if self.width is None or self.height is None:
            info = ffmpeg.probe(url)
            stream = next(
                (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
                {},
            )
            self.width = stream.get("width", 0)
            self.height = stream.get("height", 0)
        if downscale and downscale != 1:
            self.width //= downscale
            self.height //= downscale
        self.frame_size = self.width * self.height * 3
        self.proc: Optional[subprocess.Popen[bytes]] = None
        super().__init__(
            url=url,
            width=self.width,
            height=self.height,
            transport=transport,
            queue_size=30,
            start_thread=start_thread,
        )

    # ------------------------------------------------------------------
    def _start_backend(self) -> None:
        self._start_process()

    def _start_process(self) -> None:
        cmd = [
            "ffmpeg",
            "-rtsp_transport",
            self.transport,
            "-i",
            self.url,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-vf",
            f"scale={self.width}:{self.height}",
            "pipe:1",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        self._buf = b""

    def _read_frame(self) -> Optional[np.ndarray]:
        if not self.proc or self.proc.stdout is None:
            return None
        while len(self._buf) < self.frame_size and not self._stop:
            chunk = self.proc.stdout.read(self.frame_size - len(self._buf))
            if not chunk:
                return None
            self._buf += chunk
        if len(self._buf) != self.frame_size:
            return None
        frame = np.frombuffer(self._buf, dtype=np.uint8).reshape(
            self.height, self.width, 3
        )
        self._buf = b""
        return frame

    def _release_backend(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
