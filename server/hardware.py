from __future__ import annotations

import json
import os
from contextlib import suppress

from loguru import logger

from utils.cpu import _calc_w

logger = logger.bind(module="hardware")


def _early_cpu_setup() -> None:
    """Set thread-spawning env vars before heavy imports."""
    config_path = os.getenv("CONFIG_PATH", "config.json")
    workers_env = os.getenv("WORKERS")
    workers = None
    if workers_env:
        with suppress(ValueError):
            workers = int(workers_env)
    cores = os.cpu_count() or 1
    try:
        with open(config_path) as f:
            pct = int(json.load(f).get("cpu_limit_percent", 50))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pct = 50
    w = _calc_w(workers, pct, cores)
    for var in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[var] = str(w)
    logger.info("Resolved core count: {} of {}", w, cores)
