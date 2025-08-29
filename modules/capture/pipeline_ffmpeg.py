from __future__ import annotations

"""FFmpeg-based MJPEG pipeline."""

import logging
import queue
import subprocess
import threading
from typing import Iterator, List, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - base may live elsewhere
    from .pipeline_base import PipelineBase  # type: ignore
except Exception:  # pragma: no cover - fallback stub

    class PipelineBase:  # type: ignore[misc]
        def __init__(
            self,
            url: str,
            *,
            read_timeout_ms: int = 5000,
            prefer_tcp: bool = True,
            ffmpeg_binary: str = "ffmpeg",
        ) -> None:
            self.url = url
            self.read_timeout_ms = read_timeout_ms
            self.prefer_tcp = prefer_tcp
            self.ffmpeg_binary = ffmpeg_binary

        def frames(self) -> Iterator[bytes]:  # pragma: no cover - interface stub
            raise NotImplementedError

        def snapshot(self) -> bytes:  # pragma: no cover - interface stub
            raise NotImplementedError


class Backoff:
    """Simple exponential backoff helper."""

    def __init__(self, base: float = 1.0, maximum: float = 10.0) -> None:
        self.base = base
        self.maximum = maximum
        self._n = 0

    def reset(self) -> None:
        self._n = 0

    def next(self) -> float:
        delay = min(self.base * (2**self._n), self.maximum)
        self._n += 1
        return delay


class FfmpegPipeline(PipelineBase):
    """Pipeline providing MJPEG frames via FFmpeg."""

    def __init__(
        self,
        url: str,
        *,
        read_timeout_ms: int = 5000,
        prefer_tcp: bool = True,
        ffmpeg_binary: str = "ffmpeg",
        extra_flags: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            url, read_timeout_ms=read_timeout_ms, prefer_tcp=prefer_tcp, ffmpeg_binary=ffmpeg_binary
        )
        self.extra_flags = extra_flags or []
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=1)
        self._clients = 0
        self._clients_lock = threading.Lock()
        self._proc_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._backoff = Backoff()

    # ------------------------------------------------------------------
    def _build_cmd(self, snapshot: bool = False) -> List[str]:
        cmd = [self.ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-nostdin"]
        if self.prefer_tcp:
            cmd.extend(["-rtsp_transport", "tcp"])
        cmd.extend(
            [
                "-stimeout",
                str(self.read_timeout_ms * 1000),
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-max_delay",
                "500000",
                "-rtbufsize",
                "64M",
            ]
        )
        if self.extra_flags:
            cmd.extend(self.extra_flags)
        cmd.extend(["-i", self.url])
        if snapshot:
            cmd.extend(["-vframes", "1"])
        cmd.extend(["-f", "mjpeg", "pipe:1"])
        return cmd

    def _start_proc(self) -> None:
        with self._proc_lock:
            if self._proc:
                return
            logger.info("connecting…")
            self._proc = subprocess.Popen(
                self._build_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**7,
            )
            self._stop_event.clear()
            self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
            self._stderr_thread.start()
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

    def _stop_proc(self) -> None:
        with self._proc_lock:
            proc = self._proc
            self._proc = None
        if proc:
            try:
                proc.terminate()
            except Exception:  # pragma: no cover - best effort
                pass
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
        if self._stderr_thread and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=1)
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1)
        self._stderr_thread = None
        self._reader_thread = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _reader_loop(self) -> None:
        assert self._proc and self._proc.stdout
        buf = bytearray()
        connected = False
        while not self._stop_event.is_set():
            chunk = self._proc.stdout.read(4096)
            if not chunk:
                break
            buf.extend(chunk)
            while True:
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9", start + 2)
                if start != -1 and end != -1:
                    frame = bytes(buf[start : end + 2])
                    del buf[: end + 2]
                    if not connected:
                        logger.info("connected")
                        connected = True
                        self._backoff.reset()
                    if self._queue.full():
                        try:
                            self._queue.get_nowait()
                        except queue.Empty:
                            pass
                    try:
                        self._queue.put_nowait(frame)
                    except queue.Full:
                        pass
                else:
                    break
        self._restart_proc()

    def _restart_proc(self) -> None:
        self._stop_proc()
        if self._clients == 0 or self._stop_event.is_set():
            return
        delay = self._backoff.next()
        logger.info("reconnecting in %ds", int(delay))
        if not self._stop_event.wait(delay):
            self._start_proc()

    def _drain_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        for raw in self._proc.stderr:
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if "401" in line or "auth" in line.lower():
                logger.error("auth failed")
            elif "invalid data" in line.lower() or "codec" in line.lower():
                logger.error("invalid data/codec")
            logger.debug("ffmpeg: %s", line)

    # ------------------------------------------------------------------
    def frames(self) -> Iterator[bytes]:
        with self._clients_lock:
            self._clients += 1
            if self._clients == 1:
                self._start_proc()
        try:
            while True:
                if self._stop_event.is_set() and self._queue.empty():
                    break
                try:
                    yield self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
        finally:
            with self._clients_lock:
                self._clients -= 1
                if self._clients == 0:
                    self._stop_event.set()
                    self._stop_proc()

    def snapshot(self) -> bytes:
        proc = subprocess.run(
            self._build_cmd(snapshot=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            logger.error("snapshot failed: %s", proc.stderr.decode("utf-8", "replace"))
            raise RuntimeError("SNAPSHOT_FAILED")
        return proc.stdout


__all__ = ["FfmpegPipeline"]
