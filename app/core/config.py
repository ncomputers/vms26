from __future__ import annotations

"""Configuration helpers backed by Redis."""

import os
import threading
import time
from typing import Callable, Optional

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

import utils.redis as redis_utils
from config import load_config, set_config, config as _CONFIG

_CFG_VERSION_KEY = "CFG_VERSION"
_CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")


def bump_version(client: Optional[Redis] = None) -> int | None:
    """Increment the global configuration version."""
    client = client or redis_utils.get_sync_client()
    try:
        version = client.incr(_CFG_VERSION_KEY)
        logger.debug("Bumped config version to {}", version)
        return version
    except RedisError as e:  # pragma: no cover
        logger.warning("Failed to bump config version: {}", e)
        return None


def _reload(client: Redis) -> dict:
    cfg = load_config(_CONFIG_PATH, client)
    set_config(cfg)
    return _CONFIG


def watch_config(
    callback: Callable[[dict], None], client: Optional[Redis] = None
) -> threading.Thread:
    """Watch for configuration changes and invoke ``callback`` on update."""
    client = client or redis_utils.get_sync_client()

    def _worker() -> None:
        last = client.get(_CFG_VERSION_KEY)
        pubsub = None
        try:
            db = client.connection_pool.connection_kwargs.get("db", 0)
            channel = f"__keyspace@{db}__:{_CFG_VERSION_KEY}"
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel)
        except RedisError:
            pubsub = None

        while True:
            try:
                changed = False
                if pubsub is not None:
                    message = pubsub.get_message(timeout=2.0)
                    if message:
                        changed = True
                else:
                    current = client.get(_CFG_VERSION_KEY)
                    if current != last:
                        last = current
                        changed = True
                    time.sleep(2)

                if changed:
                    cfg = _reload(client)
                    try:
                        callback(cfg)
                    except Exception:
                        logger.exception("Config callback failed")
            except RedisError:
                logger.warning("Config watcher lost Redis connection; retrying")
                time.sleep(2)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


__all__ = ["bump_version", "watch_config", "_CONFIG"]
