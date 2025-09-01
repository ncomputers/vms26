import asyncio

from routers import cameras


def setup_function():
    cameras.cams = []
    cameras.preview_publisher = cameras.preview_publisher.__class__()
    cameras.rtsp_connectors = {}


def test_mjpeg_stream(monkeypatch):
    cameras.cams = [{"id": 1, "url": "rtsp://example/stream"}]
    monkeypatch.setattr(cameras, "require_roles", lambda *a, **k: None)

    class FakePub:
        def __init__(self):
            self.shown = set()

        def start_show(self, cid):
            self.shown.add(cid)

        def stop_show(self, cid):
            self.shown.discard(cid)

        def is_showing(self, cid):
            return cid in self.shown

        async def stream(self, cid):
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nA\r\n"
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\nB\r\n"

    cameras.preview_publisher = FakePub()

    async def _run():
        resp = await cameras.camera_mjpeg(1)
        assert resp.status_code == 200
        gen = resp.body_iterator
        first = await gen.__anext__()
        second = await gen.__anext__()
        assert b"A" in first and b"B" in second
        await gen.aclose()

    asyncio.run(_run())


def test_show_hide_and_stats(monkeypatch):
    cameras.cams = [{"id": 1, "url": "rtsp://example/stream"}]
    monkeypatch.setattr(cameras, "require_roles", lambda *a, **k: None)

    class FakePub:
        def __init__(self):
            self.shown = set()

        def start_show(self, cid):
            self.shown.add(cid)

        def stop_show(self, cid):
            self.shown.discard(cid)

        def is_showing(self, cid):
            return cid in self.shown

        async def stream(self, cid):
            yield b""

    cameras.preview_publisher = FakePub()

    class FakeConn:
        def __init__(self):
            self.started = 0
            self.stopped = 0

        def start(self):
            self.started += 1

        def stop(self):
            self.stopped += 1

        def stats(self):
            return {"state": "ok"}

    fake_conn = FakeConn()
    cameras.rtsp_connectors = {1: fake_conn}

    async def _run():
        await cameras.camera_show(1)
        assert cameras.preview_publisher.is_showing(1)
        stats = await cameras.camera_stats(1)
        assert stats["preview"] is True
        assert stats["state"] == "ok"
        await cameras.camera_hide(1)
        assert not cameras.preview_publisher.is_showing(1)
        stats2 = await cameras.camera_stats(1)
        assert stats2["preview"] is False
        assert fake_conn.started == 0 and fake_conn.stopped == 0

    asyncio.run(_run())
