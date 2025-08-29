from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from core.context import AppContext, get_app_context
from routers import reports


class FakeRedis:
    def zcard(self, key):
        return 0

    def zrevrangebyscore(self, *args, **kwargs):
        return []


class FakeRedisFX:
    async def call(self, *args, **kwargs):
        return []


def create_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(reports.router)
    templates = Jinja2Templates(directory="templates")
    ctx = AppContext(
        config={"track_objects": ["person"], "count_classes": [], "branding": {}},
        redis=FakeRedis(),
        trackers={},
        templates=templates,
        branding={},
        cameras=[{"id": 1, "archived": False}],
        redisfx=FakeRedisFX(),
    )
    app.dependency_overrides[get_app_context] = lambda: ctx
    return TestClient(app)


def test_report_page_renders(monkeypatch):
    client = create_app()
    monkeypatch.setattr(reports, "require_roles", lambda request, roles: True)
    resp = client.get("/report")
    assert resp.status_code == 200
