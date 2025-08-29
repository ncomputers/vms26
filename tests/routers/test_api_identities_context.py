from __future__ import annotations

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from core.context import AppContext, get_app_context
from routers import api_identities


class FakeRedis:
    def __init__(self):
        self.data = {
            "identity:abc": {
                "name": "Alice",
                "company": "ACME",
                "tags": "vip",
                "primary_face_id": "f1",
            },
            "identity:abc:faces": ["f1"],
            "identity:abc:visits": ["2024"],
            "identity:abc:cameras": {"1"},
            "identity_face:f1": {"url": "/faces/f1.jpg"},
        }

    def hgetall(self, key):
        return self.data.get(key, {})

    def lrange(self, key, start, end):
        return list(self.data.get(key, []))

    def smembers(self, key):
        return set(self.data.get(key, set()))

    def hset(self, key, mapping):
        self.data.setdefault(key, {}).update(mapping)

    def lrem(self, key, count, value):
        vals = [v for v in self.data.get(key, []) if v != value]
        self.data[key] = vals

    def delete(self, key):
        self.data.pop(key, None)

    def hget(self, key, field):
        return self.data.get(key, {}).get(field)

    def hdel(self, key, field):
        if key in self.data:
            self.data[key].pop(field, None)


def create_app() -> TestClient:
    app = FastAPI()
    app.include_router(api_identities.router)
    templates = Jinja2Templates(directory="templates")
    ctx = AppContext(
        config={},
        redis=FakeRedis(),
        trackers={},
        templates=templates,
        branding={},
        cameras=[],
    )
    app.dependency_overrides[get_app_context] = lambda: ctx
    return TestClient(app)


def test_get_identity_uses_context():
    client = create_app()
    resp = client.get("/api/identities/abc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alice"
