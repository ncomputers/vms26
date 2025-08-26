"""Application configuration loader.

This module exposes a :class:`Config` settings model backed by a JSON file.
The helper :func:`get_config` returns a singleton instance that callers may
use to access configuration values.  Existing configuration mechanisms are
unchanged; this module is provided for optional use.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Optional
import json
from pathlib import Path
from typing import Any, Optional


from loguru import logger
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Pydantic settings for application configuration."""

    features: dict[str, Any] = {}
    ui: dict[str, Any] = {}
    thresholds: dict[str, Any] = {}
    cameras: list[dict[str, Any]] = []
    target_fps: int = 15
    jpeg_quality: int = 80

import utils.redis as redis_utils
from config import load_config, set_config, config as _CONFIG
from .redis_keys import CFG_UI_VMS, CFG_VERSION


def load_config(path: str = "./config.json") -> Config:
    """Load configuration from *path*.

    The file is parsed as JSON if it exists, otherwise defaults are used.  A
    single informational log line is emitted indicating the number of cameras
    loaded.
    """

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


__all__ = ["Config", "get_config", "load_config"]

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


def get_vms_ui(redis: Optional[Redis] = None) -> dict:
    """Return stored VMS UI configuration."""
    client = redis or redis_utils.get_sync_client()
    data = client.hgetall(CFG_UI_VMS)
    config: dict[str, dict[str, str]] = {"tiles": {}, "alerts": {}}
    for k, v in data.items():
        if k.startswith("tiles."):
            config["tiles"][k.split(".", 1)[1]] = v
        elif k.startswith("alerts."):
            config["alerts"][k.split(".", 1)[1]] = v
        else:
            config[k] = v
    return config


def _flatten(prefix: str, data: dict, out: dict) -> None:
    for k, v in data.items():
        if isinstance(v, dict):
            _flatten(f"{prefix}{k}.", v, out)
        else:
            out[f"{prefix}{k}"] = v


def set_vms_ui(patch: dict, redis: Optional[Redis] = None) -> dict:
    """Patch VMS UI configuration and bump version."""
    client = redis or redis_utils.get_sync_client()
    flat: dict[str, Any] = {}
    _flatten("", patch, flat)
    if flat:
        client.hset(CFG_UI_VMS, mapping=flat)
    client.incr(CFG_VERSION)
    return get_vms_ui(client)


__all__.extend(["get_vms_ui", "set_vms_ui"])

