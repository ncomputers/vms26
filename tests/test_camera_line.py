import pytest
import fakeredis
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from routers import cameras

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    cfg = {
        "license_info": {
            "features": {
                "in_out_counting": True,
                "face_recognition": True,
                "visitor_mgmt": True,
                "ppe_detection": True,
            }
        },
        "features": {
            "in_out_counting": True,
            "face_recognition": True,
            "visitor_mgmt": True,
        },
    }
    cams = [
        {
            "id": 1,
            "name": "Cam",
            "url": "rtsp://example",
            "tasks": [],
            "face_recognition": False,
            "visitor_mgmt": False,
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
        yield ac, cams

async def test_keeps_line_when_omitted(client):
    ac, cams = client
    cams[0]["line"] = [0, 0, 1, 1]
    cams[0]["tasks"] = ["in_count", "out_count"]
    resp = await ac.put("/cameras/1", json={"face_recog": True})
    assert resp.status_code == 200
    assert cams[0]["line"] == [0, 0, 1, 1]
    assert "face_recognition" in cams[0]["tasks"]


async def test_adopts_legacy_line(client):
    ac, cams = client
    cams[0]["inout_line"] = [1, 1, 2, 2]
    cams[0]["tasks"] = ["in_count", "out_count"]
    resp = await ac.put("/cameras/1", json={"face_recog": True})
    assert resp.status_code == 200
    assert cams[0]["line"] == [1, 1, 2, 2]


async def test_requires_line_on_enable(client):
    ac, cams = client
    cams[0]["tasks"] = ["in_count", "out_count"]
    resp = await ac.put("/cameras/1", json={"face_recog": True})
    assert resp.status_code == 400
    assert resp.json()["error"] == "Virtual line required"


async def test_builds_tasks_correctly(client):
    ac, cams = client
    cams[0]["line"] = [0, 0, 1, 1]
    resp = await ac.put(
        "/cameras/1",
        json={"face_recog": True, "counting": True},
    )
    assert resp.status_code == 200
    assert set(cams[0]["tasks"]) == {
        "in_count",
        "out_count",
        "inout_count",
        "face_recognition",
    }


async def test_put_face_recog_true_with_existing_line(client):
    ac, cams = client
    cams[0]["line"] = [0, 0, 1, 1]
    resp = await ac.put("/cameras/1", json={"face_recog": True})
    assert resp.status_code == 200
    assert "face_recognition" in cams[0]["tasks"]
