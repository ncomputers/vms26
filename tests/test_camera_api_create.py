"""Test API endpoint for creating cameras."""

import json
import sys
import threading
from types import SimpleNamespace

import fakeredis
import pytest
from loguru import logger

sys.modules.setdefault("cv2", SimpleNamespace())

from routers import cameras


@pytest.fixture(scope="session", autouse=True)
def _patch_redis():
    from fakeredis.aioredis import FakeRedis as AsyncFakeRedis

    import app
    from utils import redis as redis_utils

    mp = pytest.MonkeyPatch()
    mp.setattr(
        app,
        "get_sync_client",
        lambda url=None: fakeredis.FakeRedis(decode_responses=True),
        raising=False,
    )

    async def _fake_get_client(url: str | None = None):
        return AsyncFakeRedis(decode_responses=True)

    mp.setattr(redis_utils, "get_client", _fake_get_client)
    mp.setattr(
        redis_utils,
        "get_sync_client",
        lambda url=None: fakeredis.FakeRedis(decode_responses=True),
    )
    yield
    mp.undo()


def _payload():
    return {
        "name": "Cam",
        "url": "rtsp://user:pass@example.com/stream",
        "profile": "recording",
        "orientation": "horizontal",
        "show": True,
        "transport": "udp",
        "enabled": True,
    }


def test_create_camera_saves_and_masks(client, monkeypatch):
    cameras.cams = []
    called = threading.Event()

    async def fake_start(cam):
        r = client.app.state.redis_client
        r.hset(f"camera:{cam['id']}:health", mapping={"status": "offline"})
        called.set()

    monkeypatch.setattr(cameras.camera_manager, "start", fake_start)

    logs: list[str] = []
    handle = logger.add(lambda m: logs.append(m), level="INFO")
    try:
        res = client.post("/api/cameras", json=_payload())
    finally:
        logger.remove(handle)
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 1
    assert body["site_id"] == 1
    assert "created_at" in body
    assert "updated_at" in body
    assert called.wait(1)
    r = client.app.state.redis_client
    cams = json.loads(r.get("cameras"))
    assert cams[0]["rtsp_transport"] == "udp"
    assert cams[0]["site_id"] == 1
    health = r.hgetall("camera:1:health")
    assert health.get("status") == "offline"
    joined = "".join(logs)
    assert "***:***@" in joined
    assert "user:pass@" not in joined


def test_create_camera_uppercase_rtsp_url(client, monkeypatch):
    cameras.cams = []
    called = threading.Event()

    async def fake_start(cam):
        called.set()

    monkeypatch.setattr(cameras.camera_manager, "start", fake_start)

    payload = _payload()
    payload["url"] = "RTSP://user:pass@example.com/stream"
    res = client.post("/api/cameras", json=payload)
    assert res.status_code == 201
    assert called.wait(1)
    r = client.app.state.redis_client
    cams = json.loads(r.get("cameras"))
    assert cams[0]["type"] == "rtsp"
    assert cams[0]["site_id"] == 1


def test_create_camera_auto_resolution(client, monkeypatch):
    cameras.cams = []

    async def fake_start(cam):
        pass

    async def fake_res(
        url,
        *,
        cache_seconds=300,
        invalidate=False,
        timeout=5,
        fallback_ttl=None,
    ):
        return 111, 222

    monkeypatch.setattr(cameras.camera_manager, "start", fake_start)
    monkeypatch.setattr(cameras, "async_get_stream_resolution", fake_res)

    payload = _payload()
    payload["resolution"] = "auto"
    res = client.post("/api/cameras", json=payload)
    assert res.status_code == 201
    r = client.app.state.redis_client
    cams = json.loads(r.get("cameras"))
    assert cams[0]["resolution"] == "111x222"


def test_create_camera_with_coordinates(client, monkeypatch):
    cameras.cams = []

    async def fake_start(cam):
        pass

    monkeypatch.setattr(cameras.camera_manager, "start", fake_start)

    payload = _payload()
    payload["latitude"] = 12.34
    payload["longitude"] = -56.78
    res = client.post("/api/cameras", json=payload)
    assert res.status_code == 201
    r = client.app.state.redis_client
    cams = json.loads(r.get("cameras"))
    assert cams[0]["latitude"] == 12.34
    assert cams[0]["longitude"] == -56.78
