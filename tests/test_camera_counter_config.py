import fakeredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routers import cameras

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    cfg = {
        "license_info": {"features": {"in_out_counting": True}},
        "features": {"in_out_counting": True},
    }
    cams = [
        {
            "id": 1,
            "name": "Cam",
            "url": "rtsp://example",
            "tasks": [],
            "face_recognition": False,
            "ppe": False,
            "enabled": True,
        }
    ]
    r = fakeredis.FakeRedis()
    cameras.init_context(cfg, cams, {}, r, str(tmp_path))
    monkeypatch.setattr(cameras, "require_roles", lambda r, roles: {"role": "admin"})

    class DummyManager:
        async def start(self, cam_id):
            return None

    app = FastAPI()
    app.include_router(cameras.router)
    app.dependency_overrides[cameras.get_camera_manager] = lambda: DummyManager()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, r


async def test_effective_config_roundtrip(client):
    ac, r = client
    line = {"x1": 0, "y1": 0, "x2": 1, "y2": 1, "orientation": "vertical"}
    resp = await ac.patch("/api/cameras/1/line", json=line)
    assert resp.status_code == 200
    resp = await ac.patch("/api/cameras/1", json={"counting": True})
    assert resp.status_code == 200
    settings = {"vehicle_classes": ["car", "truck"]}
    resp = await ac.patch("/api/cameras/1/settings", json=settings)
    assert resp.status_code == 200
    resp = await ac.get("/api/cameras/1/effective_config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["line"]["x1"] == 0.0
    assert data["counting"] is True
    assert set(data["vehicle_classes"]) == {"car", "truck"}
    assert data["line"]["orientation"] == "vertical"
