"""Application configuration loader.

This module exposes a :class:`Config` settings model backed by a JSON file.
The helper :func:`get_config` returns a singleton instance that callers may
use to access configuration values.  Existing configuration mechanisms are
unchanged; this module is provided for optional use.
"""

from __future__ import annotations

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

