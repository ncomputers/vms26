import subprocess
import threading
from collections import deque

import ffmpeg
import numpy as np


class FFmpegCameraStream:
    def __init__(
        self, url, width=None, height=None, start_thread=True, downscale=1, **kwargs
    ):
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
        self.queue = deque(maxlen=30)
        self._stop = False
        self.proc = None
        self.t = None

        if start_thread:
            self._start_process()

    def _start_process(self):
        cmd = [
            "ffmpeg",
            "-rtsp_transport",
            "tcp",
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

        def _reader():
            buf = b""
            while not self._stop:
                if self.proc.stdout is None:
                    break
                chunk = self.proc.stdout.read(self.frame_size - len(buf))
                if not chunk:
                    break
                buf += chunk
                if len(buf) == self.frame_size:
                    frame = np.frombuffer(buf, dtype=np.uint8).reshape(
                        self.height, self.width, 3
                    )
                    self.queue.append(frame)
                    buf = b""

        self.t = threading.Thread(target=_reader, daemon=True)
        self.t.start()

    def read(self):
        return (True, self.queue.popleft()) if self.queue else (False, None)

    def release(self):
        self._stop = True
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
        if self.t and self.t.is_alive():
            self.t.join(timeout=1)
