import asyncio
import io
import subprocess
import sys
import types

sys.modules.setdefault("cv2", types.SimpleNamespace())
from routers import cameras
from modules.email_utils import sign_token


class FakeProc:
    def __init__(self, data: bytes):
        self.stdout = io.BytesIO(data)
        self.killed = False

    def kill(self):
        self.killed = True


def setup_function():
    cameras.cams = []


def test_mjpeg_stream(monkeypatch):
    cameras.cams = [{"id": 1, "url": "rtsp://example/stream"}]
    monkeypatch.setattr(cameras, "require_roles", lambda *a, **k: None)

    proc = FakeProc(b"\xff\xd8test\xff\xd9")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: proc)

    async def _run():
        tok = sign_token("1", cameras.cfg.get("secret_key", "secret"))
        resp = await cameras.camera_mjpeg(1, token=tok)
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
        )
        gen = resp.body_iterator
        first = await gen.__anext__()
        assert b"\xff\xd8" in first
        await gen.aclose()
        assert proc.killed

    asyncio.run(_run())
