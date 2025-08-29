"""High level tracker manager coordinating detection, tracking and streaming."""

from __future__ import annotations

import json
import queue
import time
from collections import deque
from collections.abc import Iterable
from datetime import date
from typing import Any

# ruff: noqa


try:  # OpenCV is optional in certain environments
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore
import numpy as np
import psutil
from loguru import logger
from redis.exceptions import RedisError

from app.core.perf import PERF
from app.core.redis_guard import ensure_ttl, wrap_pipeline
from config import ANOMALY_ITEMS, config
from modules.profiler import register_thread
from utils import logx
from utils.gpu import get_device
from utils.redis import EVENTS_STREAM, get_sync_client, xadd_event
from utils.time import format_ts
from utils.url import get_stream_type

from ..duplicate_filter import DuplicateFilter
from ..utils import SNAP_DIR, lock
from .detector import Detector
from .stream import CaptureWorker
from .tracker import Tracker

try:  # optional heavy dependency
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - torch is optional in tests
    torch = None

try:  # optional heavy dependency
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None


TRACK_CLASSES = {
    "person",
    "car",
    "truck",
    "bus",
    "motorcycle",
    "bicycle",
    "auto",
    "van",
}

VEHICLE_CLASSES = {
    "car",
    "truck",
    "bus",
    "motorcycle",
    "motorbike",
    "bicycle",
    "auto",
    "van",
}


def group_of(cls: str) -> str:
    """Return high-level group for a detection label."""

    if cls == "person":
        return "person"
    if cls in VEHICLE_CLASSES:
        return "vehicle"
    return "other"


def side(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    eps: float = 2.0,
) -> int:
    """Return which side of ``ab`` the ``point`` lies on.

    Uses the sign of the 2D cross product. ``1`` indicates the point is to the
    left of the directed line from ``a`` to ``b``; ``-1`` indicates the right
    side. ``0`` is returned when the absolute cross product is below ``eps``,
    treating the point as on the line.
    """

    ax, ay = a
    bx, by = b
    px, py = point
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) < eps:
        return 0
    return 1 if cross > 0 else -1


def point_line_distance(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Return the perpendicular distance from ``point`` to line ``ab``.

    The distance is computed using the magnitude of the 2D cross product
    divided by the length of the line segment.
    """

    px, py = point
    ax, ay = a
    bx, by = b
    denom = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    if denom == 0.0:
        return 0.0
    return abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / denom


def infer_batch(
    tracker: "PersonTracker", batch: list[np.ndarray], frames: list[np.ndarray]
) -> list[Any]:
    """Run batched detection and enqueue frame/detection pairs."""
    try:
        start = time.time()
        dets_batch = tracker.detector.detect_batch(batch, list(TRACK_CLASSES))
        elapsed = (time.time() - start) * 1000.0
        per_frame = elapsed / max(len(batch), 1)
        for frm, dets in zip(frames, dets_batch):
            PERF[tracker.cam_id].on_det_ms(per_frame)
            if tracker.det_queue.full():
                try:
                    tracker.det_queue.get_nowait()
                    PERF[tracker.cam_id].on_drop()
                except queue.Empty:  # pragma: no cover - queue emptied
                    pass
            try:
                tracker.det_queue.put((frm, dets), timeout=1)
            except queue.Full:  # pragma: no cover - queue full
                PERF[tracker.cam_id].on_drop()
        return dets_batch
    except Exception:
        logger.exception(f"[{tracker.cam_id}] infer error")
        return []


def process_frame(tracker: "PersonTracker", frame: np.ndarray, detections: list[Any]) -> None:
    """Process a single frame with associated detections."""
    purge = getattr(tracker, "_purge_counted", None)
    if purge:
        purge()
    updated = False
    if getattr(tracker, "tracker", None):
        if not detections:
            now = time.time()
            interval = (
                0.0
                if not getattr(tracker, "detector_fps", 0)
                else 1.0 / float(tracker.detector_fps)
            )
            last_ts = getattr(tracker, "_last_det_ts", 0.0)
            run_det = interval == 0.0 or now - last_ts >= interval
            if run_det:
                if getattr(tracker, "detector", None):
                    start_det = time.time()
                    detections = tracker.detector.detect(frame, list(TRACK_CLASSES))
                    PERF[tracker.cam_id].on_det_ms((time.time() - start_det) * 1000.0)
                else:  # pragma: no cover - exercised in unit tests
                    from modules.tracker import detector as det

                    start_det = time.time()
                    detections = det.profile_predict(None, "person", frame, device=tracker.device)
                    PERF[tracker.cam_id].on_det_ms((time.time() - start_det) * 1000.0)
                tracker._last_det_ts = now
                tracker.last_detections = detections

        filtered = []
        for det in detections or []:
            bbox = score = label = None
            if isinstance(det, tuple):
                if len(det) == 3:
                    bbox, score, label = det
            else:
                label = getattr(det, "label", None)
                bbox = getattr(det, "bbox", None)
                score = getattr(det, "score", None)
                if isinstance(det, dict):
                    label = det.get("label", label)
                    bbox = det.get("bbox", bbox)
                    score = det.get("score", score)
            if label not in TRACK_CLASSES:
                continue
            if bbox is None or score is None:
                continue
            try:
                arr = np.asarray(bbox, dtype=float)
                sc = float(score)
            except (TypeError, ValueError):
                continue
            if arr.size != 4 or not np.isfinite(arr).all() or not np.isfinite(sc):
                continue
            filtered.append((tuple(arr.tolist()), sc, label))
        try:
            try:
                start_trk = time.time()
                ds_tracks = tracker.tracker.update_tracks(
                    filtered,
                    frame=frame,
                    aux=[getattr(tracker, "_counted", {})],
                )
                PERF[tracker.cam_id].on_trk_ms((time.time() - start_trk) * 1000.0)
            except TypeError:
                start_trk = time.time()
                ds_tracks = tracker.tracker.update_tracks(filtered, frame=frame)
                PERF[tracker.cam_id].on_trk_ms((time.time() - start_trk) * 1000.0)
        except ValueError:
            logger.exception(f"[{tracker.cam_id}] tracker update error")
            return
        ds_tracks = sorted(ds_tracks, key=lambda tr: getattr(tr, "det_class", "") != "person")
        new_tracks = {}
        h, w = frame.shape[:2]
        tracker.last_frame_shape = (h, w)
        line_pos = int((h if tracker.line_orientation == "horizontal" else w) * tracker.line_ratio)
        now = time.time()
        for trk in ds_tracks:
            if not trk.is_confirmed():
                continue
            tid = trk.track_id
            l_raw, t_raw, r_raw, b_raw = trk.to_ltrb()
            scale = getattr(tracker, "scale", 1.0)
            pad_x = getattr(tracker, "pad_x", 0)
            pad_y = getattr(tracker, "pad_y", 0)
            left = int((l_raw - pad_x) / scale)
            top = int((t_raw - pad_y) / scale)
            right = int((r_raw - pad_x) / scale)
            bottom = int((b_raw - pad_y) / scale)
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            if tracker.line_orientation == "horizontal":
                line_start = (0.0, float(line_pos))
                line_end = (float(w - 1), float(line_pos))
            else:
                line_start = (float(line_pos), 0.0)
                line_end = (float(line_pos), float(h - 1))
            prev = tracker.tracks.get(tid, {})
            raw_side = side((cx, cy), line_start, line_end, getattr(tracker, "side_eps", 2.0))
            cur_side_sign = raw_side
            prev_side_sign = prev.get("last_side")

            if tracker.line_orientation == "horizontal":
                zone = (
                    "top"
                    if cur_side_sign < 0
                    else "bottom" if cur_side_sign > 0 else prev.get("zone", "top")
                )
            else:
                zone = (
                    "left"
                    if cur_side_sign > 0
                    else "right" if cur_side_sign < 0 else prev.get("zone", "left")
                )
            label = getattr(trk, "det_class", prev.get("label", ""))
            group = group_of(label)
            conf = float(getattr(trk, "det_conf", 0.0) or 0.0)
            trail = prev.get("trail", [])
            trail.append((cx, cy))
            if len(trail) > 30:
                trail = trail[-30:]
            if getattr(tracker, "ppe_classes", []) and group in tracker.ppe_classes:
                associated = False
                for pid, pdata in new_tracks.items():
                    if pdata.get("group") == "person":
                        pl, pt, pr, pb = pdata["bbox"]
                        if left >= pl and top >= pt and right <= pr and bottom <= pb:
                            pdata.setdefault("ppe", []).append(group)
                            associated = True
                            break
                if associated:
                    continue
            new_tracks[tid] = {
                "bbox": (left, top, right, bottom),
                "zone": zone,
                "last_side": cur_side_sign,
                "trail": trail,
                "group": group,
                "label": label,
                "conf": conf,
                "center": (cx, cy),
            }
            state_lines = tracker.track_states.get(tid, {})
            state = state_lines.get(
                0,
                {
                    "last_side": cur_side_sign,
                    "counted_in": False,
                    "counted_out": False,
                    "last_seen": now,
                },
            )
            prev_side_sign = state.get("last_side", 0)
            direction = None
            age = getattr(trk, "age", 0)
            if conf >= 0.5 and age >= 2 and group != "other":
                if prev_side_sign != cur_side_sign and prev_side_sign != 0 and cur_side_sign != 0:
                    if cur_side_sign > 0 and not state.get("counted_in"):
                        tracker.in_counts[group] = tracker.in_counts.get(group, 0) + 1
                        state["counted_in"] = True
                        direction = "in"
                    elif cur_side_sign < 0 and not state.get("counted_out"):
                        tracker.out_counts[group] = tracker.out_counts.get(group, 0) + 1
                        state["counted_out"] = True
                        direction = "out"
                    if direction:
                        logx.event(
                            "COUNT_EMIT",
                            camera_id=tracker.cam_id,
                            group=group,
                            dir=direction,
                            track_id=tid,
                            cls=label,
                        )
                        updated = True
                        ts = int(now)
                        path = None
                        try:
                            crop = frame[top:bottom, left:right]
                            fname = f"{ts}_{tracker.cam_id}_{tid}.jpg"
                            img_path = tracker.snap_dir / fname
                            cv2.imwrite(str(img_path), crop)
                            path = str(img_path)
                        except Exception:
                            path = None
                        entry = {
                            "ts": ts,
                            "cam_id": tracker.cam_id,
                            "track_id": tid,
                            "line_id": 0,
                        }

                    try:
                        key = f"cam:{tracker.cam_id}:state"
                        pipe = tracker.redis.pipeline()
                        pipe.hset(
                            key,
                            mapping={
                                "fps_in": tracker.debug_stats.get("capture_fps", 0.0),
                                "fps_out": tracker.debug_stats.get("process_fps", 0.0),
                                "last_error": tracker.stream_error,
                            },
                        )
                        ensure_ttl(tracker.redis, key, 15)
                    except Exception:
                        logger.exception("failed to update cam state")
            state["last_side"] = cur_side_sign
            state["last_seen"] = now
            state_lines[0] = state
            tracker.track_states[tid] = state_lines
        now = time.time()
        cutoff = now - tracker.track_state_ttl
        for t_id in list(tracker.track_states.keys()):
            lines = tracker.track_states[t_id]
            for lid in list(lines.keys()):
                if lines[lid].get("last_seen", 0) < cutoff:
                    del lines[lid]
            if not lines:
                del tracker.track_states[t_id]
        tracker.tracks = new_tracks
        if {"in_count", "out_count"} & set(getattr(tracker, "tasks", ["in_count", "out_count"])):
            tracker.in_count = sum(tracker.in_counts.values())
            tracker.out_count = sum(tracker.out_counts.values())
        if updated and tracker.update_callback:
            try:
                tracker.update_callback()
            except Exception:
                logger.exception("update_callback failed")
    debug_flags = {
        name: getattr(tracker, name, False)
        for name in (
            "show_lines",
            "show_ids",
            "show_track_lines",
            "show_counts",
        )
    }
    processed = frame.copy() if any(debug_flags.values()) else frame
    if any(debug_flags.values()):
        counts = {
            k: int(v)
            for k, v in {
                "entered": tracker.in_count,
                "exited": tracker.out_count,
                "inside": tracker.in_count - tracker.out_count,
            }.items()
        }
        counts["inside"] = max(0, counts["inside"])
        with lock:
            tracker.output_frame = processed

    else:
        with lock:
            tracker.output_frame = None
    if tracker.out_queue.full():
        try:
            tracker.out_queue.get_nowait()
            PERF[tracker.cam_id].on_drop()
        except queue.Empty:
            pass
    try:
        tracker.out_queue.put(processed, timeout=1)
        PERF[tracker.cam_id].on_output()
    except queue.Full:
        PERF[tracker.cam_id].on_drop()


class InferWorker:
    """Background worker handling preprocessing and batched inference."""

    def __init__(self, tracker: "PersonTracker") -> None:
        self.tracker = tracker

    def run(self) -> None:
        t = self.tracker
        register_thread(f"Tracker-{t.cam_id}-infer")
        logger.info(f"[proc:{t.cam_id}] infer loop started")
        batch: list[np.ndarray] = []
        frames: list[np.ndarray] = []
        batch_size = getattr(t, "batch_size", 1)
        while t.running or not t.frame_queue.empty() or batch:
            try:
                frame = t.frame_queue.get(timeout=1)
                frames.append(frame)
                batch.append(frame)
                if len(batch) < batch_size:
                    continue
            except queue.Empty:
                if not batch:
                    continue
            infer_batch(t, batch, frames)
            batch = []
            frames = []
        logger.info(f"[proc:{t.cam_id}] infer loop stopped")


class PostProcessWorker:
    """Consume detections, run tracking, and publish frames."""

    def __init__(self, tracker: "PersonTracker") -> None:
        self.tracker = tracker

    def run(self) -> None:
        t = self.tracker
        register_thread(f"Tracker-{t.cam_id}-post")
        logger.info(f"[proc:{t.cam_id}] post-process loop started")
        try:
            while t.running or not t.det_queue.empty():
                try:
                    frame, detections = t.det_queue.get(timeout=1)
                except queue.Empty:
                    continue
                try:
                    process_frame(t, frame, detections)
                except Exception:
                    logger.exception(f"[proc:{t.cam_id}] process error")
                t.debug_stats["last_process_ts"] = time.time()
        except Exception:
            logger.exception(f"[proc:{t.cam_id}] post-process fatal error")
        finally:
            logger.info(f"[proc:{t.cam_id}] post-process loop stopped")
            if getattr(t, "renderer", None):
                t.renderer.close()


# ProcessingWorker class encapsulates a simplified processing loop
class ProcessingWorker:
    """Process frames by running detection (optionally throttled) and tracking."""

    def __init__(self, tracker: "PersonTracker") -> None:
        self.tracker = tracker

    def run(self) -> None:
        t = self.tracker
        while t.running or not t.frame_queue.empty():
            try:
                frame = t.frame_queue.get(timeout=1)
                PERF[t.cam_id].qdepth = t.frame_queue.qsize()
            except queue.Empty:
                continue
            detections = []
            now = time.time()
            interval = 0.0 if not getattr(t, "detector_fps", 0) else 1.0 / float(t.detector_fps)
            last_ts = getattr(t, "_last_det_ts", 0.0)
            run_det = interval == 0.0 or now - last_ts >= interval
            if run_det and getattr(t, "detector", None):
                start_det = time.time()
                detections = t.detector.detect(frame, list(TRACK_CLASSES))
                PERF[t.cam_id].on_det_ms((time.time() - start_det) * 1000.0)
                t._last_det_ts = now
            try:
                start_trk = time.time()
                t.tracker.update_tracks(
                    detections,
                    frame=frame,
                    aux=[getattr(t, "_counted", {})],
                )
                PERF[t.cam_id].on_trk_ms((time.time() - start_trk) * 1000.0)
            except TypeError:
                start_trk = time.time()
                t.tracker.update_tracks(detections, frame=frame)
                PERF[t.cam_id].on_trk_ms((time.time() - start_trk) * 1000.0)
            PERF[t.cam_id].on_output()


# UniqueFaceCounter class encapsulates uniquefacecounter behavior
class UniqueFaceCounter:
    """Filter to count unique faces using embeddings."""

    # __init__ routine
    def __init__(self, similarity: float = 0.6, max_age: int = 30) -> None:
        self.records: deque[tuple[np.ndarray, float]] = deque()
        self.similarity = similarity
        self.max_age = max_age

    # _purge routine
    def _purge(self, now: float) -> None:
        while self.records and now - self.records[0][1] > self.max_age:
            self.records.popleft()

    # is_new routine
    def is_new(self, emb: np.ndarray) -> bool:
        now = time.time()
        self._purge(now)
        for e, _ in self.records:
            sim = float(np.dot(e, emb) / (np.linalg.norm(e) * np.linalg.norm(emb)))
            if sim >= self.similarity:
                return False
        self.records.append((emb, now))
        return True


# _iou routine
def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Return intersection-over-union for two boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0, inter_x2 - inter_x1)
    ih = max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / float(area_a + area_b - inter)


# LightweightFaceTracker class encapsulates a minimal IoU tracker
class LightweightFaceTracker:
    """Very small tracker assigning IDs using IoU matching."""

    def __init__(self, iou_thresh: float = 0.5) -> None:
        self.next_id = 0
        self.tracks: dict[int, tuple[int, int, int, int]] = {}
        self.iou_thresh = iou_thresh

    # update routine
    def update(
        self, detections: list[tuple[int, int, int, int, float]]
    ) -> list[tuple[int, tuple[int, int, int, int], float]]:
        """Update tracker with ``detections`` and return active tracks."""
        assigned: dict[int, bool] = {}
        results: list[tuple[int, tuple[int, int, int, int], float]] = []
        for x1, y1, x2, y2, conf in detections:
            best_id = None
            best_iou = 0.0
            for tid, bbox in self.tracks.items():
                iou = _iou(bbox, (x1, y1, x2, y2))
                if iou > best_iou and iou >= self.iou_thresh:
                    best_iou = iou
                    best_id = tid
            if best_id is None:
                best_id = self.next_id
                self.next_id += 1
            self.tracks[best_id] = (x1, y1, x2, y2)
            results.append((best_id, (x1, y1, x2, y2), conf))
            assigned[best_id] = True
        self.tracks = {tid: bbox for tid, bbox in self.tracks.items() if tid in assigned}
        return results


# PersonTracker class encapsulates persontracker behavior
class PersonTracker:
    """Tracks entry and exit counts using YOLOv8 and DeepSORT."""

    # __init__ routine
    def __init__(
        self,
        cam_id: int,
        src: str,
        classes: list[str],
        cfg: dict,
        tasks: list[str] | None = None,
        src_type: str | None = None,
        line_orientation: str | None = None,
        reverse: bool = False,
        resolution: str = "original",
        rtsp_transport: str = "tcp",
        update_callback=None,
        frame_callback=None,
    ):
        self.cfg = cfg
        for k, v in cfg.items():
            setattr(self, k, v)
        self.load_durations: dict[str, float] = {}
        self.pipeline = cfg.get("pipeline", "")
        self.cam_id = cam_id
        self.src = src
        self.src_type = src_type or cfg.get("type") or get_stream_type(src)
        self.classes = classes
        self.tasks = tasks or ["in_count", "out_count"]
        self.count_classes = cfg.get("count_classes", [])
        self.ppe_classes = cfg.get("ppe_classes", [])
        self.alert_anomalies = cfg.get("alert_anomalies", [])
        self.line_orientation = line_orientation or cfg.get("line_orientation", "vertical")
        self.reverse = reverse
        self.resolution = resolution
        self.rtsp_transport = rtsp_transport
        self.stream_mode = cfg.get("stream_mode", "gstreamer")
        self.ppe_conf_thresh = cfg.get("ppe_conf_thresh", 0.5)
        self.detect_helmet_color = cfg.get("detect_helmet_color", False)
        self.track_misc = cfg.get("track_misc", True)
        self.show_lines = cfg.get("show_lines", True)
        self.show_ids = cfg.get("show_ids", True)
        self.show_track_lines = cfg.get("show_track_lines", False)
        self.show_counts = cfg.get("show_counts", False)
        self.preview_scale = cfg.get("preview_scale", 1.0)
        self.detector_fps = cfg.get("detector_fps", 10)
        self.adaptive_skip = cfg.get("adaptive_skip", False)

        # Distance from counting line required to register a crossing. Uses
        # ``point_line_distance`` to add hysteresis around the line.
        self.cross_hysteresis = cfg.get("cross_hysteresis", 15)

        # Letterbox parameters used to convert model coordinates back to the
        # original frame. ``scale`` is the resize factor applied before
        # padding, while ``pad_x`` and ``pad_y`` are the added margins.
        self.pad_x = 0
        self.pad_y = 0
        self.scale = 1.0

        # Epsilon used by the side-of-line test; points producing a cross
        # product magnitude below this threshold are treated as on the line.
        self.side_eps = cfg.get("side_eps", 2.0)

        # Per-track line-crossing state storing last side and counted flags
        self.track_states: dict[int, dict[int, dict[str, Any]]] = {}
        self.track_state_ttl = 120.0

        # Allow adjusting the maximum age for DeepSort tracks so IDs persist
        self.track_max_age = cfg.get("track_max_age", 10)

        self.debug_logs = cfg.get("debug_logs", False)
        self.duplicate_filter_enabled = cfg.get("duplicate_filter_enabled", False)
        self.duplicate_filter_threshold = cfg.get("duplicate_filter_threshold", 0.1)
        self.duplicate_bypass_seconds = cfg.get("duplicate_bypass_seconds", 2)
        self.max_retry = cfg.get("max_retry", 5)
        self.update_callback = update_callback
        self.frame_callback = frame_callback
        self.online = False
        self.restart_capture = False
        self.first_frame_ok = False

        self.renderer = None
        self.output_frame = None

        self.dup_filter = (
            DuplicateFilter(self.duplicate_filter_threshold, self.duplicate_bypass_seconds)
            if self.duplicate_filter_enabled
            else None
        )
        # Resolve device; "auto" prefers GPU and falls back to CPU with warning.
        self.device = get_device(device=cfg.get("device"))
        logger.info(f"Loading person model {self.person_model} on {self.device.type}")
        if self.device.type == "cuda":
            logger.info(f"\U0001f9e0 CUDA Enabled: {torch.cuda.get_device_name(0)}")

        def log_mem(note: str) -> None:
            mem = psutil.virtual_memory()
            logger.debug(f"{note}: RAM available {mem.available / (1024**3):.2f} GB")
            if getattr(self.device, "type", "") == "cuda" and torch:
                free, _ = torch.cuda.mem_get_info(self.device)
                logger.debug(f"{note}: GPU available {free / (1024**3):.2f} GB")

        log_mem("Before loading person model")
        try:
            from ..model_registry import get_yolo

            start = time.perf_counter()
            self.model_person = get_yolo(self.person_model, self.device)
            self.load_durations["person_model"] = time.perf_counter() - start
            logger.info(
                "Person model loaded in {:.2f}s",
                self.load_durations["person_model"],
            )
            logx.event(
                "MODEL_LOADED",
                camera_id=self.cam_id,
                model="person",
                load_ms=int(self.load_durations["person_model"] * 1000),
                backend=str(self.device),
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"Failed to load person model: {e}. Disable this feature or use smaller weights.",
            ) from e
        self.detector = Detector(self.model_person, self.device)
        self.batch_size = max(2, min(int(cfg.get("batch_size", 2)), 4))
        qsize = cfg.get("queue_size", 10)
        self.frame_queue = queue.Queue(maxsize=qsize)
        self.det_queue = queue.Queue(maxsize=qsize)
        self.out_queue = queue.Queue(maxsize=qsize)
        log_mem("Before loading plate model")
        try:
            start = time.perf_counter()
            self.model_plate = get_yolo(
                cfg.get("plate_model", "license_plate_detector.pt"), self.device
            )
            self.load_durations["plate_model"] = time.perf_counter() - start
            logger.info(
                "Plate model loaded in {:.2f}s",
                self.load_durations["plate_model"],
            )
            logx.event(
                "MODEL_LOADED",
                camera_id=self.cam_id,
                model="plate",
                load_ms=int(self.load_durations["plate_model"] * 1000),
                backend=str(self.device),
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"Failed to load plate model: {e}. Disable this feature or use smaller weights.",
            ) from e
        self.email_cfg = cfg.get("email", {})
        if getattr(self.device, "type", "") == "cuda" and torch:
            torch.backends.cudnn.benchmark = True
        self.use_gpu_embedder = getattr(self.device, "type", "") == "cuda"
        log_mem("Before initializing DeepSort")
        try:
            start = time.perf_counter()
            self.tracker = Tracker(self.use_gpu_embedder, max_age=self.track_max_age)
            self.load_durations["tracker"] = time.perf_counter() - start
            logger.info(
                "DeepSort initialized in {:.2f}s",
                self.load_durations["tracker"],
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"Failed to initialize DeepSort: {e}. Disable this feature or use smaller weights.",
            ) from e
        self.tracks = {}
        self._counted: dict[tuple[int, str], float] = {}
        self.count_cooldown = cfg.get("count_cooldown", 2)
        try:
            self.redis = get_sync_client(self.redis_url)
        except (RedisError, OSError) as e:
            logger.error(f"[{self.cam_id}] Redis connection failed: {e}")
            raise

        key_prefix = f"person_tracker:cam:{self.cam_id}"
        self.key_in = f"{key_prefix}:in"
        self.key_out = f"{key_prefix}:out"
        self.key_date = f"{key_prefix}:date"
        # ``track_objects`` accepts raw labels or alias names defined in
        # ``GROUP_ALIASES``.
        groups = cfg.get("track_objects", ["person", "vehicle"])
        if isinstance(groups, str) or not isinstance(groups, Iterable):
            groups = [groups]
        else:
            groups = list(groups)
        self.groups = groups
        self.in_counts = {}
        self.out_counts = {}
        keys_in = [f"{self.key_in}:{g}" for g in self.groups]
        keys_out = [f"{self.key_out}:{g}" for g in self.groups]
        vals = self.redis.mget(keys_in + keys_out)
        split = len(self.groups)
        for idx, g in enumerate(self.groups):
            self.in_counts[g] = int(vals[idx] or 0)
            self.out_counts[g] = int(vals[idx + split] or 0)
        self.in_count = sum(self.in_counts.values())
        self.out_count = sum(self.out_counts.values())
        stored_date = self.redis.get(self.key_date)
        self.prev_date = date.fromisoformat(stored_date) if stored_date else date.today()
        init_data = {self.key_date: self.prev_date.isoformat()}
        for g in self.groups:
            init_data[f"{self.key_in}:{g}"] = self.in_counts[g]
            init_data[f"{self.key_out}:{g}"] = self.out_counts[g]
        self.redis.mset(init_data)
        today = date.today().isoformat()
        date_keys = [f"{item}_date" for item in ANOMALY_ITEMS]
        date_vals = self.redis.mget(date_keys)
        anomaly_init: dict[str, Any] = {}
        for item, d_raw in zip(ANOMALY_ITEMS, date_vals):
            d = date.fromisoformat(d_raw) if d_raw else self.prev_date
            if d.isoformat() != today:
                anomaly_init[f"{item}_count"] = 0
                anomaly_init[f"{item}_date"] = today
        if anomaly_init:
            self.redis.mset(anomaly_init)
        self.snap_dir = SNAP_DIR
        self.raw_frame = None
        self.output_frame = None
        # Parameters for the downscaled/throttled preview stream
        self.preview_downscale = cfg.get("preview_downscale", 2)
        self._last_preview_ts = 0.0
        self.viewers = 0
        self.running = True
        self.capture_backend = None
        self.pipeline_info = ""
        self.stream_status = ""
        self.stream_error = ""
        self.log_interval = cfg.get("log_interval", 30)
        self._log_count = 0
        # Stats for debugging
        self.debug_stats = {
            "capture_fps": 0.0,
            "process_fps": 0.0,
            "queue": 0,
            "last_capture_ts": None,
            "last_process_ts": None,
            "restarts": 0,
            "last_frame_ts": None,
            "jitter_ms": 0.0,
            "dropped_frames": 0,
            "det_in": 0,
            "ppe_in": 0,
        }
        self.frame_times: deque[float] = deque(maxlen=30)
        self.dropped_frames = 0
        self.queue_stats: dict[str, int] = {"det_in": 0, "ppe_in": 0}
        # Timestamp of the last debug restart
        self.debug_restart_ts: float | None = None

        # Workers
        self.capture_worker = CaptureWorker(self)
        self.infer_worker = InferWorker(self)
        self.post_worker = PostProcessWorker(self)

    @staticmethod
    # _clean_label routine
    def _clean_label(name: str) -> str:
        """Normalize a label to lowercase with underscores."""
        return name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")

    # _log_process_interval routine
    def _log_process_interval(self, delta: float) -> None:
        """Log processing interval every N frames to avoid log spam."""
        self._log_count += 1
        if self._log_count % self.log_interval == 0:
            logger.debug(f"[{self.cam_id}] process interval={delta:.3f}s")

    def _purge_counted(self, now: float | None = None) -> None:
        if not hasattr(self, "_counted"):
            self._counted = {}
        if not hasattr(self, "count_cooldown"):
            self.count_cooldown = 2
        now = now or time.time()
        cutoff = now - self.count_cooldown
        self._counted = {k: ts for k, ts in self._counted.items() if ts >= cutoff}

    # update_cfg routine
    def update_cfg(self, cfg: dict):
        if "device" in cfg and torch is not None:
            # Normalize device configuration; "auto" selects GPU when available.
            cfg["device"] = get_device(device=cfg["device"])

        for k, v in cfg.items():
            setattr(self, k, v)
        # update object classes if provided
        if "object_classes" in cfg:
            self.classes = cfg["object_classes"]
        if "count_classes" in cfg:
            self.count_classes = cfg["count_classes"]
        if "ppe_classes" in cfg:
            self.ppe_classes = cfg["ppe_classes"]
        if "tasks" in cfg:
            self.tasks = cfg["tasks"]
            if not isinstance(self.tasks, list):
                self.tasks = ["in_count", "out_count"]
        if "type" in cfg:
            self.src_type = cfg["type"]
        if "alert_anomalies" in cfg:
            self.alert_anomalies = cfg["alert_anomalies"]
        if "line_orientation" in cfg:
            self.line_orientation = cfg["line_orientation"]
        if "reverse" in cfg:
            self.reverse = bool(cfg["reverse"])
        if "resolution" in cfg:
            self.resolution = cfg["resolution"]
        if "stream_mode" in cfg:
            self.stream_mode = cfg["stream_mode"]
        if "ppe_conf_thresh" in cfg:
            self.ppe_conf_thresh = cfg["ppe_conf_thresh"]
        if "detect_helmet_color" in cfg:
            self.detect_helmet_color = cfg["detect_helmet_color"]
        if "track_misc" in cfg:
            self.track_misc = cfg["track_misc"]
        if "show_lines" in cfg:
            self.show_lines = cfg["show_lines"]
        if "show_ids" in cfg:
            self.show_ids = cfg["show_ids"]
        if "show_track_lines" in cfg:
            self.show_track_lines = cfg["show_track_lines"]
        if "show_counts" in cfg:
            self.show_counts = cfg["show_counts"]
        if "detector_fps" in cfg:
            self.detector_fps = cfg["detector_fps"]
        if "adaptive_skip" in cfg:
            self.adaptive_skip = cfg["adaptive_skip"]
        if "debug_logs" in cfg:
            self.debug_logs = cfg["debug_logs"]
        if "duplicate_filter_enabled" in cfg:
            self.duplicate_filter_enabled = cfg["duplicate_filter_enabled"]
            self.dup_filter = (
                DuplicateFilter(self.duplicate_filter_threshold, self.duplicate_bypass_seconds)
                if self.duplicate_filter_enabled
                else None
            )
        if "duplicate_filter_threshold" in cfg:
            self.duplicate_filter_threshold = cfg["duplicate_filter_threshold"]
            if self.dup_filter:
                self.dup_filter.threshold = self.duplicate_filter_threshold
        if "duplicate_bypass_seconds" in cfg:
            self.duplicate_bypass_seconds = cfg["duplicate_bypass_seconds"]
            if self.dup_filter:
                self.dup_filter.bypass_seconds = self.duplicate_bypass_seconds
        from ..model_registry import get_yolo

        if "person_model" in cfg and cfg["person_model"] != getattr(self, "person_model", None):
            self.person_model = cfg["person_model"]
            self.model_person = get_yolo(self.person_model, self.device)
        if "plate_model" in cfg and cfg["plate_model"] != getattr(self, "plate_model", None):
            self.plate_model = cfg["plate_model"]
            self.model_plate = get_yolo(self.plate_model, self.device)
        if "email" in cfg:
            self.email_cfg = cfg["email"]
        if "rtsp_transport" in cfg:
            self.rtsp_transport = cfg["rtsp_transport"]

        if "track_objects" in cfg:
            new_groups = cfg["track_objects"]
            missing = [g for g in new_groups if g not in self.in_counts]
            if missing:
                m_keys_in = [f"{self.key_in}:{g}" for g in missing]
                m_keys_out = [f"{self.key_out}:{g}" for g in missing]
                vals = self.redis.mget(m_keys_in + m_keys_out)
                split = len(missing)
                for idx, g in enumerate(missing):
                    self.in_counts[g] = int(vals[idx] or 0)
                    self.out_counts[g] = int(vals[idx + split] or 0)
            for g in list(self.in_counts.keys()):
                if g not in new_groups:
                    self.in_counts.pop(g, None)
                    self.out_counts.pop(g, None)
                    self.redis.delete(f"{self.key_in}:{g}", f"{self.key_out}:{g}")
            self.groups = new_groups
            self.in_count = sum(self.in_counts.values())
            self.out_count = sum(self.out_counts.values())

    # apply_debug_pipeline routine
    def apply_debug_pipeline(self, pipeline: str | None = None, **params: dict) -> None:
        """Merge debug parameters into current config and restart capture."""
        changed = False
        if pipeline is not None and pipeline != self.cfg.get("pipeline"):
            self.cfg["pipeline"] = pipeline
            self.pipeline_info = pipeline
            self.pipeline = pipeline
            changed = True
        for k, v in params.items():
            if k == "url":
                if v != self.src:
                    self.src = v
                    changed = True
            elif k == "type":
                if v != self.src_type:
                    self.src_type = v
                    changed = True
            elif k == "resolution":
                if v != self.resolution:
                    self.resolution = v
                    self.cfg["resolution"] = v
                    changed = True
            elif k in {
                "rtsp_transport",
                "stream_mode",
                "ffmpeg_flags",
                "backend_priority",
            }:
                cur = getattr(self, k, self.cfg.get(k))
                if cur != v:
                    setattr(self, k, v)
                    self.cfg[k] = v
                    changed = True
            elif k == "pipeline":
                if v != self.cfg.get("pipeline"):
                    self.cfg["pipeline"] = v
                    self.pipeline_info = v
                    self.pipeline = v
                    changed = True
            else:
                if self.cfg.get(k) != v:
                    self.cfg[k] = v
                    changed = True
        if changed:
            self.restart_capture = True
            self.debug_restart_ts = time.time()

    # get_debug_stats routine
    def get_debug_stats(self) -> dict:
        """Return copy of current debug statistics."""
        return dict(self.debug_stats)

    def get_queue_stats(self) -> dict[str, int]:
        """Return current queue lengths."""
        return dict(self.queue_stats)

    # _append_runtime_debug routine
    def _append_runtime_debug(self, message: str) -> None:
        """Append runtime capture errors to Redis for diagnostics."""
        if not self.redis:
            return
        key = f"camera_debug:{self.cam_id}"
        try:
            raw = self.redis.get(key)
            data = json.loads(raw) if raw else {}
            runtime = data.setdefault("runtime", [])
            runtime.append(
                {
                    "ts": int(time.time()),
                    "backend": getattr(self, "capture_backend", ""),
                    "message": message,
                }
            )
            # keep only last 50 entries
            if len(runtime) > 50:
                data["runtime"] = runtime[-50:]
            self.redis.set(key, json.dumps(data))
        except Exception:
            pass

    # capture_loop routine
    def capture_loop(self):
        """Delegate to the capture worker."""
        self.capture_worker.run()

    # infer_loop routine
    def infer_loop(self):
        """Delegate to the inference worker."""
        self.infer_worker.run()

    # post_process_loop routine
    def post_process_loop(self):
        """Delegate to the post-process worker."""
        self.post_worker.run()
