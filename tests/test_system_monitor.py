import json
from types import SimpleNamespace

import fakeredis
import psutil

from core import events
from workers.system_monitor import SystemMonitor


def test_system_monitor_emits_events(monkeypatch):
    r = fakeredis.FakeRedis()
    cfg = {"alerts": {"network_high": 1, "disk_low": 10, "cpu_high": 50}}
    monitor = SystemMonitor(cfg, r, interval=1, start=False)

    net = SimpleNamespace(bytes_sent=0, bytes_recv=0)
    monkeypatch.setattr(psutil, "net_io_counters", lambda: net)
    monitor.sample()  # establish baseline
    net.bytes_sent = 10
    disk = SimpleNamespace(percent=95)
    monkeypatch.setattr(psutil, "disk_usage", lambda _: disk)
    monkeypatch.setattr(psutil, "cpu_percent", lambda: 90)
    monitor.sample()
    rows = [json.loads(e) for e in r.zrange("events", 0, -1)]
    names = {r["event"] for r in rows}
    assert events.NETWORK_USAGE_HIGH in names
    assert events.DISK_SPACE_LOW in names
    assert events.SYSTEM_CPU_HIGH in names
