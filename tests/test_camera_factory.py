import pytest

import modules.camera_factory as cf
from config import config as shared_config
from modules.capture import FrameSourceError, IFrameSource


class Dummy(IFrameSource):
    def __init__(self, uri: str, **kwargs):
        super().__init__(uri)
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def read(self, timeout=None):
        return None

    def info(self):
        return {}

    def close(self) -> None:
        pass


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_rtsp_backend_selection(monkeypatch):
    monkeypatch.setattr(cf, "RtspFfmpegSource", Dummy)
    monkeypatch.setattr(cf, "RtspGstSource", Dummy)
    shared_config["camera"] = {"mode": "rtsp", "uri": "rtsp://x"}
    shared_config["use_gstreamer"] = False
    cap, _ = cf.open_capture(shared_config, 1, capture_buffer=2)
    assert isinstance(cap, Dummy) and cap.opened
    shared_config["use_gstreamer"] = True
    cap, _ = cf.open_capture(shared_config, 1)
    assert isinstance(cap, Dummy) and cap.opened


def test_local_backend(monkeypatch):
    monkeypatch.setattr(cf, "LocalCvSource", Dummy)
    shared_config["camera"] = {"mode": "local", "uri": 0}
    cap, _ = cf.open_capture(shared_config, 1)
    assert isinstance(cap, Dummy) and cap.opened


def test_http_backend(monkeypatch):
    monkeypatch.setattr(cf, "HttpMjpegSource", Dummy)
    shared_config["camera"] = {"mode": "http", "uri": "http://x"}
    cap, _ = cf.open_capture(shared_config, 1, capture_buffer=3, backend_priority=["http"])
    assert isinstance(cap, Dummy) and cap.opened


def test_gstreamer_fallback_unsup_codec(monkeypatch):
    class GstFail(Dummy):
        def open(self) -> None:
            raise FrameSourceError("UNSUPPORTED_CODEC")

    monkeypatch.setattr(cf, "RtspGstSource", GstFail)
    monkeypatch.setattr(cf, "RtspFfmpegSource", Dummy)
    shared_config["camera"] = {"mode": "rtsp", "uri": "rtsp://x"}
    shared_config["use_gstreamer"] = True
    cap, _ = cf.open_capture(shared_config, 1)
    assert isinstance(cap, Dummy) and cap.opened


def test_udp_retry_on_no_video(monkeypatch):
    class FailingDummy(IFrameSource):
        def __init__(self, uri: str, *, tcp: bool = True, **kwargs):
            super().__init__(uri)
            self.tcp = tcp
            self.opened = False

        def open(self) -> None:
            if self.tcp:
                raise FrameSourceError("NO_VIDEO_STREAM")
            self.opened = True

        def read(self, timeout=None):
            return None

        def info(self):
            return {}

        def close(self) -> None:
            pass

    monkeypatch.setattr(cf, "RtspFfmpegSource", FailingDummy)
    shared_config["camera"] = {"mode": "rtsp", "uri": "rtsp://x", "tcp": True}
    cap, transport = cf.open_capture(shared_config, 1)
    assert isinstance(cap, FailingDummy) and cap.opened
    assert transport == "udp"


@pytest.mark.anyio
async def test_async_open_capture(monkeypatch):
    monkeypatch.setattr(cf, "RtspFfmpegSource", Dummy)
    shared_config["camera"] = {"mode": "rtsp", "uri": "rtsp://x"}

    async def fake_probe(url):
        return url, "udp", 0, 0, 0.0

    monkeypatch.setattr(cf, "async_probe_rtsp", fake_probe)
    cap, _ = await cf.async_open_capture(shared_config, 1)
    assert isinstance(cap, Dummy) and cap.opened
