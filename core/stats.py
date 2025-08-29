"""Utilities for collecting and aggregating system statistics."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Dict

import redis
from loguru import logger

from config import ANOMALY_ITEMS, COUNT_GROUPS, config
from modules.events_store import RedisStore
from utils.logx import event, every, on_change


# gather_stats routine
def gather_stats(trackers: Dict[int, "PersonTracker"], r: redis.Redis, store: RedisStore) -> dict:
    """Collect aggregated counts and anomaly metrics."""
    now = int(time.time())
    start_day = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    group_counts = {}
    warned = False

    def _safe_count(labels, direction, start, end):
        nonlocal warned
        try:
            return store.count_events(labels, direction, start, end)
        except redis.RedisError as e:
            if not warned:
                logger.warning(
                    "count_events failed for labels={} direction={}: {}",
                    labels,
                    direction,
                    e,
                )
                warned = True
            return 0

    for g, labels in COUNT_GROUPS.items():
        in_c = _safe_count(labels, "in", start_day, now)
        out_c = _safe_count(labels, "out", start_day, now)
        group_counts[g] = {"in": in_c, "out": out_c, "current": in_c - out_c}
    total_in = sum(gv["in"] for gv in group_counts.values())
    total_out = sum(gv["out"] for gv in group_counts.values())
    count_keys = [f"{item}_count" for item in ANOMALY_ITEMS]
    count_vals = r.mget(count_keys)
    anomaly_counts = {
        item: int(val or 0) for item, val in zip(ANOMALY_ITEMS, count_vals, strict=False)
    }
    max_cap = config.get("max_capacity", 0)
    warn_lim = max_cap * config.get("warn_threshold", 0) / 100
    current = total_in - total_out
    status = "green" if current < warn_lim else "yellow" if current < max_cap else "red"
    last_24h = _safe_count(None, None, now - 86400, now)
    if every(300, "reports_last24h") or on_change("reports_last24h", last_24h):
        event("REPORT_ROWS", last24h=last_24h)
    return {
        "in_count": total_in,
        "out_count": total_out,
        "current": current,
        "max_capacity": max_cap,
        "status": status,
        "anomaly_counts": anomaly_counts,
        "group_counts": group_counts,
    }


# broadcast_stats routine
def broadcast_stats(
    trackers: Dict[int, "PersonTracker"], r: redis.Redis, store: RedisStore
) -> None:
    """Publish the latest stats if totals changed."""
    data = gather_stats(trackers, r, store)

    try:
        raw_totals = r.hgetall("stats_totals") or {}
    except redis.RedisError:
        raw_totals = {}

    existing: dict = {}
    for k, v in raw_totals.items():
        key = k.decode() if isinstance(k, (bytes, bytearray)) else k
        val = v.decode() if isinstance(v, (bytes, bytearray)) else v
        if key in {"anomaly_counts", "group_counts"}:
            try:
                existing[key] = json.loads(val)
            except Exception:  # pragma: no cover - corrupt data
                existing[key] = {}
        else:
            try:
                existing[key] = int(val)
            except (TypeError, ValueError):
                existing[key] = val

    if (
        data.get("in_count", 0) == existing.get("in_count", 0)
        and data.get("out_count", 0) == existing.get("out_count", 0)
        and data.get("current", 0) == existing.get("current", 0)
        and data.get("anomaly_counts", {}) == existing.get("anomaly_counts", {})
        and data.get("group_counts", {}) == existing.get("group_counts", {})
    ):
        return

    payload = json.dumps(data)
    r.publish("stats_updates", payload)
    try:
        r.hset(
            "stats_totals",
            mapping={
                "in_count": data["in_count"],
                "out_count": data["out_count"],
                "current": data["current"],
                "max_capacity": data["max_capacity"],
                "status": data["status"],
                "anomaly_counts": json.dumps(data["anomaly_counts"]),
                "group_counts": json.dumps(data["group_counts"]),
            },
        )
        r.xadd("stats_stream", {"data": payload}, maxlen=1, approximate=False)
    except redis.ResponseError:
        # stream might not exist or be trimmed incorrectly
        pass
