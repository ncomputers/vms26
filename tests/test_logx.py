"""Purpose: verify logx helpers push structured events and utilities."""

import json
import types

import pytest
from redis.exceptions import RedisError

from utils import logx


def test_push_redis_masks_and_trims(monkeypatch):
    calls = []

    class Dummy:
        def lpush(self, key, value):
            calls.append(("lpush", key, value))

        def ltrim(self, key, start, end):
            calls.append(("ltrim", key, start, end))

    dummy = Dummy()

    class ClientStub:
        def __call__(self):
            return dummy

        def cache_clear(self):
            pass

    monkeypatch.setattr(logx, "get_redis_client", ClientStub())
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


def test_push_redis_failure_logs_and_clears(monkeypatch, caplog):
    calls = {"cleared": False}

    class Failing:
        def lpush(self, *args, **kwargs):
            raise RedisError("boom")

        def ltrim(self, *args, **kwargs):
            pass

    class Stub:
        def __call__(self):
            return Failing()

        def cache_clear(self):
            calls["cleared"] = True

    monkeypatch.setattr(logx, "get_redis_client", Stub())
    logger = logx.logger
    logger.remove()
    logger.add(caplog.handler, level="WARNING")
    logx.event("capture_start", camera_id=1, mode="m", url="rtsp://a")
    assert "push_redis redis error" in caplog.text
    assert calls["cleared"]
