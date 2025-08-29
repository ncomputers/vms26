import asyncio
import json

import fakeredis
import pytest
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis

from utils.redis_facade import RedisFacade


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_sync_operations():
    r = fakeredis.FakeRedis(decode_responses=True)
    r.zadd("k", {"a": 1, "b": 2})
    fx = RedisFacade(r)
    res = await fx.zrevrange("k", 0, -1)
    assert res == ["b", "a"]


@pytest.mark.anyio
async def test_async_operations():
    r = AsyncFakeRedis(decode_responses=True)
    await r.zadd("k", {"a": 1, "b": 2})
    fx = RedisFacade(r)
    res = await fx.zrevrange("k", 0, -1)
    assert res == ["b", "a"]


@pytest.mark.anyio
async def test_retry_logic():
    class Flaky:
        def __init__(self):
            self.calls = 0

        def ping(self):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("fail")
            return True

    fx = RedisFacade(Flaky(), max_retries=1, retry_delay=0)
    assert await fx.call("ping") is True
