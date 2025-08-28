import numpy as np
import pytest

from modules.camera_manager import CameraManager


@pytest.mark.asyncio
async def test_frame_cache_is_instance_scoped():
    cams = [{"id": 1, "url": "", "tasks": []}]
    trackers1 = {}
    trackers2 = {}
    start = lambda cam, cfg, trackers, r: None
    stop = lambda cid, tr: None

    mgr1 = CameraManager({}, trackers1, {}, None, lambda: cams, start, stop)
    mgr2 = CameraManager({}, trackers2, {}, None, lambda: cams, start, stop)

    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    await mgr1._update_latest(1, frame)

    assert 1 in mgr1._latest_frames
    assert 1 not in mgr2._latest_frames


def test_build_flags():
    cams = []
    trackers = {}
    start = lambda cam, cfg, trackers, r: None
    stop = lambda cid, tr: None
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
