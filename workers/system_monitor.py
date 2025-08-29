from __future__ import annotations

"""Background worker sampling system metrics and emitting events."""

import threading
import time
from typing import Optional

import psutil
from loguru import logger

from core import events
from utils.redis import publish_event


class SystemMonitor:
    """Periodically sample system metrics and publish alerts."""

    def __init__(self, cfg: dict, redis_client, interval: int = 5, start: bool = True) -> None:
        self.cfg = cfg
        self.redis = redis_client
        self.interval = interval
        self.running = True
        self._last_net: Optional[int] = None
        if start:
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()
        else:
            self.thread = None

    def stop(self) -> None:
        """Stop the monitor thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def loop(self) -> None:
        """Worker loop."""
        logger.info("SystemMonitor started")
        while self.running:
            self.sample()
            time.sleep(self.interval)
        logger.info("SystemMonitor stopped")

    def sample(self) -> None:
        """Collect metrics and emit events when thresholds exceed config."""
        alerts = self.cfg.get("alerts", {})

        # Network throughput
        try:
            io = psutil.net_io_counters()
            total = io.bytes_sent + io.bytes_recv
            if self._last_net is not None:
                rate = (total - self._last_net) / max(self.interval, 1)
                high = alerts.get("network_high")
                low = alerts.get("network_low")
                if high is not None and rate > high:
                    publish_event(self.redis, events.NETWORK_USAGE_HIGH, rate=rate)
                if low is not None and rate < low:
                    publish_event(self.redis, events.NETWORK_USAGE_LOW, rate=rate)
            self._last_net = total
        except Exception:  # pragma: no cover - psutil may fail
            logger.exception("Network metrics error")

        # Disk usage
        try:
            disk = psutil.disk_usage("/")
            used = disk.percent
            low = alerts.get("disk_low")
            if low is not None and used > low:
                publish_event(self.redis, events.DISK_SPACE_LOW, percent=used)
        except Exception:  # pragma: no cover
            logger.exception("Disk metrics error")

        # CPU load
        try:
            cpu = psutil.cpu_percent()
            high = alerts.get("cpu_high")
            if high is not None and cpu > high:
                publish_event(self.redis, events.SYSTEM_CPU_HIGH, percent=cpu)
        except Exception:  # pragma: no cover
            logger.exception("CPU metrics error")
