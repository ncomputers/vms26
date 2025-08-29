import asyncio
import asyncio
import sys
import types
import time
import numpy as np

sys.modules.setdefault("cv2", types.SimpleNamespace())
from routers import cameras
from modules.capture.base import FrameSourceError


def setup_function():
    cameras.cams = []


def test_mjpeg_stream(monkeypatch):
    cameras.cams = [{"id": 1, "url": "rtsp://example/stream"}]
    monkeypatch.setattr(cameras, "require_roles", lambda *a, **k: None)

    class FakeCap:
        def __init__(self):
            self.frames = [np.zeros((1, 1, 3), dtype=np.uint8), np.ones((1, 1, 3), dtype=np.uint8)]
            self.idx = 0
            self.last_frame_ts = 0.0
            self.restarts = 0

        def read(self, timeout=None):
            if self.idx >= len(self.frames):
                raise FrameSourceError("READ_TIMEOUT")
            frame = self.frames[self.idx]
            self.idx += 1
            self.last_frame_ts = time.time()
            return frame

    fake_cap = FakeCap()

    async def fake_get_cap(cam):
        return fake_cap

    monkeypatch.setattr(cameras, "_get_preview_cap", fake_get_cap)

    def fake_imencode(ext, frame, params):
        return True, np.frombuffer(b"\xff\xd8test\xff\xd9", dtype=np.uint8)

    monkeypatch.setattr(cameras.cv2, "imencode", fake_imencode, raising=False)
    monkeypatch.setattr(cameras.cv2, "IMWRITE_JPEG_QUALITY", 1, raising=False)
    monkeypatch.setattr(cameras, "require_roles", lambda *a, **k: None)

    async def _run():
        resp = await cameras.camera_mjpeg(1)
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "multipart/x-mixed-replace; boundary=frame"
        )
        gen = resp.body_iterator
        first = await gen.__anext__()
        second = await gen.__anext__()
        assert b"\xff\xd8" in first
        assert b"\xff\xd8" in second
        await gen.aclose()

    asyncio.run(_run())
