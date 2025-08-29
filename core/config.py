from __future__ import annotations

"""Configuration helpers."""

from config import config as _config


def get_config() -> dict:
    """Return application configuration."""
    return _config


__all__ = ["get_config"]
