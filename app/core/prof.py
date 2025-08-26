from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Callable, Deque, Dict, TypeVar, cast

# Ring buffer storage for profiling samples
PERF: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=120))

# Profiling only enabled when environment variable explicitly set
ENABLED = os.getenv("VMS26_PROF") == "1"

F = TypeVar("F", bound=Callable[..., Any])


def profiled(name: str) -> Callable[[F], F]:
    """Decorator that records call duration under ``name`` when enabled.

    Durations are stored in milliseconds in a ring buffer of length 120 for
    each ``name`` in the global ``PERF`` dictionary. When profiling is not
    enabled, the wrapped function is returned unchanged to avoid overhead.
    """

    def decorator(fn: F) -> F:
        if not ENABLED:
            return fn

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                dt_ms = (time.perf_counter() - start) * 1000.0
                PERF[name].append(dt_ms)

        return cast(F, wrapper)

    return decorator


__all__ = ["PERF", "profiled"]
