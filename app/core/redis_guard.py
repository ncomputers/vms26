"""Helpers to guard Redis operations with TTL enforcement and pipelines."""

from __future__ import annotations

from typing import Callable, Iterable

from loguru import logger
from redis import Redis
from redis.client import Pipeline
from redis.exceptions import RedisError

_missing_keys: set[str] = set()


def wrap_pipeline(r: Redis, ops: Iterable[Callable[[Pipeline], object]]) -> None:
    """Execute ``ops`` in a single Redis pipeline.

    Each callable in ``ops`` is invoked with the pipeline instance. The pipeline
    is executed once all operations have been enqueued to minimise round trips.
    """

    pipe = r.pipeline()
    for op in ops:
        op(pipe)
    pipe.execute()


def ensure_ttl(r: Redis, key: str, ttl: int = 15) -> None:
    """Ensure ``key`` has a positive TTL.

    If the key is missing (``TTL == -2``) a warning is logged only once. Keys
    without expiry (``TTL == -1``) are assigned ``ttl`` seconds.
    """

    try:
        remaining = r.ttl(key)
        if remaining < 0:
            if remaining == -2 and key not in _missing_keys:
                _missing_keys.add(key)
                logger.warning("ensure_ttl missing key {}", key)
            r.expire(key, ttl)
    except RedisError as exc:  # pragma: no cover - network failure
        logger.warning("ensure_ttl failed for {}: {}", key, exc)
