from datetime import datetime

import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.events_store import RedisStore
from routers import api_summary
from utils.deps import get_redis


def test_summary_fallback_to_events():
    r = fakeredis.FakeRedis(decode_responses=True)
    app = FastAPI()
    app.dependency_overrides[get_redis] = lambda: r
    app.include_router(api_summary.router)
    client = TestClient(app)

    r.hset(
        "summaries:2024-01-01",
        mapping={"in_person": 5, "out_person": 3, "in_vehicle": 2, "out_vehicle": 1},
    )
    store = RedisStore(r)
    ts = int(datetime(2024, 1, 2, 12, 0, 0).timestamp())
    for track_id in range(2):
        store.persist_event(
            ts_utc=ts + track_id,
            ts_local="2024-01-02T12:00:00",
            camera_id=1,
            camera_name="cam",
            track_id=track_id,
            direction="in",
            label="person",
            image_path=None,
            thumb_path=None,
        )
    store.persist_event(
        ts_utc=ts + 2,
        ts_local="2024-01-02T12:00:02",
        camera_id=1,
        camera_name="cam",
        track_id=99,
        direction="out",
        label="person",
        image_path=None,
        thumb_path=None,
    )
    store.persist_event(
        ts_utc=ts + 3,
        ts_local="2024-01-02T12:00:03",
        camera_id=1,
        camera_name="cam",
        track_id=100,
        direction="in",
        label="car",
        image_path=None,
        thumb_path=None,
    )

    resp = client.get(
        "/api/v1/summary",
        params={
            "from": "2024-01-01",
            "to": "2024-01-02",
            "group": "person,vehicle",
            "metric": "in,out",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "person": {"in": 7, "out": 4},
        "vehicle": {"in": 3, "out": 1},
    }
