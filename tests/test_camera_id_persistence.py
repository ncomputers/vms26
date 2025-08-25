import asyncio
import sys
from pathlib import Path

import fakeredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class Buf:
    def __init__(self, data: bytes = b"img"):
        self._data = data

    def tobytes(self) -> bytes:  # pragma: no cover - trivial
        return self._data


class CV2Stub:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5

    @staticmethod
    def imencode(ext, frame):  # pragma: no cover - trivial
        return True, Buf()


sys.modules.setdefault("cv2", CV2Stub)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routers import cameras  # noqa: E402

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def api_client(tmp_path, monkeypatch):
    cfg = {}
    cams = []
    r = fakeredis.FakeRedis()
    cameras.init_context(cfg, cams, {}, r, str(tmp_path))
    monkeypatch.setattr(cameras, "require_roles", lambda r, roles: {"role": "admin"})
    app = FastAPI()
    app.include_router(cameras.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, r, cams


async def _prepare(monkeypatch):
    def ok_probe(*a, **k):
        return {"ok": True}

    monkeypatch.setattr(cameras, "check_rtsp", ok_probe)

    class StreamStub:
        def __init__(self, *a, **k):
            self.last_status = "ok"
            self.last_error = ""
            self.last_hint = ""
            self.last_stderr = ""
            self.last_command = "cmd"

        def read(self):
            return True, object()

        def release(self):
            pass

    monkeypatch.setattr(cameras, "FFmpegCameraStream", StreamStub)
    monkeypatch.setattr(cameras, "cv2", CV2Stub)

    async def fake_start(cam_id):
        return None

    monkeypatch.setattr(cameras.camera_manager, "start", fake_start)


async def test_delete_removes_from_memory_and_redis(api_client, monkeypatch):
    client, r, cams = api_client
    await _prepare(monkeypatch)

    resp = await client.post("/api/cameras", json={"name": "Cam1", "url": "rtsp://a"})
    cam1 = resp.json()["id"]
    r.set(f"camera:{cam1}", "data")
    r.hset(f"camera:{cam1}:health", mapping={"status": "ok"})
    r.set(f"camera_pipeline:{cam1}", "pipe")
    r.set(f"camera_ffmpeg_flags:{cam1}", "flags")
    r.set(f"camera_profile:{cam1}", "prof")

    called = {}

    def fake_stop(cid, trackers):
        called["id"] = cid

    monkeypatch.setattr(cameras.camera_manager, "stop_tracker_fn", fake_stop)

    resp = await client.delete(f"/cameras/{cam1}")
    assert resp.status_code == 200
    assert not cams
    assert called["id"] == cam1
    assert r.get(f"camera:{cam1}") is None
    assert r.hget(f"camera:{cam1}:health", "status") is None
    assert r.get(f"camera_pipeline:{cam1}") is None
    assert r.get(f"camera_ffmpeg_flags:{cam1}") is None
    assert r.get(f"camera_profile:{cam1}") is None
