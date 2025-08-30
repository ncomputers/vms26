from __future__ import annotations

"""Redis-backed store for tracking events."""

import json
from typing import Iterable

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

# Basic label mapping for vehicle classes
VEHICLE_LABELS = {
    "car",
    "truck",
    "bus",
    "motorcycle",
    "motorbike",
    "bicycle",
    "auto",
    "van",
}


class RedisStore:
    """Lightweight wrapper around Redis sorted sets for event data."""

    def __init__(self, client: Redis):
        self.r = client

    # persist_event routine
    def persist_event(
        self,
        *,
        ts_utc: int,
        ts_local: str,
        camera_id: int,
        camera_name: str,
        track_id: int,
        direction: str,
        label: str,
        image_path: str | None,
        thumb_path: str | None,
    ) -> None:
        """Store an event entry in Redis sorted sets."""
        entry = {
            "ts": ts_utc,
            "ts_local": ts_local,
            "cam_id": camera_id,
            "camera_name": camera_name,
            "track_id": track_id,
            "direction": direction,
            "label": label,
            "image_path": image_path,
            "thumb_path": thumb_path,
        }
        raw = json.dumps(entry)
        try:
            self.r.zadd("events", {raw: ts_utc})
            if label == "person":
                self.r.zadd("person_logs", {raw: ts_utc})
            elif label == "vehicle" or label in VEHICLE_LABELS:
                self.r.zadd("vehicle_logs", {raw: ts_utc})
        except RedisError as exc:
            logger.warning("failed to persist event: {}", exc)

    # fetch_events routine
    def fetch_events(self, start_ts: int, end_ts: int, *, label: str | None = None) -> list[str]:
        """Return raw event entries from Redis within the time range."""
        key = "events"
        if label == "person":
            key = "person_logs"
        elif label == "vehicle":
            key = "vehicle_logs"
        return self.r.zrangebyscore(key, start_ts, end_ts)

    # count_events routine
    def count_events(
        self,
        labels: Iterable[str] | None,
        direction: str | None,
        start_ts: int,
        end_ts: int,
    ) -> int:
        """Count events in Redis matching optional filters."""
        keys: set[str] = set()
        if not labels:
            keys = {"person_logs", "vehicle_logs"}
        else:
            for lbl in labels:
                if lbl == "person":
                    keys.add("person_logs")
                elif lbl == "vehicle" or lbl in VEHICLE_LABELS:
                    keys.add("vehicle_logs")
                else:
                    keys.add("events")
        count = 0
        for key in keys:
            entries = self.r.zrangebyscore(key, start_ts, end_ts)
            for raw in entries:
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if labels and data.get("label") not in labels:
                    continue
                if direction and data.get("direction") != direction:
                    continue
                count += 1
        return count
