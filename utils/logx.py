"""Lightweight structured logging helpers used across the app.

Provides convenience wrappers around :mod:`loguru` so modules can emit
structured events that are also mirrored to Redis for consumption by the UI.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from loguru import logger

from .redis import get_sync_client
from .url import mask_creds

# in-memory state for throttling helpers
_last_times: Dict[str, float] = {}
_last_values: Dict[str, Any] = {}
_redis_client = None

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
    """Push *payload* to the Redis ``logs:events`` list.

    The list is capped at 2000 entries to avoid unbounded growth. Errors are
    swallowed so logging never interferes with the main application flow.
    """

    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = get_sync_client()
        except Exception:
            _redis_client = False  # sentinel for failed init
    if not _redis_client:
        return
    try:
        data = json.dumps(payload)
        _redis_client.lpush("logs:events", data)
        _redis_client.ltrim("logs:events", 0, 1999)
    except Exception:
        pass


def _log(level: str, event: str, **fields: Any) -> None:
    """Internal helper to emit a structured log and mirror it to Redis."""

    for key in ("url", "cmd", "pipeline", "pipeline_info"):
        if key in fields:
            fields[key] = mask_creds(str(fields[key]))
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
    "push_redis",
]
