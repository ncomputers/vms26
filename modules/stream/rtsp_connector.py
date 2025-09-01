from __future__ import annotations

import os
import queue
import select
import subprocess
import threading
import time
from typing import Dict, List, Optional

import numpy as np

from utils import logx


class RtspConnector:
    """Lightweight FFmpeg based RTSP frame reader.

    Frames are published to subscriber queues.  The connector automatically
    restarts the underlying FFmpeg process using an exponential backoff policy
    and a watchdog timer that triggers when frames stop arriving.
    """

    # states
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RETRYING = "retrying"

    def __init__(self, url: str, width: int, height: int, fps: float = 30.0) -> None:
        self.url = url
        self.width = width
        self.height = height
        self.frame_size = width * height * 3
        self.expected_interval = 1.0 / fps if fps > 0 else 0.033
        self.state = self.STOPPED
        self.last_error: str = ""
        self.last_frame_ts: float = 0.0
        self.fps_in: float = 0.0
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._subs: List[queue.Queue[np.ndarray]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.state = self.STOPPED

    def subscribe(self, maxsize: int = 1) -> queue.Queue[np.ndarray]:
        q: queue.Queue[np.ndarray] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def stats(self) -> Dict[str, object]:
        return {
            "state": self.state,
            "last_error": self.last_error,
            "fps_in": round(self.fps_in, 2),
            "last_frame_ts": self.last_frame_ts,
            "subscribers": len(self._subs),
        }

    # ------------------------------------------------------------------
    def _run(self) -> None:
        backoff = 1
        logx.event("STREAM_START", url=self.url)
        while not self._stop.is_set():
            self.state = self.CONNECTING
            try:
                self._proc = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-rtsp_transport",
                        "tcp",
                        "-fflags",
                        "nobuffer",
                        "-flags",
                        "low_delay",
                        "-i",
                        self.url,
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "bgr24",
                        "-vf",
                        f"scale={self.width}:{self.height}",
                        "pipe:1",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            except Exception as exc:
                self.state = self.ERROR
                self.last_error = str(exc)
                logx.error("STREAM_ERROR", url=self.url, error=self.last_error)
                return

            self.last_frame_ts = time.time()
            while not self._stop.is_set() and self._proc.poll() is None:
                if not self._proc.stdout:
                    break
                timeout = 0.5
                ready, _, _ = select.select([self._proc.stdout], [], [], timeout)
                now = time.time()
                interval = 1.0 / self.fps_in if self.fps_in > 0 else self.expected_interval
                if not ready:
                    if now - self.last_frame_ts > 3 * interval:
                        logx.warn("STREAM_RETRY", url=self.url, reason="watchdog")
                        self.state = self.RETRYING
                        self._proc.kill()
                        break
                    continue
                data = os.read(self._proc.stdout.fileno(), self.frame_size)
                if len(data) != self.frame_size:
                    self.last_error = "short read"
                    self.state = self.ERROR
                    logx.error("STREAM_ERROR", url=self.url, error=self.last_error)
                    self._proc.kill()
                    break
                frame = np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3)
                if self.state != self.CONNECTED:
                    self.state = self.CONNECTED
                    logx.event("STREAM_CONNECTED", url=self.url)
                self._publish(frame)
                if self.last_frame_ts:
                    dt = now - self.last_frame_ts
                    if dt > 0:
                        inst = 1.0 / dt
                        self.fps_in = (self.fps_in * 0.9) + (0.1 * inst) if self.fps_in else inst
                self.last_frame_ts = now
            if self._stop.is_set():
                break
            if self._proc and self._proc.poll() is not None and self.state != self.RETRYING:
                self.state = self.ERROR
                self.last_error = f"ffmpeg exited: {self._proc.returncode}"
                logx.error("STREAM_ERROR", url=self.url, error=self.last_error)
            self._cleanup_proc()
            if self._stop.is_set():
                break
            self.state = self.RETRYING
            logx.warn("STREAM_RETRY", url=self.url, sleep=backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
        self._cleanup_proc()

    def _cleanup_proc(self) -> None:
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def _publish(self, frame: np.ndarray) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(frame)
            except queue.Full:
                try:
                    q.get_nowait()
                except Exception:
                    pass
                try:
                    q.put_nowait(frame)
                except queue.Full:
                    pass
