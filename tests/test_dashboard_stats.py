"""Regression tests for dashboard stats API and helpers."""

import json
from datetime import datetime

import fakeredis
import pytest
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError

import app
from routers import dashboard
from utils import redis as redis_utils
from utils import time as time_utils


@pytest.fixture(scope="session", autouse=True)
def _patch_redis():
    app.get_sync_client = lambda url=None: fakeredis.FakeRedis(decode_responses=True)
    redis_utils.get_sync_client = app.get_sync_client
    yield


@pytest.fixture
def anyio_backend():  # pragma: no cover - used by anyio
    return "asyncio"


def test_dashboard_stats_missing_entry_exit(client):
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 200


def test_parse_range_today(monkeypatch):
    fixed_now = datetime(2023, 1, 2, 15, 30)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls):  # type: ignore[override]
            return fixed_now

    monkeypatch.setattr(time_utils, "datetime", FixedDatetime)
    monkeypatch.setattr(time_utils.time, "time", lambda: fixed_now.timestamp())
    start, end = dashboard.parse_range("today")
    assert start == int(datetime(2023, 1, 2).timestamp())
    assert end == int(fixed_now.timestamp())


@pytest.mark.anyio
async def test_fetch_stats_and_aggregate():
    redis = AsyncFakeRedis(decode_responses=True)
    ts1 = 1_700_000_000
    ts2 = ts1 + 60
    totals = {
        "in_count": 3,
        "out_count": 1,
        "current": 2,
        "group_counts": json.dumps({"vehicle": {"current": 1}}),
        "anomaly_counts": json.dumps({"helmet": 3}),
    }
    await redis.hset("stats_totals", mapping=totals)
    data = await dashboard.fetch_stats(redis, ts1, ts2)
    result = dashboard.aggregate_metrics(data)
    assert result["timeline"] == [ts2]
    assert result["total_visitors"] == 3
    assert result["vehicles_detected"] == 1
    assert result["safety_violations"] == 3
    assert result["current"] == 2


@pytest.mark.anyio
async def test_load_stats_totals_redis_failure():
    class BadRedis:
        async def hgetall(self, key):  # pragma: no cover - test stub
            raise RedisConnectionError()

        async def xrevrange(self, key, count=1):  # pragma: no cover - test stub
            raise RedisConnectionError()

    totals = await dashboard._load_stats_totals(BadRedis())
    assert totals == {
        "in_count": 0,
        "out_count": 0,
        "current": 0,
        "anomaly_counts": {},
        "group_counts": {},
    }


@pytest.mark.anyio
async def test_load_stats_totals_missing_totals():
    class EmptyRedis:
        async def hgetall(self, key):
            return {}

        async def xrevrange(self, key, count=1):
            return []

    totals = await dashboard._load_stats_totals(EmptyRedis())
    assert totals["in_count"] == 0
    assert totals["out_count"] == 0
    assert totals["current"] == 0
    assert totals["anomaly_counts"] == {}
    assert totals["group_counts"] == {}


@pytest.mark.anyio
async def test_load_stats_totals_malformed_json():
    class BadJSONRedis:
        async def hgetall(self, key):
            return {
                b"in_count": b"5",
                b"out_count": b"2",
                b"current": b"3",
                b"anomaly_counts": b"{bad}",
                b"group_counts": b"notjson",
            }

        async def xrevrange(self, key, count=1):  # pragma: no cover - test stub
            return []

    totals = await dashboard._load_stats_totals(BadJSONRedis())
    assert totals["in_count"] == 5
    assert totals["out_count"] == 2
    assert totals["current"] == 3
    assert totals["anomaly_counts"] == {}
    assert totals["group_counts"] == {}


def test_compute_group_counts():
    class T:
        def __init__(self, in_counts=None, out_counts=None):
            self.in_counts = in_counts or {}
            self.out_counts = out_counts or {}

    trackers = {
        1: T({"person": 3, "vehicle": 1}, {"person": 1}),
        2: T({"person": 2}, {"person": 1, "vehicle": 0}),
    }
    res = dashboard.compute_group_counts(trackers, ["person", "vehicle"])
    assert res["person"] == {"in": 5, "out": 2, "current": 3}
    assert res["vehicle"] == {"in": 1, "out": 0, "current": 1}
