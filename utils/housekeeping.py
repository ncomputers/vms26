"""Periodic housekeeping utilities."""

from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Dict, MutableMapping

from utils.logx import log_throttled

try:  # optional heavy dependency
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - torch optional
    torch = None

_CACHES: Dict[str, MutableMapping] = {}
_LOCK = Lock()


def register_cache(name: str, cache: MutableMapping) -> None:
    """Register *cache* dict under *name* for housekeeping."""
    with _LOCK:
        _CACHES[name] = cache


def prune_caches(limit: int = 10_000) -> Dict[str, int]:
    """Prune registered caches exceeding ``limit`` items.

    Returns mapping of cache names to number of entries pruned.
    """
    pruned: Dict[str, int] = {}
    with _LOCK:
        items = list(_CACHES.items())
    for name, cache in items:
        try:
            extra = len(cache) - limit
            if extra > 0:
                keys = list(cache)
                for k in keys[:extra]:
                    cache.pop(k, None)
                pruned[name] = extra
        except Exception:
            continue
    return pruned


def housekeeping() -> None:
    """Run periodic housekeeping tasks."""
    pruned = prune_caches()
    env = os.getenv("VMS26_CUDA_EMPTY_EVERY")
    if torch and torch.cuda.is_available():
        try:
            if env and int(env) == 60:
                torch.cuda.empty_cache()
        except ValueError:
            pass
    parts = [f"{n}={c}" for n, c in pruned.items() if c]
    msg = "[perf] housekeeping" + (" " + " ".join(parts) if parts else "")
    log_throttled(
        logging.getLogger(__name__).info,
        msg,
        key="perf_housekeeping",
        interval=60,
    )


__all__ = ["register_cache", "housekeeping", "prune_caches"]
