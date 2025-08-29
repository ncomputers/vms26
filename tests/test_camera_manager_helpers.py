import asyncio

import numpy as np
import pytest

from core.camera_manager import CameraManager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_snapshot_uses_cached_frame():
    cams = [{"id": 1, "url": "", "tasks": []}]
    trackers = {}

    def start(cam, cfg, trackers, r, cb=None):
        return None

    def stop(cid, tr):
        return None

    mgr = CameraManager({}, trackers, {}, None, lambda: cams, start, stop)

    frame = np.ones((2, 2, 3), dtype=np.uint8)
    mgr.update_latest_frame(1, frame)
    await asyncio.sleep(0.01)

    ok, got, detail = await mgr.snapshot(1)
    assert ok is True
    assert detail == "from_cache"
    assert np.array_equal(got, frame)
