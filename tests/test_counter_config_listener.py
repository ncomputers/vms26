import asyncio
from contextlib import suppress

import fakeredis

from config import set_config
from core.tracker_manager import counter_config_listener
from modules.tracker import PersonTracker


def test_counter_config_updates_tracker():
    r = fakeredis.FakeRedis()
    set_config({"track_objects": []})
    tr = PersonTracker.__new__(PersonTracker)
    tr.cam_id = 1
    tr.line_orientation = "vertical"
    tr.line_ratio = 0.5
    tr.groups = ["person"]
    tr.in_counts = {"person": 0}
    tr.out_counts = {"person": 0}
    tr.key_in = "person_tracker:cam:1:in"
    tr.key_out = "person_tracker:cam:1:out"
    tr.redis = r
    tr.cfg = {}
    trackers = {1: tr}

    async def run_test():
        task = asyncio.create_task(counter_config_listener(r, trackers))
        await asyncio.sleep(0.05)
        r.hset(
            "cam:1:line",
            mapping={"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0, "orientation": "horizontal"},
        )
        r.sadd("cam:1:vehicle_classes", "car")
        r.publish("counter.config", "cam:1")
        await asyncio.sleep(0.1)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    asyncio.run(run_test())
    assert tr.line_orientation == "horizontal"
    assert "person" in tr.groups and "vehicle" in tr.groups
