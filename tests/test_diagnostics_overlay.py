"""Tests for diagnostics overlay endpoints."""

import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routers import detections, diagnostics  # noqa: E402


class DummyTracker:
    def __init__(self):
        self.last_frame_shape = (480, 640)
        self.in_count = 1
        self.out_count = 0
        self.tracks = {1: {"bbox": (0, 0, 10, 10), "label": "person", "conf": 0.9}}


@pytest.fixture
def app(monkeypatch):
    app = FastAPI()
    cfg = {"secret_key": "secret"}
    trackers = {1: DummyTracker()}
    cams = [{"id": 1, "url": "rtsp://x"}]
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    app.state.config = cfg
    app.state.trackers = trackers
    app.state.cameras = cams
    app.state.templates = Jinja2Templates(directory=str(ROOT / "templates"))
    app.include_router(diagnostics.router)
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    monkeypatch.setattr(diagnostics, "check_rtsp", lambda url: {"ok": True})
    monkeypatch.setattr(
        "utils.redis.get_sync_client",
        lambda: types.SimpleNamespace(hgetall=lambda *a, **k: {}),
    )

    class DummyRenderer:
        def __init__(self, shape):
            import numpy as np

            self.frame = np.zeros(shape, dtype=np.uint8)
            self.output = np.zeros(shape, dtype=np.uint8)

            def put_nowait(msg):
                self.output[:] = 1

            self.queue = types.SimpleNamespace(put_nowait=put_nowait)
            self.process = types.SimpleNamespace(join=lambda timeout=None: None)

        def close(self):
            pass

    monkeypatch.setattr(diagnostics, "RendererProcess", DummyRenderer)

    class DummyAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            class Resp:
                status_code = 200

            return Resp()

    monkeypatch.setattr(diagnostics, "httpx", types.SimpleNamespace(AsyncClient=DummyAsyncClient))

    class DummyWS:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        diagnostics,
        "websockets",
        types.SimpleNamespace(connect=lambda *a, **k: DummyWS()),
    )

    class DummyModel:
        def predict(self, img):
            return []

    monkeypatch.setattr(diagnostics, "get_yolo", lambda *a, **k: DummyModel())
    return app


def test_api(app):
    client = TestClient(app)
    resp = client.get("/api/diagnostics/overlay/1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 11
    assert any(r["step"] == "S0" and r["ok"] for r in data)


def test_template(app):
    client = TestClient(app)
    resp = client.get("/diagnostics/overlay/1")
    assert resp.status_code == 200
    assert "Run All Checks" in resp.text


def test_legacy_redirect(app):
    client = TestClient(app)
    resp = client.get("/diagnostics_overlay.html?cam_id=1", follow_redirects=False)
    assert resp.status_code in {301, 302, 307}
    assert resp.headers["location"].endswith("/diagnostics/overlay/1")
