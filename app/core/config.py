"""Application configuration loader and watcher."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger
from pydantic_settings import BaseSettings
from redis import Redis, RedisError

import utils.redis as redis_utils
from config import config as _CONFIG
from config import set_config

from .redis_keys import CFG_VERSION


class Config(BaseSettings):
    """Pydantic settings for application configuration."""

    features: dict[str, Any] = {}
    ui: dict[str, Any] = {}
    thresholds: dict[str, Any] = {}
    cameras: list[dict[str, Any]] = []
    target_fps: int = 15
    jpeg_quality: int = 80


def load_config(path: str = "./config.json") -> Config:
    """Load configuration from *path*."""

    cfg_path = Path(path)
    data: dict[str, Any] = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in %s; using defaults", cfg_path)
            data = {}
    cfg = Config.model_validate(data)
    logger.info("Loaded configuration with %d cameras", len(cfg.cameras))
    return cfg


_CONFIG: Optional[Config] = None


def get_config() -> Config:
    """Return a shared :class:`Config` instance."""

    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def watch_config(client: Redis, callback: Callable[[Config], None]) -> threading.Thread:
    """Watch ``CFG_VERSION`` in Redis and invoke ``callback`` on changes."""

    key = CFG_VERSION

    def _worker() -> None:
        last = client.get(key)
        pubsub = None
        try:
            db = client.connection_pool.connection_kwargs.get("db", 0)
            channel = f"__keyspace@{db}__:{key}"
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
                    current = client.get(key)
                    if current != last:
                        last = current
                        changed = True
                    time.sleep(2)

                if changed:
                    cfg = load_config()
                    set_config(cfg.model_dump())
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


__all__ = [
    "Config",
    "get_config",
    "load_config",
    "watch_config",
]
