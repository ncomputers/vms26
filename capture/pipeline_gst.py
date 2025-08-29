from __future__ import annotations

"""GStreamer-based MJPEG capture pipeline."""

import logging
import queue
import threading
from typing import Optional

try:  # pragma: no cover - optional dependency
    import gi  # type: ignore

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib  # type: ignore

    Gst.init(None)
except Exception:  # pragma: no cover - Gst not installed
    Gst = None  # type: ignore
    GLib = None  # type: ignore

from .pipeline_base import PipelineBase

logger = logging.getLogger(__name__)


class Backoff:
    """Simple exponential backoff helper."""

    def __init__(self, base: float = 1.0, maximum: float = 10.0) -> None:
        self.base = base
        self.maximum = maximum
        self._n = 0

    def reset(self) -> None:
        self._n = 0

    def next(self) -> float:
        delay = min(self.base * (2 ** self._n), self.maximum)
        self._n += 1
        return delay


class GstPipeline(PipelineBase):
    """Pipeline that pulls JPEG frames using GStreamer.

    The pipeline is kept running once :meth:`start` is invoked. Frames are
    queued only when at least one client is connected, mirroring the behaviour
    of the FFmpeg pipeline implementation.
    """

    def __init__(self, uri: str, *, prefer_tcp: bool = True, latency_ms: int = 200) -> None:
        super().__init__(uri)
        self.prefer_tcp = prefer_tcp
        self.latency_ms = latency_ms
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pipeline: Optional[object] = None
        self._appsink: Optional[object] = None
        self._loop: Optional[GLib.MainLoop] = None
        self._backoff = Backoff()
        self._connected = False
        self.transport = "tcp" if self.prefer_tcp else "udp"

    # ------------------------------------------------------------------
    def _build_pipeline(self) -> str:
        proto = "tcp" if self.prefer_tcp else "udp"
        decode = "decodebin"
        return (
            f'rtspsrc location="{self.uri}" protocols={proto} latency={self.latency_ms} ! '
            f"{decode} ! jpegenc ! appsink name=appsink drop=true sync=false max-buffers=1 emit-signals=true"
        )

    # ------------------------------------------------------------------
    def _on_sample(self, sink) -> int:  # pragma: no cover - requires Gst
        sample = sink.emit("pull-sample")
        if not sample:
            return 0
        buf = sample.get_buffer()
        data = buf.extract_dup(0, buf.get_size())
        if not self._connected:
            logger.info("connected")
            self._connected = True
            self._backoff.reset()
        self._record_input_frame()
        if self.codec is None:
            caps = sample.get_caps().get_structure(0)
            if caps:
                self.width = caps.get_value("width")
                self.height = caps.get_value("height")
            self.codec = "JPEG"
            self.pipeline = self._build_pipeline()
        if self._clients > 0:
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                pass
        return 0

    def _on_bus(self, _bus, msg) -> None:  # pragma: no cover - requires Gst
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, _ = msg.parse_error()
            logger.error("gstreamer error: %s", err)
            if self._loop and self._loop.is_running():
                self._loop.quit()
        elif t == Gst.MessageType.EOS:
            logger.info("gstreamer eos")
            if self._loop and self._loop.is_running():
                self._loop.quit()

    # ------------------------------------------------------------------
    def _run(self) -> None:  # pragma: no cover - requires Gst
        while not self._stop_event.is_set():
            try:
                self.pipeline = self._build_pipeline()
                logger.info("connecting…")
                self._pipeline = Gst.parse_launch(self.pipeline)
                self._appsink = self._pipeline.get_by_name("appsink")
                self._appsink.connect("new-sample", self._on_sample)
                bus = self._pipeline.get_bus()
                bus.add_signal_watch()
                bus.connect("message", self._on_bus)
                self._loop = GLib.MainLoop()
                self._pipeline.set_state(Gst.State.PLAYING)
                self._loop.run()
            except Exception as exc:
                logger.error("gst pipeline failed: %s", exc)
            finally:
                if self._pipeline:
                    self._pipeline.set_state(Gst.State.NULL)
                self._pipeline = None
                self._appsink = None
                self._loop = None
                if self._stop_event.is_set():
                    break
                self.reconnect_count += 1
                delay = self._backoff.next()
                logger.info("reconnecting in %ds", int(delay))
                if self._stop_event.wait(delay):
                    break

    # ------------------------------------------------------------------
    def start(self) -> None:
        if Gst is None:
            raise RuntimeError("GSTREAMER_MISSING")
        self._on_start()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.quit()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None
        self._on_stop()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    def get_snapshot(self) -> bytes:
        if Gst is None:
            raise RuntimeError("GSTREAMER_MISSING")
        pipeline = self._build_pipeline()
        try:
            pipe = Gst.parse_launch(pipeline)
            sink = pipe.get_by_name("appsink")
            pipe.set_state(Gst.State.PLAYING)
            sample = sink.emit("pull-sample")
            pipe.set_state(Gst.State.NULL)
        except Exception as exc:  # pragma: no cover - best effort
            logger.error("snapshot failed: %s", exc)
            raise RuntimeError("SNAPSHOT_FAILED") from exc
        if not sample:
            raise RuntimeError("SNAPSHOT_FAILED")
        buf = sample.get_buffer()
        return buf.extract_dup(0, buf.get_size())

    # ------------------------------------------------------------------
    def frames(self):
        self._clients += 1
        logger.debug("client connected: total=%d", self._clients)
        try:
            while self._running:
                try:
                    frame = self._queue.get(timeout=0.5)
                except queue.Empty:
                    if self._stop_event.is_set():
                        break
                    continue
                self._out_count += 1
                yield frame
        finally:
            self._clients -= 1
            logger.debug("client disconnected: total=%d", self._clients)


__all__ = ["GstPipeline"]
