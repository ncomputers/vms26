"""Lightweight structured logging helpers used across the app.

Provides convenience wrappers around :mod:`loguru` so modules can emit
structured events that are also mirrored to Redis for consumption by the UI.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any, Dict

from loguru import logger
from redis.exceptions import RedisError

from .redis import get_sync_client
from .url import mask_credentials

# in-memory state for throttling helpers
_last_times: Dict[str, float] = {}
_last_values: Dict[str, Any] = {}


@lru_cache(maxsize=1)
def get_redis_client():
    """Return a cached Redis client."""
    return get_sync_client()


# required field map for known events
_REQUIRED: dict[str, list[str]] = {
    "capture_start": ["camera_id", "mode", "url"],
    "capture_stop": ["camera_id", "mode", "url"],
    "capture_error": ["camera_id", "mode", "url", "code", "rc", "ffmpeg_tail"],
    "capture_read_fail": ["camera_id", "mode", "url", "status", "error", "count"],
}


def _validate(event: str, fields: Dict[str, Any]) -> None:
    required = _REQUIRED.get(event)
    if not required:
        return
    missing = [k for k in required if k not in fields]
    if missing:
        raise KeyError(f"missing fields for {event}: {', '.join(missing)}")


def push_redis(payload: Dict[str, Any]) -> None:
    """Push *payload* to the Redis ``logs:events`` list."""

    try:
        client = get_redis_client()
    except RedisError as exc:
        logger.warning("push_redis init failed: {}", exc)
        get_redis_client.cache_clear()
        return
    try:
        data = json.dumps(payload)
    except (TypeError, ValueError) as exc:
        logger.warning("push_redis encode failed: {}", exc)
        return
    try:
        client.lpush("logs:events", data)
        client.ltrim("logs:events", 0, 1999)
    except RedisError as exc:
        logger.warning("push_redis redis error: {}", exc)
        get_redis_client.cache_clear()


def _log(level: str, event: str, **fields: Any) -> None:
    """Internal helper to emit a structured log and mirror it to Redis."""

    for key in ("url", "cmd", "pipeline", "pipeline_info"):
        if key in fields:
            fields[key] = mask_credentials(str(fields[key]))
    _validate(event, fields)
    payload: Dict[str, Any] = {
        "ts": time.time(),
        "level": level,
        "event": event,
        **fields,
    }
    logger.log(level.upper(), json.dumps(payload))
    push_redis(payload)


def event(event: str, **fields: Any) -> None:
    """Log an informational *event* with structured *fields*."""

    _log("info", event, **fields)


def warn(event: str, **fields: Any) -> None:
    """Log a warning *event*."""

    _log("warning", event, **fields)


def error(event: str, **fields: Any) -> None:
    """Log an error *event*."""

    _log("error", event, **fields)


def debug(event: str, **fields: Any) -> None:
    """Log a debug *event*."""

    _log("debug", event, **fields)


def every(seconds: float, key: str) -> bool:
    """Return ``True`` if ``seconds`` elapsed since last call with *key*.

    This is useful for rate-limiting noisy logs.
    """

    now = time.time()
    last = _last_times.get(key, 0)
    if now - last >= seconds:
        _last_times[key] = now
        return True
    return False


def log_throttled(fn, *args: Any, key: str, interval: float = 60, **kwargs: Any) -> None:
    """Invoke ``fn`` only if ``interval`` seconds elapsed for ``key``.

    This provides a convenient way to rate-limit noisy log messages.
    """

    if every(interval, key):
        fn(*args, **kwargs)


def on_change(key: str, value: Any) -> bool:
    """Return ``True`` when *value* differs from the previous call."""

    if _last_values.get(key) != value:
        _last_values[key] = value
        return True
    return False


__all__ = [
    "event",
    "warn",
    "error",
    "debug",
    "every",
    "on_change",
    "log_throttled",
    "push_redis",
]
