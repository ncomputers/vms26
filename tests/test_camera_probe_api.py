import shutil
from urllib.parse import urlparse

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from modules import stream_probe


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.post("/cameras/probe")
    async def camera_probe(body: dict):
        url = body.get("url")
        if not isinstance(url, str) or not url.startswith("rtsp://"):
            return JSONResponse({"ok": False, "error_code": "BAD_URL"}, status_code=400)
        info = stream_probe.probe_stream(url)
        details = {
            "codec": info["metadata"]["codec"],
            "resolution": f"{info['metadata']['width']}x{info['metadata']['height']}",
            "transport_used": info["transport"],
        }
        return {"ok": True, "details": details}

    @app.post("/api/rtsp/probe")
    async def rtsp_probe(payload: dict):
        url = payload.get("url", "")
        parsed = urlparse(url)
        info = stream_probe.probe_stream(url)
        data = {
            "ok": True,
            "parsed": {"host": parsed.hostname},
            "meta": {"width": info["metadata"]["width"]},
            "measure": {"transport_used": info["transport"]},
        }
        return data

    return TestClient(app)


@pytest.mark.parametrize(
    "endpoint,payload,fake_result,extra_setup,check",
    [
        (
            "/cameras/probe",
            {
                "name": "cam1",
                "type": "RTSP",
                "url": "rtsp://example",
                "transport": "TCP",
                "timeout_sec": 8,
            },
            {
                "metadata": {"codec": "h264", "width": 640, "height": 480},
                "transport": "tcp",
                "hwaccel": False,
                "effective_fps": 29.7,
            },
            lambda m: None,
            lambda d: (
                d["details"]["codec"] == "h264"
                and d["details"]["resolution"] == "640x480"
                and d["details"]["transport_used"] == "tcp"
            ),
        ),
        (
            "/api/rtsp/probe",
            {"url": "rtsp://admin:pass@192.168.31.11:554/cam/realmonitor?channel=1&subtype=1"},
            {
                "metadata": {
                    "codec": "h264",
                    "profile": "Main",
                    "width": 1280,
                    "height": 720,
                    "pix_fmt": "yuv420p",
                    "bit_rate": None,
                    "avg_frame_rate": "20/1",
                    "r_frame_rate": "20/1",
                    "nominal_fps": 20.0,
                },
                "transport": "TCP",
                "hwaccel": True,
                "frames": 157,
                "effective_fps": 19.6,
                "elapsed": 8.02,
            },
            lambda m: m.setattr(shutil, "which", lambda name: f"/usr/bin/{name}"),
            lambda d: (
                d["parsed"]["host"] == "192.168.31.11"
                and d["meta"]["width"] == 1280
                and d["measure"]["transport_used"] == "TCP"
            ),
        ),
    ],
)
def test_probe_endpoints(
    client: TestClient,
    monkeypatch,
    endpoint,
    payload,
    fake_result,
    extra_setup,
    check,
):
    def fake_probe(url, sample_seconds=8, enable_hwaccel=True):
        return fake_result

    monkeypatch.setattr(stream_probe, "probe_stream", fake_probe)
    extra_setup(monkeypatch)
    resp = client.post(endpoint, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert check(data)


def test_camera_probe_bad_url(client: TestClient):
    body = {
        "name": "cam1",
        "type": "RTSP",
        "url": "http://example",  # not rtsp
        "transport": "TCP",
        "timeout_sec": 5,
    }
    resp = client.post("/cameras/probe", json=body)
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "BAD_URL"
