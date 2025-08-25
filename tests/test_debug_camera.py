"""Tests for debug camera page and update."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from routers import debug
from utils.redis_facade import RedisFacade


class DummyRequest:
    def __init__(self, data=None):
        self.session = {"user": {"role": "admin"}}
        self._data = data or {}

    async def json(self):
        return self._data


class DummyRedis:
    def __init__(self):
        self.store = {"camera_debug:1": b"fail"}

    def get(self, key):
        return self.store.get(key)


class DummyRedisStr:
    def __init__(self):
        self.store = {"camera_debug:1": "ok"}

    def get(self, key):
        return self.store.get(key)


class DummyRedisHSet:
    def __init__(self):
        self.calls = []

    def hset(self, key, mapping):
        self.calls.append((key, mapping))

    def get(self, key):  # unused but for interface compatibility
        return None


class DummyTracker:
    def __init__(self):
        self.cfg = {"pipeline": "orig", "resolution": "640x480"}
        self.pipeline_info = "orig"
        self.capture_backend = "ffmpeg"
        self.src = "url"
        self.src_type = "rtsp"
        self.resolution = "640x480"
        self.rtsp_transport = "tcp"
        self.stream_mode = "gstreamer"
        self.restart_capture = False
        self.pipeline = ""

    def apply_debug_pipeline(self, pipeline=None, **params):
        if pipeline is not None:
            self.pipeline = pipeline
            self.pipeline_info = pipeline
            self.cfg["pipeline"] = pipeline
        if "rtsp_transport" in params:
            self.rtsp_transport = params["rtsp_transport"]
        if "resolution" in params:
            self.resolution = params["resolution"]
            self.cfg["resolution"] = params["resolution"]

        self.restart_capture = True


@pytest.mark.parametrize(
    "redis_cls,summary",
    [(DummyRedis, "fail"), (DummyRedisStr, "ok")],
)
def test_debug_camera_page(redis_cls, summary):
    trackers = {1: DummyTracker()}
    cams = [{"id": 1, "name": "cam1"}]

    redis = RedisFacade(redis_cls())
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    req = DummyRequest()
    resp = asyncio.run(
        debug.debug_overview(
            req,
            trackers_map=trackers,
            cams=cams,
            redisfx=redis,
            cfg={},
            templates=templates,
        )
    )
    cam_ctx = resp.context["cameras"][0]
    assert cam_ctx["pipeline"] == "orig"
    assert cam_ctx["backend"] == "ffmpeg"
    assert cam_ctx["debug_summary"] == summary
    assert cam_ctx["debug_attempts"] == []


@pytest.mark.parametrize("cam_id", [1, "1"])
def test_debug_camera_update_camid(cam_id):
    tr = DummyTracker()
    trackers = {1: tr}
    req = DummyRequest({"cam_id": cam_id, "rtsp_transport": "udp"})
    resp = asyncio.run(
        debug.debug_camera_update(
            req, trackers_map=trackers, redisfx=RedisFacade(DummyRedisHSet())
        )
    )
    assert tr.rtsp_transport == "udp"
    assert tr.cfg["pipeline"] == "orig"
    assert tr.pipeline_info == "orig"
    assert tr.restart_capture is True
    assert resp["cam_id"] == 1
    assert resp["pipeline"] == "orig"


def test_debug_camera_update_pipeline():
    tr = DummyTracker()
    trackers = {1: tr}
    req = DummyRequest({"cam_id": 1, "rtsp_transport": "udp", "pipeline": "pipe1"})
    resp = asyncio.run(
        debug.debug_camera_update(
            req, trackers_map=trackers, redisfx=RedisFacade(DummyRedisHSet())
        )
    )
    assert tr.rtsp_transport == "udp"
    assert tr.pipeline == "pipe1"
    assert tr.cfg["pipeline"] == "pipe1"
    assert tr.src == "url"
    assert tr.restart_capture is True
    assert resp["pipeline"] == "pipe1"
    assert resp["restarting"] is True


def test_debug_camera_update_resolution():
    tr = DummyTracker()
    trackers = {1: tr}
    redis = DummyRedisHSet()
    req = DummyRequest({"cam_id": 1, "resolution": "800x600"})
    resp = asyncio.run(
        debug.debug_camera_update(
            req, trackers_map=trackers, redisfx=RedisFacade(redis)
        )
    )
    assert tr.resolution == "800x600"
    assert tr.cfg["resolution"] == "800x600"
    assert tr.restart_capture is True
    assert redis.calls[0] == ("camera:1", {"resolution": "800x600"})
    assert resp["pipeline"] == "orig"
