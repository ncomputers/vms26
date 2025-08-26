from __future__ import annotations

import logging
from typing import Dict

from .utils import mtime

_last: Dict[str, float] = {}


def get_logger(name: str = "vms26") -> logging.Logger:
    """Return a basic stderr logger configured once."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_throttled(
    logger: logging.Logger,
    key: str,
    level: int,
    msg: str,
    interval: float = 5.0,
) -> bool:
    """Log *msg* if ``interval`` seconds elapsed since last call with ``key``."""
    now = mtime()
    last = _last.get(key, 0.0)
    if now - last >= interval:
        _last[key] = now
        logger.log(level, msg)
        return True
    return False
