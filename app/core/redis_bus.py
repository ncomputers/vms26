"""Lightweight Redis message bus helpers."""

from __future__ import annotations

import os
from typing import Dict

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from .redis_guard import ensure_ttl, wrap_pipeline
from .redis_keys import CAM_STATE, EVENTS_STREAM

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Return a singleton Redis client using ``REDIS_URL``.

    The connection URL is resolved from the ``REDIS_URL`` environment variable
    and defaults to ``redis://127.0.0.1:6379/0``.
    """

    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        _redis_client = Redis.from_url(url, decode_responses=True)
    return _redis_client


def xadd_event(stream: str = EVENTS_STREAM, data: Dict | None = None) -> None:
    """Append ``data`` to the Redis ``stream``.

    Any errors are logged but otherwise ignored so event publishing does not
    interrupt application flow.
    """

    if data is None:
        data = {}
    if not data:
        logger.debug("xadd_event skipped for %s: empty data", stream)
        return
    try:
        get_redis().xadd(stream, data, maxlen=1000, approximate=True)
    except RedisError as exc:  # pragma: no cover - network failure
        logger.warning("xadd_event failed for {}: {}", stream, exc)


def set_cam_state(camera_id: int, state_dict: Dict, ttl: int = 15) -> None:
    """Store ``state_dict`` under the camera's state hash with a TTL."""

    key = CAM_STATE.format(id=camera_id)
    client: Redis | None = None
    try:
        client = get_redis()
        wrap_pipeline(
            client,
            [
                lambda p: p.hset(key, mapping=state_dict),
                lambda p: p.expire(key, ttl),
            ],
        )
        ensure_ttl(client, key, ttl)
    except RedisError as exc:  # pragma: no cover - network failure
        logger.warning("set_cam_state failed for {}: {}", key, exc)
    if client is None:
        logger.debug("Redis unavailable; skipped TTL refresh for {}", key)


__all__ = ["get_redis", "xadd_event", "set_cam_state"]
