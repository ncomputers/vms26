from __future__ import annotations

"""Lightweight face tracking for attendance events."""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

try:  # optional heavy dependency
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

from core import events
from modules import face_db
from modules.model_registry import get_insightface
from modules.utils import SNAP_DIR
from utils.gpu import get_device


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """Return IoU between two ``ltrb`` boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity between vectors ``a`` and ``b``."""
    if not a.any() or not b.any():
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _sharpness(img: np.ndarray) -> float:
    """Return a crude sharpness metric in ``0..1`` range."""
    if img.size == 0:
        return 0.0
    if cv2 is None:  # pragma: no cover - tests patch deterministic values
        return float(np.var(img))
    lap = cv2.Laplacian(img, cv2.CV_64F)
    val = float(lap.var())
    # normalise to 0..1 assuming 0..1000 typical range
    return min(1.0, val / 1000.0)


def _frontalness(face: Any) -> float:
    """Return frontalness score from face object if available."""
    val = getattr(face, "frontalness", None)
    if val is None:
        return 1.0
    try:
        return float(val)
    except Exception:  # pragma: no cover - defensive
        return 1.0


def _crop_with_margin(frame: np.ndarray, bbox: Tuple[int, int, int, int], margin: float = 0.15) -> np.ndarray:
    """Return crop from ``frame`` with ``margin`` around ``bbox``."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    dw = int((x2 - x1) * margin)
    dh = int((y2 - y1) * margin)
    x1 = max(0, x1 - dw)
    y1 = max(0, y1 - dh)
    x2 = min(w, x2 + dw)
    y2 = min(h, y2 + dh)
    return frame[y1:y2, x1:x2]


# ---------------------------------------------------------------------------
# FaceTracker implementation
# ---------------------------------------------------------------------------


class FaceTracker:
    """Track faces and emit IN/OUT events."""

    def __init__(
        self,
        cam_id: int,
        cfg: dict,
        redis_client,
        line_orientation: str = "vertical",
        line_ratio: float = 0.5,
        reverse: bool = False,
    ) -> None:
        self.cam_id = cam_id
        self.cfg = cfg
        self.redis = redis_client
        self.line_orientation = line_orientation
        self.line_ratio = line_ratio
        self.reverse = reverse
        self.min_conf = cfg.get("min_face_conf", 0.60)
        self.min_size = cfg.get("min_face_size", 40)
        self.similarity_thresh = cfg.get("similarity_thresh", 0.35)
        self.count_cooldown = cfg.get("count_cooldown", 2.0)
        self.device = get_device(device=cfg.get("device", "auto"))
        self.device_type = getattr(self.device, "type", str(self.device))
        self.cpu_sample_every = cfg.get("cpu_sample_every", 3)
        self.iou_thresh = cfg.get("iou_thresh", 0.3)
        self.detector = None
        try:  # pragma: no cover - detector optional
            from modules.face_engine.detector import FaceDetector

            self.detector = FaceDetector()
        except Exception:
            self.detector = None
        try:
            self.model = get_insightface(cfg.get("visitor_model", "buffalo_l"))
        except Exception:
            self.model = None
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1
        self.frame_idx = 0
        self._counted: Dict[Tuple[int, str], float] = {}
        self.snap_dir = SNAP_DIR

    # ------------------------------------------------------------------
    def _match_track(
        self, bbox: Tuple[int, int, int, int], emb: np.ndarray, now: float
    ) -> int:
        best_id: Optional[int] = None
        best_score = -1.0
        for tid, t in self.tracks.items():
            iou = _iou(bbox, t["bbox"])
            cos = _cosine(emb, t["embedding_avg"])
            if iou >= self.iou_thresh and cos >= self.similarity_thresh:
                score = iou + cos
                if score > best_score:
                    best_score = score
                    best_id = tid
        if best_id is None:
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = {
                "bbox": bbox,
                "embedding_avg": emb,
                "prev_zone": None,
                "curr_zone": None,
                "best_q": 0.0,
                "best_img_ref": None,
                "first_seen": now,
                "last_seen": now,
                "seen_count": 0,
                "person_id": None,
                "name": None,
            }
            return tid
        return best_id

    # ------------------------------------------------------------------
    def _zone(self, bbox: Tuple[int, int, int, int], frame: np.ndarray) -> str:
        h, w = frame.shape[:2]
        line_pos = int((h if self.line_orientation == "horizontal" else w) * self.line_ratio)
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        if self.line_orientation == "horizontal":
            return "top" if cy < line_pos else "bottom"
        return "left" if cx < line_pos else "right"

    # ------------------------------------------------------------------
    def process_frame(self, frame: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], str]]:
        """Process ``frame`` and return overlay data."""
        self.frame_idx += 1
        if self.device_type == "cpu" and self.frame_idx % self.cpu_sample_every:
            return []
        detections: List[Tuple[int, int, int, int, float]] = []
        if self.detector:
            for det in self.detector.detect(frame):
                x1, y1, x2, y2 = det.bbox
                conf = float(det.det_score)
                if (
                    conf < self.min_conf
                    or x2 - x1 < self.min_size
                    or y2 - y1 < self.min_size
                ):
                    continue
                detections.append((x1, y1, x2, y2, conf))
        overlays: List[Tuple[Tuple[int, int, int, int], str]] = []
        now = time.time()
        for x1, y1, x2, y2, conf in detections:
            crop = _crop_with_margin(frame, (x1, y1, x2, y2))
            emb = np.zeros(512, dtype=np.float32)
            name = None
            person_id = None
            score = 0.0
            face_obj = None
            if self.model is not None:
                try:
                    faces = self.model.get(crop)
                except Exception:  # pragma: no cover - model failure
                    faces = []
                if faces:
                    face_obj = faces[0]
                    emb = np.array(getattr(face_obj, "embedding", emb), dtype=np.float32)
                    name = getattr(face_obj, "name", None)
                    person_id = getattr(face_obj, "person_id", None)
                    score = float(getattr(face_obj, "match_score", 0.0))
            tid = self._match_track((x1, y1, x2, y2), emb, now)
            tr = self.tracks[tid]
            # update embedding average
            count = tr["seen_count"] + 1
            tr["embedding_avg"] = (
                tr["embedding_avg"] * tr["seen_count"] + emb
            ) / count
            tr["seen_count"] = count
            tr["bbox"] = (x1, y1, x2, y2)
            tr["last_seen"] = now
            if tr.get("person_id") is None and person_id is not None:
                tr["person_id"] = person_id
                tr["name"] = name
            zone = self._zone((x1, y1, x2, y2), frame)
            prev_zone = tr.get("curr_zone")
            tr["prev_zone"] = prev_zone
            tr["curr_zone"] = zone
            q = 0.5 * conf + 0.3 * _sharpness(crop) + 0.2 * _frontalness(face_obj)
            if q > tr.get("best_q", 0.0) or tr.get("best_img_ref") is None:
                fname = f"{int(now)}_{self.cam_id}_{tid}.jpg"
                tr["best_img_ref"] = str(self.snap_dir / fname)
                tr["best_q"] = q
            if tr.get("person_id") is None and "temp_uuid" not in tr:
                tr["temp_uuid"] = uuid.uuid4().hex
            overlays.append(((x1, y1, x2, y2), tr.get("name") or "Unknown"))
            if prev_zone and prev_zone != zone:
                entered = (
                    (prev_zone == "left" and zone == "right")
                    if self.line_orientation == "vertical"
                    else (prev_zone == "top" and zone == "bottom")
                )
                direction = "in" if entered else "out"
                if self.reverse:
                    direction = "out" if entered else "in"
                key = (tid, direction)
                last = self._counted.get(key)
                if not last or now - last >= self.count_cooldown:
                    payload = {
                        "ts": int(now),
                        "event": events.FACE_IN if direction == "in" else events.FACE_OUT,
                        "camera_id": self.cam_id,
                        "tid": tid,
                        "dir": direction,
                        "score": score,
                        "img_ref": tr.get("best_img_ref"),
                    }
                    if tr.get("person_id"):
                        payload["person_id"] = tr["person_id"]
                    else:
                        uuid_ = tr.get("temp_uuid")
                        payload["temp_uuid"] = uuid_
                        try:
                            face_db.upsert_temp_face(
                                uuid_,
                                {
                                    "embed": tr["embedding_avg"].tolist(),
                                    "best_q": tr["best_q"],
                                    "img_ref": tr.get("best_img_ref"),
                                    "camera_id": self.cam_id,
                                    "first_seen": tr["first_seen"],
                                    "last_seen": now,
                                },
                            )
                        except Exception:
                            logger.exception("temp face upsert failed")
                    try:
                        self.redis.xadd("attendance:events", payload)
                        key_stats = f"stats:face_{direction}:{self.cam_id}"
                        self.redis.incr(key_stats)
                    except Exception:  # pragma: no cover - redis failure
                        logger.exception("Failed to write attendance event")
                    self._counted[key] = now
        # prune old tracks
        expired = [
            tid
            for tid, t in self.tracks.items()
            if now - t["last_seen"] > 10
        ]
        for tid in expired:
            self.tracks.pop(tid, None)
        return overlays


# ---------------------------------------------------------------------------
# Convenience start/stop helpers
# ---------------------------------------------------------------------------

def start_face_tracker(
    cam: dict, cfg: dict, trackers: Dict[int, FaceTracker], r
) -> FaceTracker | None:
    if not cam.get("face_recognition"):
        return None
    tr = FaceTracker(
        cam["id"],
        cfg,
        r,
        line_orientation=cam.get("line_orientation", "vertical"),
        line_ratio=cam.get("line_ratio", 0.5),
        reverse=cam.get("reverse", False),
    )
    trackers[cam["id"]] = tr
    return tr


def stop_face_tracker(cam_id: int, trackers: Dict[int, FaceTracker]) -> None:
    trackers.pop(cam_id, None)
