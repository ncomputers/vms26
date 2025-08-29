import asyncio
from collections import OrderedDict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.troubleshooter as ts


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_troubleshooter_rtsp_mode_skips_mjpeg(monkeypatch):
    async def _fake_ping(host):
        return True

    monkeypatch.setattr(ts, "_ping", _fake_ping)
    monkeypatch.setattr(ts, "check_rtsp", lambda url: {"ok": True})

    class _Client:  # should never be instantiated when mode is rtsp
        def __init__(self, *a, **k):
            raise AssertionError("mjpeg probe should be skipped")

    monkeypatch.setattr(ts.httpx, "AsyncClient", _Client)

    async def _age(cid):
        return 0.5

    monkeypatch.setattr(ts, "get_last_frame_age_sec", _age)

    cams = [{"id": 1, "url": "rtsp://example", "type": "rtsp"}]
    data = asyncio.run(ts.troubleshooter_api(1, cameras=cams))

    assert all(r["ok"] is not False for r in data)
    rtsp = next(r for r in data if r["step"] == "rtsp")
    assert rtsp["ok"] is True
    mjpeg = next(r for r in data if r["step"] == "mjpeg")
    assert mjpeg["ok"] is None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ts.router)
    return TestClient(app)


def test_troubleshooter_tests_endpoint(client, monkeypatch):
    monkeypatch.setattr(ts, "list_tests", lambda: OrderedDict([("a", object()), ("b", object())]))
    res = client.get("/api/troubleshooter/tests")
    assert res.status_code == 200
    body = res.json()
    assert body["tests"] == ["a", "b"]
    assert body["capabilities"]["sse"] is True


def test_troubleshooter_run_continues_on_error(client, monkeypatch):
    order = []

    async def ok_test(cam_id):
        order.append("ok")
        return {
            "id": "ok_test",
            "status": "ok",
            "reason": "",
            "detail": "",
            "suggestion": "",
            "duration_ms": 1,
        }

    async def bad_test(cam_id):
        order.append("bad")
        raise RuntimeError("boom")

    monkeypatch.setattr(
        ts,
        "list_tests",
        lambda: OrderedDict([("ok_test", ok_test), ("bad_test", bad_test)]),
    )
    res = client.post(
        "/api/troubleshooter/run",
        json={"camera_id": 1, "tests": ["ok_test", "bad_test"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["run_id"]
    statuses = [r["status"] for r in body["results"]]
    assert statuses == ["ok", "fail"]
    assert order == ["ok", "bad"]


@pytest.mark.anyio
async def test_run_tests_event_source(monkeypatch):
    async def simple(cam_id):
        return {
            "id": "simple",
            "status": "ok",
            "reason": "",
            "detail": "",
            "suggestion": "",
            "duration_ms": 1,
        }

    monkeypatch.setattr(ts, "list_tests", lambda: OrderedDict([("simple", simple)]))
    gen = ts.run_tests_event_source(1, ["simple"])
    first = await anext(gen)
    assert first.startswith("event: test_result")
    last = await anext(gen)
    assert last.startswith("event: run_complete")
