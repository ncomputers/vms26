import asyncio
from types import SimpleNamespace

import routers.cameras as rc


def test_delete_camera_stops_all_trackers(monkeypatch):
    rc.cams = [{"id": 1}]
    rc.trackers_map = {1: object()}
    rc.face_trackers_map = {1: object()}
    rc.redis = None
    rc.cams_lock = asyncio.Lock()
    monkeypatch.setattr(rc, "save_cameras", lambda cams, r: None)
    monkeypatch.setattr(rc, "delete_camera_model", lambda cid, r: None)

    calls: list[tuple[str, int]] = []

    def stop_tracker(cid, trackers):
        calls.append(("person", cid))
        trackers.pop(cid, None)

    def stop_face_tracker(cid, trackers):
        calls.append(("face", cid))
        trackers.pop(cid, None)

    rc.camera_manager.stop_tracker_fn = stop_tracker
    rc.camera_manager.stop_face_tracker_fn = stop_face_tracker

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    asyncio.run(rc.delete_camera(1, SimpleNamespace()))

    assert calls == [("person", 1), ("face", 1)]
    assert rc.trackers_map == {}
    assert rc.face_trackers_map == {}
