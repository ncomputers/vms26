"""Tests for app.core.redis_bus helpers."""

from app.core import redis_bus


class DummyRedis:
    def __init__(self):
        self.called = False

    def xadd(self, *args, **kwargs):
        self.called = True


def test_xadd_event_skips_empty_payload(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(redis_bus, "get_redis", lambda: dummy)
    redis_bus.xadd_event()
    assert dummy.called is False


def test_xadd_event_publishes_non_empty(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(redis_bus, "get_redis", lambda: dummy)
    redis_bus.xadd_event(data={"foo": "bar"})
    assert dummy.called is True
