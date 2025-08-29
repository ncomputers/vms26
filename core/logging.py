from __future__ import annotations

"""Logging utilities."""

import sys

from loguru import logger


def setup_json_logger() -> None:
    """Configure loguru to emit JSON logs to stdout."""
    logger.remove()
    logger.add(sys.stdout, serialize=True)


__all__ = ["setup_json_logger"]
