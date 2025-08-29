import asyncio
from typing import Any

from loguru import logger
from redis.exceptions import RedisError


class RedisFacade:
    def __init__(
        self,
        client: Any,
        *,
        default_timeout: float = 2.0,
        max_workers: int = 4,
        max_retries: int = 2,
        retry_delay: float = 0.1,
    ) -> None:
        self.client = client
        self.default_timeout = default_timeout
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.is_async = hasattr(client, "__aenter__") or client.__class__.__module__.endswith(
            ".asyncio.client"
        )

    async def call(self, func_name: str, *args, **kwargs):
        timeout = kwargs.pop("timeout", self.default_timeout)
        func = getattr(self.client, func_name)
        if self.is_async:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout)
            except TypeError:
                pass
        for attempt in range(self.max_retries + 1):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except RedisError as exc:
                logger.warning("Redis call %s failed: %s", func_name, exc)
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.retry_delay)

    async def get(self, key):
        return await self.call("get", key)

    async def set(self, key, value):
        return await self.call("set", key, value)

    async def hgetall(self, key):
        return await self.call("hgetall", key)

    async def hset(self, key, mapping=None, **kwargs):
        return await self.call("hset", key, mapping=mapping, **kwargs)

    async def zrange(self, key, start, end):
        return await self.call("zrange", key, start, end)

    async def zrevrange(self, key, start, end):
        return await self.call("zrevrange", key, start, end)

    async def zadd(self, key, mapping):
        return await self.call("zadd", key, mapping)

    async def publish(self, channel, message):
        return await self.call("publish", channel, message)

    async def subscribe(self, *channels):
        return await self.call("subscribe", *channels)

    async def unlink(self, *keys):
        return await self.call("unlink", *keys)

    async def delete(self, *keys):
        return await self.call("delete", *keys)

    async def exists(self, *keys):
        return await self.call("exists", *keys)

    async def ping(self) -> bool:
        try:
            await self.call("ping")
            return True
        except RedisError as exc:
            logger.warning("Redis ping failed: %s", exc)
            return False


import redis
import redis.asyncio as redis_async

from config import config as shared_config


def make_facade_from_url(url: str) -> RedisFacade:
    use_async = bool(shared_config.get("redis_async"))
    Client = redis_async.Redis if use_async else redis.Redis
    client = Client.from_url(
        url,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )
    return RedisFacade(client)
