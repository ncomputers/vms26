from __future__ import annotations

import os
import time
from typing import Callable, TypeVar, overload

T = TypeVar("T", int, float)


def now_ms() -> int:
    """Return current wall clock time in milliseconds."""
    return round(time.time() * 1000)


def mtime() -> float:
    """Return monotonic time in seconds as a float."""
    return time.monotonic_ns() / 1_000_000_000


def parse_bool(s, default: bool = False) -> bool:
    """Parse *s* into a boolean.

    Accepts common truthy strings like ``"1"``, ``"true"``, ``"yes"`` and ``"on"``.
    Any other value yields ``default``.
    """

    if isinstance(s, bool):
        return s
    if not isinstance(s, str):
        return default
    return s.strip().lower() in {"1", "true", "yes", "on"}


def getenv_num(name: str, default: T, cast: Callable[[str], T]) -> T:
    """Return numeric environment variable ``name`` parsed with ``cast``.

    Falls back to ``default`` if the variable is unset or cannot be parsed.
    """

    val = os.getenv(name)
    if val is None:
        return default
    try:
        return cast(val)
    except (TypeError, ValueError):
        return default


class RateLimiter:
    """Simple monotonic time based rate limiter."""

    def __init__(self, interval_sec: float) -> None:
        self.interval = interval_sec
        self._last = 0.0

    def ok(self) -> bool:
        now = mtime()
        if now - self._last >= self.interval:
            self._last = now
            return True
        return False
