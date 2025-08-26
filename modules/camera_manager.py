from __future__ import annotations

import asyncio
import time
from random import random
from typing import Callable, Dict, Iterable, List

import numpy as np
from modules.camera_factory import StreamUnavailable, open_capture

from loguru import logger
from app.core.utils import mtime

BACKOFF_BASE = 0.5
BACKOFF_MAX = 30.0
JITTER = 0.3
BREAKER_OPEN_SECS = 15.0

# latest frames shared across capture loops
LATEST_FRAMES: Dict[int, Dict[str, object]] = {}

# Types for injected functions
StartFn = Callable[[dict, dict, Dict[int, object], object], object]
StopFn = Callable[[int, Dict[int, object]], None]


class CameraManager:
    """Service layer for starting and restarting camera pipelines."""

    def __init__(
        self,
        cfg: dict,
        trackers: Dict[int, object],
        face_trackers: Dict[int, object],
        redis_client,
        cams_getter: Callable[[], Iterable[dict]],
        start_fn: StartFn,
        stop_fn: StopFn,
        start_face_fn: StartFn | None = None,
        stop_face_fn: StopFn | None = None,
    ) -> None:
        self.cfg = cfg
        self.trackers = trackers
        self.face_trackers = face_trackers
        self.redis = redis_client
        self._get_cams = cams_getter
        self.start_tracker_fn = start_fn
        self.stop_tracker_fn = stop_fn
        self.start_face_tracker_fn = start_face_fn
        self.stop_face_tracker_fn = stop_face_fn
        self._state: Dict[int, Dict[str, float | int | str]] = {}
        self._latest = LATEST_FRAMES

    def _get_state(self, cam_id: int) -> Dict[str, float | int | str]:
        return self._state.setdefault(
            cam_id,
            {
                "fail_count": 0,
                "next_retry_ts": 0.0,
                "breaker_state": "CLOSED",
                "opened_at": 0.0,
            },
        )

    def _publish_status(self, cam_id: int) -> None:
        st = self._state.get(cam_id)
        if not st or not self.redis:
            return
        try:
            self.redis.hset(
                f"cam:{cam_id}:status",
                mapping={
                    "state": st["breaker_state"],
                    "fail_count": st["fail_count"],
                    "next_retry": int(st["next_retry_ts"]),
                },
            )
        except Exception:
            logger.exception(f"[{cam_id}] failed publishing status")

    async def _attempt_start(self, cam: dict) -> None:
        cam_id = cam.get("id")
        st = self._get_state(cam_id)
        now = time.time()
        if st["breaker_state"] == "OPEN":
            if now - float(st["opened_at"]) < BREAKER_OPEN_SECS:
                self._publish_status(cam_id)
                return
            st["breaker_state"] = "HALF_OPEN"
        if now < float(st["next_retry_ts"]):
            self._publish_status(cam_id)
            return
        try:
            await self._start_tracker_background(cam)
        except Exception:
            st["fail_count"] = int(st.get("fail_count", 0)) + 1
            backoff = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** min(st["fail_count"], 6)))
            jittered = backoff * (1.0 - JITTER + random() * JITTER * 2)
            st["next_retry_ts"] = now + jittered
            if st["fail_count"] >= 3 and st["breaker_state"] == "CLOSED":
                st["breaker_state"] = "OPEN"
                st["opened_at"] = now
            self._publish_status(cam_id)
            raise
        else:
            st["fail_count"] = 0
            st["next_retry_ts"] = 0.0
            st["breaker_state"] = "CLOSED"
            st["opened_at"] = 0.0
            self._publish_status(cam_id)

    # internal helper
    def _find_cam(self, cam_id: int) -> dict | None:
        for cam in self._get_cams():
            if cam.get("id") == cam_id:
                return cam
        return None

    async def _start_tracker_background(self, cam: dict) -> None:
        """Launch tracker start in a background thread and update status."""
        start = asyncio.get_event_loop().time()
        try:
            tr = await asyncio.to_thread(
                self.start_tracker_fn, cam, self.cfg, self.trackers, self.redis
            )
            if self.start_face_tracker_fn and cam.get("face_recognition"):
                await asyncio.to_thread(
                    self.start_face_tracker_fn,
                    cam,
                    self.cfg,
                    self.face_trackers,
                    self.redis,
                )
            if self.redis:
                status = "online" if tr and getattr(tr, "online", False) else "offline"
                self.redis.hset(
                    f"camera:{cam.get('id')}:health", mapping={"status": status}
                )
                self.redis.hset(f"camera:{cam.get('id')}", "status", status)
        except Exception:
            logger.exception(f"[{cam.get('id')}] tracker start failed")
            if self.redis:
                self.redis.hset(
                    f"camera:{cam.get('id')}:health", mapping={"status": "offline"}
                )
                self.redis.hset(f"camera:{cam.get('id')}", "status", "offline")
            raise
        else:
            duration = asyncio.get_event_loop().time() - start
            if duration > 5.0:
                logger.warning(f"[{cam.get('id')}] start_tracker took {duration:.2f}s")

    async def start(self, camera_id: int) -> None:
        cam = self._find_cam(camera_id)
        if not cam:
            return
        flags = {
            "enabled": cam.get("enabled", True),
            "ppe": cam.get("ppe", False),
            "vms": cam.get("visitor_mgmt", False),
            "face": cam.get("face_recognition", False),
            "counting": any(
                t in cam.get("tasks", []) for t in ("in_count", "out_count")
            ),
        }
        logger.info(
            f"[camera:{camera_id}] start type={cam.get('type')} "
            f"transport={cam.get('rtsp_transport')} flags={flags}"
        )
        try:
            await self._attempt_start(cam)
        except Exception:
            logger.exception(f"[camera:{camera_id}] tracker start failed")
            raise

    async def restart(self, camera_id: int) -> None:
        cam = self._find_cam(camera_id)
        if not cam:
            return
        flags = {
            "enabled": cam.get("enabled", True),
            "ppe": cam.get("ppe", False),
            "vms": cam.get("visitor_mgmt", False),
            "face": cam.get("face_recognition", False),
            "counting": any(
                t in cam.get("tasks", []) for t in ("in_count", "out_count")
            ),
        }
        logger.info(
            f"[camera:{camera_id}] restart type={cam.get('type')} "
            f"transport={cam.get('rtsp_transport')} flags={flags}"
        )

        async def _do_restart() -> None:
            await asyncio.to_thread(self.stop_tracker_fn, camera_id, self.trackers)
            if self.stop_face_tracker_fn:
                await asyncio.to_thread(
                    self.stop_face_tracker_fn, camera_id, self.face_trackers
                )
            if cam.get("enabled", True) and self.cfg.get(
                "enable_person_tracking", True
            ):
                await self._attempt_start(cam)

        asyncio.create_task(_do_restart())

    async def refresh_flags(self, camera_id: int) -> None:
        async def _refresh() -> None:
            tr = self.trackers.get(camera_id)
            if tr:
                setattr(tr, "restart_capture", True)

        asyncio.create_task(_refresh())

    @staticmethod
    def _cap_frame(frame: np.ndarray) -> np.ndarray:
        """Downscale oversized frames for diagnostics."""
        h, w = frame.shape[:2]
        if h > 1080 or w > 1920:
            try:
                import cv2  # type: ignore

                scale = min(1920 / w, 1080 / h)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            except Exception:
                pass
        return frame

    async def snapshot(self, cam_id: int, timeout: float = 0.8):
        """Return a recent frame for ``cam_id``.

        Returns ``(ok, frame, detail)`` where ``frame`` is a BGR ndarray or
        ``None`` when unavailable. ``detail`` indicates whether the frame was
        served from the cache or via a probe capture.
        """

        info = self._latest.get(cam_id)
        now = mtime()
        if info and (now - float(info.get("ts", 0.0)) <= 2.0):
            bgr = info.get("bgr")
            if isinstance(bgr, np.ndarray):
                return True, self._cap_frame(bgr.copy()), "from_cache"

        cam = self._find_cam(cam_id)
        url = cam.get("url", "") if cam else ""
        try:
            cap, _ = await asyncio.to_thread(
                open_capture, url, cam_id, cam.get("type") if cam else None
            )
            try:
                res = await asyncio.to_thread(cap.read, timeout)
            finally:
                close = getattr(cap, "close", None)
                if callable(close):
                    await asyncio.to_thread(close)
                else:
                    release = getattr(cap, "release", None)
                    if callable(release):
                        await asyncio.to_thread(release)
            if isinstance(res, tuple):
                ok, frame = res
            else:
                ok, frame = True, res
            if ok and isinstance(frame, np.ndarray):
                return True, self._cap_frame(frame), "from_probe"
            return False, None, "no_frame"
        except StreamUnavailable as e:
            return False, None, f"unavailable:{e}"
        except Exception as e:
            return False, None, f"error:{e}"
