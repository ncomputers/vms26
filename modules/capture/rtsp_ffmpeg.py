from __future__ import annotations

"""RTSP capture using FFmpeg.

This source supports optional command-line flags via the ``FFMPEG_EXTRA_FLAGS``
environment variable. ``RTSP_RW_TIMEOUT_USEC`` and ``RTSP_STIMEOUT_USEC``
control the ``-rw_timeout`` and ``-stimeout`` parameters (in microseconds,
default ``5000000``). Stream dimensions are probed with ``ffprobe`` when not
specified explicitly.
"""

import logging
import os
import queue
import shlex
import subprocess
import threading
import time
from collections import deque

import ffmpeg
import numpy as np

from utils.logging import log_capture_event

from .base import FrameSourceError, IFrameSource

logger = logging.getLogger(__name__)


MAX_SHORT_READS = 3
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 10.0


class RtspFfmpegSource(IFrameSource):
    """Capture frames from an RTSP stream using FFmpeg.

    Frames are read on a background thread into a preallocated buffer. Complete
    frames are pushed into a two-element queue, dropping the oldest when full.
    Consecutive short reads trigger FFmpeg restarts with exponential backoff.
    """

    def __init__(
        self,
        uri: str,
        *,
        width: int | None = None,
        height: int | None = None,
        tcp: bool = True,
        latency_ms: int = 100,
        cam_id: int | str | None = None,
        rw_timeout_usec: int | None = None,
        stimeout_usec: int | None = None,
        extra_flags: list[str] | None = None,
    ) -> None:
        """Initialize the RTSP FFmpeg source.

        Parameters
        ----------
        uri:
            RTSP stream URI.
        width, height:
            Optional frame dimension overrides.
        tcp:
            Use TCP (``True``) or UDP (``False``) transport.
        latency_ms:
            Queue latency in milliseconds.
        cam_id:
            Optional camera identifier for logging.
        rw_timeout_usec:
            Microseconds before aborting blocking read/write operations
            passed to FFmpeg as ``-rw_timeout``. Defaults to ``5000000``.
        stimeout_usec:
            Microseconds to wait for establishing the connection passed as
            ``-stimeout``. Defaults to ``5000000``.
        extra_flags:
            Additional FFmpeg flags inserted before the input URL.
        """
        super().__init__(uri, cam_id=cam_id)
        self.width = width
        self.height = height
        self.tcp = tcp
        self.latency_ms = latency_ms
        self.rw_timeout_usec = rw_timeout_usec
        self.stimeout_usec = stimeout_usec
        self.extra_flags = extra_flags or []
        self.proc: subprocess.Popen[bytes] | None = None
        self._stderr_buffer: deque[str] = deque(maxlen=20)
        self._stderr_thread: threading.Thread | None = None
        self._frame_queue: queue.Queue[np.ndarray] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._short_reads = 0
        self._backoff = BACKOFF_INITIAL
        self.restarts = 0

    def _probe_resolution(self) -> None:
        """Fill ``self.width`` and ``self.height`` from stream metadata."""
        if self.width and self.height:
            return
        try:
            info = ffmpeg.probe(self.uri)
            stream = next(
                s for s in info.get("streams", []) if s.get("codec_type") == "video"
            )
            self.width = self.width or int(stream.get("width", 0) or 0)
            self.height = self.height or int(stream.get("height", 0) or 0)
        except Exception as exc:
            logger.debug("ffprobe failed: %s", exc)

    def open(self) -> None:
        self._start_proc()
        self._frame_queue = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()
        if self.width and self.height:
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True
            )
            self._reader_thread.start()

    def _start_proc(self) -> None:
        self._probe_resolution()
        transport = "tcp" if self.tcp else "udp"
        rw_timeout = (
            self.rw_timeout_usec
            if self.rw_timeout_usec is not None
            else int(os.getenv("RTSP_RW_TIMEOUT_USEC", "5000000"))
        )
        stimeout = (
            self.stimeout_usec
            if self.stimeout_usec is not None
            else int(os.getenv("RTSP_STIMEOUT_USEC", "5000000"))
        )
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-rtsp_transport",
            transport,
            "-rw_timeout",
            str(rw_timeout),
            "-stimeout",
            str(stimeout),
            "-i",
            self.uri,
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "32",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-",
        ]
        flags: list[str] = []
        env_flags = os.getenv("FFMPEG_EXTRA_FLAGS")
        if env_flags:
            flags.extend(shlex.split(env_flags))
        if self.extra_flags:
            flags.extend(self.extra_flags)
        if flags:
            insert_pos = cmd.index("-i")
            cmd[insert_pos:insert_pos] = flags
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**7,
        )
        self._stderr_buffer.clear()
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()
        log_capture_event(self.cam_id, "opened", backend="ffmpeg", uri=self.uri)
        self._short_reads = 0

    def read(self, timeout: float | None = None) -> np.ndarray:
        """Return the latest decoded frame from the internal queue."""
        if not self._frame_queue:
            raise FrameSourceError("NOT_OPEN")
        if not self.width or not self.height:
            self._log_stderr()
            logger.warning("ffmpeg stderr:\n%s", self.last_stderr)
            raise FrameSourceError("NO_VIDEO_STREAM")
        try:
            return self._frame_queue.get(timeout=timeout or self.latency_ms / 1000)
        except queue.Empty:
            self._log_stderr()
            logger.warning("ffmpeg stderr:\n%s", self.last_stderr)
            log_capture_event(self.cam_id, "read_timeout", backend="ffmpeg")
            raise FrameSourceError("READ_TIMEOUT")

    def _reader_loop(self) -> None:
        assert self.proc and self.proc.stdout
        expected = (self.width or 0) * (self.height or 0) * 3
        buf = bytearray(expected)
        mv = memoryview(buf)
        while self._stop_event and not self._stop_event.is_set():
            if not self.proc or not self.proc.stdout:
                self._restart_proc()
                continue
            try:
                read = self.proc.stdout.readinto(mv)
            except (EOFError, BrokenPipeError):
                self._restart_proc()
                continue
            except Exception:
                read = 0
            if read != expected:
                self._short_reads += 1
                if self._short_reads >= MAX_SHORT_READS:
                    self._restart_proc()
                continue
            frame = (
                np.frombuffer(mv, np.uint8).reshape((self.height, self.width, 3)).copy()
            )
            self._short_reads = 0
            self._backoff = BACKOFF_INITIAL
            if self._frame_queue and self._frame_queue.full():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
            if self._frame_queue:
                self._frame_queue.put(frame)

    def _restart_proc(self) -> None:
        self._stop_proc()
        self.restarts += 1
        time.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, BACKOFF_MAX)
        self._start_proc()
        if self._frame_queue:
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break

    def info(self) -> dict[str, int | float]:
        return {"w": self.width or 0, "h": self.height or 0, "fps": 0.0}

    def close(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=1)
            self._reader_thread = None
        self._stop_proc()
        if self._frame_queue:
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break
            self._frame_queue = None
        log_capture_event(self.cam_id, "closed", backend="ffmpeg")

    def _stop_proc(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            if self.proc.stdout:
                self.proc.stdout.close()
            if self.proc.stderr:
                self.proc.stderr.close()
            if self._stderr_thread:
                self._stderr_thread.join(timeout=1)
                self._stderr_thread = None
            self.proc = None

    def _drain_stderr(self) -> None:
        if not self.proc or not self.proc.stderr:
            return
        for line in self.proc.stderr:
            if not line:
                break
            self._stderr_buffer.append(line.decode("utf-8", "replace").rstrip())

    def _log_stderr(self) -> None:
        if self._stderr_buffer:
            logger.debug("ffmpeg stderr:\n%s", "\n".join(self._stderr_buffer))

    @property
    def last_stderr(self) -> str:
        return "\n".join(self._stderr_buffer)
