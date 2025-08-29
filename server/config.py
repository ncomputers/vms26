from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

import utils.redis as redis_utils

try:  # pragma: no cover
    from core.tracker_manager import load_cameras  # type: ignore
except Exception:  # pragma: no cover
    load_cameras = None  # type: ignore

logger = logger.bind(module="config")


def _load_secret_key() -> str:
    """Fetch session secret key from config or fall back to default."""
    config_path = os.getenv("CONFIG_PATH", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f).get("secret_key", "change-me")
    except (OSError, json.JSONDecodeError):
        return "change-me"


def _read_initial_config(path: str) -> dict:
    """Load minimal configuration required for bootstrap."""
    logger.info("Loading config from {}", path)
    try:
        from config import load_config

        return load_config(path, None, minimal=True)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.exception("Failed to read config: {}", e)
        raise SystemExit(1)


def _connect_redis(url: str) -> Redis:
    """Connect to Redis and return a client.

    If the connection fails, a :class:`fakeredis.FakeRedis` instance is
    returned so the application can still start in a degraded mode.  This
    keeps unit tests and development environments functional even when a
    real Redis server is not available.
    """
    try:
        client = redis_utils.get_sync_client(url)
        logger.info("Connected to Redis at {}", url)
        return client
    except (RedisError, OSError) as e:
        logger.warning("Redis connection failed: {}", e)
        try:
            import fakeredis

            logger.info("Falling back to fakeredis")
            return fakeredis.FakeRedis(decode_responses=True)
        except Exception as fe:  # pragma: no cover - fakeredis import failure
            logger.exception("fakeredis not available: {}", fe)
            raise SystemExit(1) from fe


def _apply_license(cfg: dict, license_info: dict) -> dict:
    """Integrate license information into configuration."""
    if not license_info.get("valid"):
        logger.warning("Invalid License: {}", license_info.get("error"))
        cfg["features"] = {}
    else:
        cfg["features"] = license_info.get("features", cfg.get("features", {}))
    cfg["license_info"] = license_info
    return cfg


def _load_camera_profiles(redis_client, cfg: dict, stream_url: str | None) -> list[dict]:
    """Fetch camera configurations or override with CLI stream."""
    lc = load_cameras
    if lc is None:  # pragma: no cover
        from core.tracker_manager import load_cameras as lc
    logger.info("Loading cameras")
    default_url = cfg.get("stream_url")
    if default_url is None:
        logger.warning("stream_url missing from config; defaulting to empty string")
        default_url = ""
    try:
        cams = lc(redis_client, default_url)
        logger.info("Loaded {} cameras", len(cams))
        try:
            max_id = max((c.get("id", 0) for c in cams), default=0)
            cur = int(redis_client.get("camera:id_seq") or 0)
            if cur < max_id:
                redis_client.set("camera:id_seq", max_id)
        except Exception:
            logger.warning("Unable to sync camera id counter")
    except (RuntimeError, OSError) as e:
        logger.exception("Failed to load cameras: {}", e)
        raise SystemExit(1)
    if stream_url:
        cams = [
            {
                "id": 1,
                "name": "CameraCLI",
                "url": stream_url,
                "tasks": ["both"],
                "enabled": True,
            }
        ]
        logger.info("Using CLI stream URL for single camera")
    return cams
