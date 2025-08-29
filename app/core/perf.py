"""Lightweight performance counters for camera pipelines."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict


class EWMA:
    """Exponentially weighted moving average."""

    def __init__(self, beta: float = 0.2) -> None:
        self.beta = beta
        self.value = 0.0
        self._initialized = False

    def update(self, x: float) -> float:
        """Update the rolling average with ``x`` and return the new value."""
        if not self._initialized:
            self.value = x
            self._initialized = True
        else:
            self.value += self.beta * (x - self.value)
        return self.value


class StatWin:
    """Fixed-size window for percentile statistics."""

    def __init__(self, n: int = 120) -> None:
        self.n = n
        self.samples: Deque[float] = deque(maxlen=n)

    def add(self, x: float) -> None:
        self.samples.append(x)

    def _percentile(self, p: float) -> float:
        if not self.samples:
            return 0.0
        data = sorted(self.samples)
        k = int(p * (len(data) - 1))
        return data[k]

    def p50(self) -> float:
        return self._percentile(0.5)

    def p95(self) -> float:
        return self._percentile(0.95)


class PerfCounter:
    """Runtime counters for a single camera."""

    def __init__(self) -> None:
        self.fps_in = EWMA()
        self.fps_out = EWMA()
        self.qdepth = 0
        self.drops = 0
        self.det_ms = StatWin()
        self.trk_ms = StatWin()
        self.last_ts = 0.0
        self._last_in: float | None = None
        self._last_out: float | None = None

    def on_input(self) -> None:
        now = time.time()
        if self._last_in is not None:
            dt = now - self._last_in
            if dt > 0:
                self.fps_in.update(1.0 / dt)
        self._last_in = now

    def on_output(self) -> None:
        now = time.time()
        if self._last_out is not None:
            dt = now - self._last_out
            if dt > 0:
                self.fps_out.update(1.0 / dt)
        self._last_out = now
        self.last_ts = now

    def on_drop(self) -> None:
        self.drops += 1

    def on_det_ms(self, ms: float) -> None:
        self.det_ms.add(ms)

    def on_trk_ms(self, ms: float) -> None:
        self.trk_ms.add(ms)


PERF: Dict[str, PerfCounter] = defaultdict(PerfCounter)
