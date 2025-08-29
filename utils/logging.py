"""Central logging configuration for the application."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "app.log"


# setup_logging routine


def setup_logging(log_file: str | Path | None = None) -> None:
    """Configure root logger using dictConfig."""
    path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    config: Dict[str, Any] = {
        "version": 1,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": "INFO",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(path),
                "maxBytes": 1_000_000,
                "backupCount": 5,
                "formatter": "standard",
                "level": "INFO",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    }
    logging.config.dictConfig(config)


# get_logger routine


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger."""
    return logging.getLogger(name)


import json
import re
import time

_CRED_RE = re.compile(r"(?<=://)([^:@\s]+):([^@/\s]+)@")


def mask_uri(uri: str) -> str:
    """Return *uri* with credentials redacted."""
    return _CRED_RE.sub("***:***@", uri)


def log_capture_event(cam, msg, lvl: str = "info", **extras) -> None:
    """Emit a structured capture event log."""
    logger = logging.getLogger("capture")
    event = {"ts": time.time(), "subsys": "capture", "cam": cam, "lvl": lvl, "msg": msg}
    if "uri" in extras:
        extras["uri"] = mask_uri(str(extras["uri"]))
    event.update(extras)
    logger.log(getattr(logging, lvl.upper(), logging.INFO), json.dumps(event))


__all__ = ["setup_logging", "get_logger", "log_capture_event", "mask_uri"]
