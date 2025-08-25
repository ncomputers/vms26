from __future__ import annotations

"""Service for starting and restarting camera trackers."""

import asyncio
import time
from random import random

from loguru import logger

from core.tracker_manager import start_tracker, stop_tracker

START_TRACKER_WARN_AFTER = 5.0

# reconnect tuning
BACKOFF_BASE = 0.5
BACKOFF_MAX = 30.0
JITTER = 0.3
BREAKER_OPEN_SECS = 15.0


class CameraManager:
    """Manage tracker lifecycle for cameras."""

    def __init__(self, cfg: dict, trackers: dict, redis_client):
        self.cfg = cfg
        self.trackers = trackers
        self.redis = redis_client
        self._state: dict[int, dict[str, float | int | str]] = {}

    def _get_state(self, cam_id: int) -> dict[str, float | int | str]:
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

    async def start(self, cam: dict) -> None:
        """Start tracking for ``cam`` using reconnect safeguards."""
        start = time.perf_counter()
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
            await asyncio.to_thread(
                start_tracker, cam, self.cfg, self.trackers, self.redis
            )
            self.redis.hset(f"camera:{cam_id}", "status", "online")
        except Exception:
            logger.exception(f"[{cam_id}] tracker start failed")
            st["fail_count"] = int(st.get("fail_count", 0)) + 1
            backoff = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** min(st["fail_count"], 6)))
            jittered = backoff * (1.0 - JITTER + random() * JITTER * 2)
            st["next_retry_ts"] = now + jittered
            if st["fail_count"] >= 3 and st["breaker_state"] == "CLOSED":
                st["breaker_state"] = "OPEN"
                st["opened_at"] = now
            self._publish_status(cam_id)
            try:
                self.redis.hset(f"camera:{cam_id}", "status", "offline")
            except Exception:
                logger.exception(f"[{cam_id}] failed setting offline status")
        else:
            duration = time.perf_counter() - start
            if duration > START_TRACKER_WARN_AFTER:
                logger.warning(f"[{cam_id}] start_tracker took {duration:.2f}s")
            st["fail_count"] = 0
            st["next_retry_ts"] = 0.0
            st["breaker_state"] = "CLOSED"
            st["opened_at"] = 0.0
            self._publish_status(cam_id)

    async def restart(self, cam: dict) -> None:
        """Restart tracker for ``cam``."""
        cam_id = cam.get("id")
        await asyncio.to_thread(stop_tracker, cam_id, self.trackers)
        await self.start(cam)

    async def refresh_flags(self, cam: dict) -> None:
        """Placeholder to refresh flags for ``cam`` without restart."""
        cam_id = cam.get("id")
        status = "online" if cam_id in self.trackers else "offline"
        self.redis.hset(f"camera:{cam_id}", "status", status)
