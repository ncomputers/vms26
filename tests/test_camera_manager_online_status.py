import asyncio
from types import SimpleNamespace

import fakeredis

from core.camera_manager import CameraManager


def test_start_tracker_sets_redis_online():
    r = fakeredis.FakeRedis(decode_responses=True)
    trackers = {}
    cams = [{"id": 1, "url": "", "type": "http", "tasks": []}]

    def start_tracker(cam, cfg, trackers_map, redis, cb=None):
        tr = SimpleNamespace(online=True)
        trackers_map[cam["id"]] = tr
        return tr

    mgr = CameraManager(
        {},
        trackers,
        {},
        r,
        lambda: cams,
        start_tracker,
        lambda cid, tr: None,
    )

    r.hset("camera:1:health", mapping={"status": "offline"})
    r.hset("camera:1", "status", "offline")

    asyncio.run(mgr._start_tracker_background(cams[0]))

    assert trackers[1].online is True
    assert r.hget("camera:1", "status") == "online"
    assert r.hget("camera:1:health", "status") == "online"
