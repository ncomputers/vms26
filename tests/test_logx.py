"""Purpose: verify logx helpers push structured events and utilities."""

import json
import types

import pytest

from utils import logx


def test_push_redis_masks_and_trims(monkeypatch):
    calls = []

    class Dummy:
        def lpush(self, key, value):
            calls.append(("lpush", key, value))

        def ltrim(self, key, start, end):
            calls.append(("ltrim", key, start, end))

    dummy = Dummy()
    monkeypatch.setattr(logx, "_redis_client", dummy)
    logx.event(
        "capture_start",
        camera_id=1,
        mode="test",
        url="rtsp://user:pass@example.com/stream",
    )
    lpush_calls = [c for c in calls if c[0] == "lpush"]
    assert lpush_calls
    payload = json.loads(lpush_calls[0][2])
    assert payload["url"] == "rtsp://user:***@example.com/stream"
    assert any(c[0] == "ltrim" for c in calls)


def test_every_and_on_change(monkeypatch):
    logx._last_times.clear()
    logx._last_values.clear()
    t = {"now": 10.0}
    monkeypatch.setattr(logx, "time", types.SimpleNamespace(time=lambda: t["now"]))
    assert logx.every(5, "k")
    assert not logx.every(5, "k")
    t["now"] = 16
    assert logx.every(5, "k")
    assert logx.on_change("a", 1)
    assert not logx.on_change("a", 1)
    assert logx.on_change("a", 2)
