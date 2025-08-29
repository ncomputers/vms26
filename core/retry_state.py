from __future__ import annotations

"""Utility for tracking retry/backoff state with a circuit breaker."""

import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from random import random  # noqa: E402

# reconnect tuning
BACKOFF_BASE = 0.5
BACKOFF_MAX = 30.0
JITTER = 0.3
BREAKER_OPEN_SECS = 15.0


@dataclass
class RetryState:
    """Track retry timing and circuit breaker status for a camera.

    Attributes
    ----------
    fail_count:
        Consecutive failure count.
    next_retry_ts:
        Unix timestamp when the next retry should be attempted.
    breaker_state:
        One of ``"CLOSED"``, ``"OPEN"`` or ``"HALF_OPEN"``.
    opened_at:
        When the breaker last opened.
    """

    fail_count: int = 0
    next_retry_ts: float = 0.0
    breaker_state: str = "CLOSED"
    opened_at: float = 0.0

    def should_retry(self) -> bool:
        """Return ``True`` if an action may be attempted now."""
        now = time.time()
        if self.breaker_state == "OPEN":
            if now - self.opened_at < BREAKER_OPEN_SECS:
                return False
            self.breaker_state = "HALF_OPEN"
        if now < self.next_retry_ts:
            return False
        return True

    def record_failure(self) -> None:
        """Update state after a failed attempt."""
        self.fail_count += 1
        backoff = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** min(self.fail_count, 6)))
        jittered = backoff * (1.0 - JITTER + random() * JITTER * 2)
        self.next_retry_ts = time.time() + jittered
        if self.fail_count >= 3 and self.breaker_state == "CLOSED":
            self.breaker_state = "OPEN"
            self.opened_at = time.time()

    def record_success(self) -> None:
        """Reset state after a successful attempt."""
        self.fail_count = 0
        self.next_retry_ts = 0.0
        self.breaker_state = "CLOSED"
        self.opened_at = 0.0
