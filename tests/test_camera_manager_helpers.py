import numpy as np
import pytest

from core.camera_manager import CameraManager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_frame_cache_is_instance_scoped():
    cams = [{"id": 1, "url": "", "tasks": []}]
    trackers1 = {}
    trackers2 = {}

    def start(cam, cfg, trackers, r, cb=None):
        return None

    def stop(cid, tr):
        return None

    mgr1 = CameraManager({}, trackers1, {}, None, lambda: cams, start, stop)
    mgr2 = CameraManager({}, trackers2, {}, None, lambda: cams, start, stop)

    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    await mgr1._update_latest(1, frame)

    assert 1 in mgr1._latest_frames
    assert 1 not in mgr2._latest_frames


async def test_build_flags():
    cams = []
    trackers = {}

    def start(cam, cfg, trackers, r, cb=None):
        return None

    def stop(cid, tr):
        return None

    mgr = CameraManager({}, trackers, {}, None, lambda: cams, start, stop)

    cam = {
        "enabled": False,
        "ppe": True,
        "visitor_mgmt": True,
        "face_recognition": True,
        "tasks": ["in_count"],
    }
    flags = mgr._build_flags(cam)
    assert flags == {
        "enabled": False,
        "ppe": True,
        "vms": True,
        "face": True,
        "counting": True,
    }


async def test_snapshot_uses_cached_frame():
    cams = [{"id": 1, "url": "", "tasks": []}]
    trackers = {}

    def start(cam, cfg, trackers, r, cb=None):
        return None

    def stop(cid, tr):
        return None

    mgr = CameraManager({}, trackers, {}, None, lambda: cams, start, stop)

    frame = np.ones((2, 2, 3), dtype=np.uint8)
    await mgr._update_latest(1, frame)

    ok, got, detail = await mgr.snapshot(1)
    assert ok is True
    assert detail == "from_cache"
    assert np.array_equal(got, frame)
