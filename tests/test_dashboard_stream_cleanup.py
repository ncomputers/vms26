import asyncio
import sys

import numpy as np
from starlette.requests import Request

sys.modules.setdefault(
    "cv2", type("cv2", (), {"imencode": lambda *a, **k: (True, np.array([0], dtype=np.uint8))})
)

from routers.dashboard import stream_preview


class DummyProc:
    def __init__(self):
        self.killed = False

    def kill(self):
        self.killed = True


class DummyTracker:
    def __init__(self):
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        self.output_frame = frame
        self.raw_frame = frame
        self.fps = 1
        self.viewers = 0
        self.restart_capture = False
        self.proc = DummyProc()


def test_stream_preview_proc_kill(monkeypatch):
    tracker = DummyTracker()
    monkeypatch.setattr("routers.dashboard.require_roles", lambda request, roles: {})

    async def _run():
        req = Request({"type": "http", "session": {"user": {"role": "viewer"}}})
        resp = await stream_preview(1, req, {1: tracker})
        gen = resp.body_iterator
        await gen.__anext__()
        await gen.aclose()
        assert tracker.proc.killed

    asyncio.run(_run())
