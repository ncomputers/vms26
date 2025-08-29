"""Streaming helpers for the tracker package."""

from __future__ import annotations

import queue
import time
from typing import TYPE_CHECKING

try:  # OpenCV may be missing in lightweight test environments
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

try:  # optional heavy dependency
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - torch is optional in tests
    torch = None

from app.core.perf import PERF
from core.events import CAPTURE_ERROR, CAPTURE_READ_FAIL, CAPTURE_START, CAPTURE_STOP
from modules.camera_factory import StreamUnavailable, open_capture
from modules.profiler import register_thread
from utils.api_errors import stream_error_message
from utils.logx import error as log_error
from utils.logx import event as log_event
from utils.logx import warn as log_warn

if TYPE_CHECKING:
    from .manager import PersonTracker


def _shutdown_capture(cap) -> None:
    """Release capture resources.

    Prefer ``close()`` when available for backends that expose it and fall
    back to OpenCV's ``release()`` method otherwise. Some capture wrappers need
    ``close()`` to flush pipelines, while ``release()`` is only implemented by
    ``cv2.VideoCapture``.
    """
    if cap is None:
        return
    close = getattr(cap, "close", None)
    if callable(close):
        close()
    else:
        release = getattr(cap, "release", None)
        if callable(release):
            release()


class CaptureWorker:
    """Background worker that reads frames and feeds a queue."""

    def __init__(self, tracker: PersonTracker) -> None:
        self.tracker = tracker

    def run(self) -> None:
        t = self.tracker
        register_thread(f"Tracker-{t.cam_id}-capture")
        cap = None
        log_event(
            CAPTURE_START,
            camera_id=t.cam_id,
            mode=t.stream_mode,
            url=t.src,
        )
        base_skip = int(t.cfg.get("frame_skip", 0))
        skip = max(1, base_skip)
        frame_idx = 0
        prev_gray = None
        while t.running:
            try:
                dev = getattr(t, "device", None)
                if isinstance(dev, str):
                    use_gpu = dev.startswith("cuda")
                else:
                    use_gpu = getattr(dev, "type", "") == "cuda"

                cap, t.rtsp_transport = open_capture(
                    t.cfg,
                    t.src,
                    t.cam_id,
                    t.src_type,
                    t.resolution,
                    t.rtsp_transport,
                    use_gpu,
                    capture_buffer=t.cfg.get("capture_buffer", 3),
                    backend_priority=t.cfg.get("backend_priority"),
                    ffmpeg_flags=t.cfg.get("ffmpeg_flags"),
                    pipeline=t.cfg.get("pipeline"),
                    profile=t.cfg.get("profile"),
                    ffmpeg_reconnect_delay=t.cfg.get("ffmpeg_reconnect_delay"),
                    ready_frames=t.cfg.get("ready_frames"),
                    ready_duration=t.cfg.get("ready_duration"),
                    ready_timeout=t.cfg.get("ready_timeout"),
                    for_display=t.viewers > 0,
                    reverse=t.cfg.get("reverse", False),
                    orientation=t.cfg.get("orientation", "vertical"),
                    pass_through=t.stream_mode == "lite",
                )
                cmd = getattr(cap, "pipeline", None) or getattr(cap, "cmd", None)
                if isinstance(cmd, list):
                    cmd = " ".join(cmd)
                t.pipeline_info = cmd or ""
                t.capture_backend = cap.__class__.__name__
                t.stream_status = "ok"
                t.stream_error = ""
                t.online = True
                log_event(
                    CAPTURE_START,
                    camera_id=t.cam_id,
                    mode=t.stream_mode,
                    url=t.src,
                    backend=t.capture_backend,
                    cmd=t.pipeline_info,
                )
                fail_count = 0
                max_failures = t.cfg.get("max_read_failures", 30)
                while t.running:
                    if t.restart_capture:
                        t.restart_capture = False
                        fail_count = 0
                        break
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        fail_count += 1
                        status = getattr(cap, "last_status", "")
                        err = getattr(cap, "last_error", "")
                        log_warn(
                            CAPTURE_READ_FAIL,
                            camera_id=t.cam_id,
                            mode=t.stream_mode,
                            url=t.src,
                            status=status,
                            error=err,
                            count=fail_count,
                        )
                        if status and status != "ok":
                            msg = stream_error_message(status) or err
                            log_error(
                                CAPTURE_ERROR,
                                camera_id=t.cam_id,
                                mode=t.stream_mode,
                                url=t.src,
                                code="status",
                                status=status,
                                error=msg,
                                cmd=t.pipeline_info,
                                rc=getattr(cap, "rc", 0),
                                ffmpeg_tail="\n".join(getattr(cap, "_stderr_buffer", [])),
                            )
                            t.stream_status = status
                            t.stream_error = msg
                            break
                        if fail_count > max_failures:
                            log_warn(
                                CAPTURE_READ_FAIL,
                                camera_id=t.cam_id,
                                mode=t.stream_mode,
                                url=t.src,
                                status=status,
                                error=err,
                                count=fail_count,
                                reason="too_many_failures",
                            )
                            break
                        time.sleep(0.1)
                        continue
                    fail_count = 0
                    frame_idx += 1
                    if not t.first_frame_ok and frame is not None:
                        h, w = frame.shape[:2]
                        if h > 0 and w > 0:
                            t.first_frame_ok = True
                    if getattr(t, "adaptive_skip", False):
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        if prev_gray is not None:
                            diff = cv2.absdiff(gray, prev_gray)
                            motion = float(diff.mean())
                            if motion < 2.0:
                                skip = min(skip + 1, 10)
                            else:
                                skip = max(1, skip - 1)
                        prev_gray = gray
                    if skip > 1 and (frame_idx - 1) % skip:
                        continue
                    PERF[t.cam_id].on_input()
                    if t.frame_queue.full():
                        try:
                            t.frame_queue.get_nowait()
                            PERF[t.cam_id].on_drop()
                            t.dropped_frames = getattr(t, "dropped_frames", 0) + 1
                            if hasattr(t, "debug_stats"):
                                t.debug_stats["dropped_frames"] = t.dropped_frames
                            PERF[t.cam_id].qdepth = t.frame_queue.qsize()
                        except queue.Empty:
                            pass
                    t.raw_frame = frame
                    if t.frame_callback:
                        t.frame_callback(t.cam_id, frame.copy())
                    if (
                        use_gpu
                        and torch is not None
                        and not torch.cuda.is_available()
                        and not getattr(t, "_warned_no_cuda", False)
                    ):
                        log_warn(
                            CAPTURE_ERROR,
                            camera_id=t.cam_id,
                            mode=t.stream_mode,
                            url=t.src,
                            code="cuda_fallback",
                            rc=0,
                            ffmpeg_tail="",
                        )
                        t._warned_no_cuda = True
                    try:
                        t.frame_queue.put(frame, timeout=1)
                        PERF[t.cam_id].qdepth = t.frame_queue.qsize()
                    except queue.Full:
                        PERF[t.cam_id].on_drop()
                        PERF[t.cam_id].qdepth = t.frame_queue.qsize()
                    now = time.time()
                    t.debug_stats["last_capture_ts"] = now
                    t.debug_stats["last_frame_ts"] = now
                    ft = getattr(t, "frame_times", None)
                    if ft is not None:
                        ft.append(now)
                        if len(ft) >= 2:
                            diffs = [ft[i] - ft[i - 1] for i in range(1, len(ft))]
                            avg = sum(diffs) / len(diffs)
                            if avg > 0:
                                t.debug_stats["capture_fps"] = 1.0 / avg
                            t.debug_stats["jitter_ms"] = (
                                (max(diffs) - min(diffs)) * 1000 if diffs else 0.0
                            )
                    qs = getattr(t, "queue_stats", None)
                    if qs is not None:
                        qs["det_in"] = t.frame_queue.qsize()
                        t.debug_stats["det_in"] = qs["det_in"]
                    else:
                        t.debug_stats["det_in"] = t.frame_queue.qsize()
                    t.debug_stats["packet_loss"] = getattr(cap, "network_error_count", 0)
                    t.debug_stats["restarts"] = getattr(cap, "restarts", 0)
                    if t.cfg.get("once"):
                        t.running = False
                        break
                _shutdown_capture(cap)
                t.online = False
            except StreamUnavailable as e:
                status = "timeout" if "timeout" in str(e).lower() else "error"
                msg = stream_error_message(status) or str(e)
                log_error(
                    CAPTURE_ERROR,
                    camera_id=t.cam_id,
                    mode=t.stream_mode,
                    url=t.src,
                    code="unavailable",
                    status=status,
                    error=msg,
                    rc=getattr(cap, "rc", 0),
                    ffmpeg_tail="",
                )
                t.stream_status = status
                t.stream_error = msg
                t.running = False
                t.online = False
            except Exception as e:
                status = getattr(cap, "last_status", "") if cap else ""
                err = getattr(cap, "last_error", "") if cap else ""
                cmd = getattr(cap, "pipeline", None) or getattr(cap, "cmd", None)
                if isinstance(cmd, list):
                    cmd = " ".join(cmd)
                msg = stream_error_message(status) or err or str(e)
                log_error(
                    CAPTURE_ERROR,
                    camera_id=t.cam_id,
                    mode=t.stream_mode,
                    url=t.src,
                    code="exception",
                    status=status,
                    error=msg,
                    cmd=cmd,
                    rc=getattr(cap, "rc", 0),
                    ffmpeg_tail="\n".join(getattr(cap, "_stderr_buffer", [])),
                )
                t.stream_status = status or "error"
                t.stream_error = msg
                t.running = False
                t.online = False
                if cap:
                    _shutdown_capture(cap)
        log_event(
            CAPTURE_STOP,
            camera_id=t.cam_id,
            mode=t.stream_mode,
            url=t.src,
            status=getattr(cap, "last_status", ""),
            error=getattr(cap, "last_error", ""),
            cmd=t.pipeline_info,
        )


__all__ = ["CaptureWorker"]
