import sys
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

sys.modules.setdefault(
    "cv2",
    SimpleNamespace(
        COLOR_BGR2RGB=0,
        cvtColor=lambda img, code: img,
        Laplacian=lambda img, mode: np.zeros_like(img),
    ),
)

import asyncio  # noqa: E402

from core import events  # noqa: E402
from core.camera_manager import CameraManager  # noqa: E402
from modules import face_db  # noqa: E402
from modules.tracker.face_tracker import FaceTracker  # noqa: E402


def _make_detector(dets):
    class D:
        def __init__(self):
            self.dets = list(dets)

        def detect(self, frame):
            if not self.dets:
                return []
            x1, y1, x2, y2, s = self.dets.pop(0)
            return [SimpleNamespace(bbox=(x1, y1, x2, y2), det_score=s)]

    return D()


def _make_model(out):
    class M:
        def __init__(self):
            self.out = list(out)

        def get(self, crop):
            if not self.out:
                return []
            data = self.out.pop(0)
            return [SimpleNamespace(**data)]

    return M()


def test_face_tracker_flow(monkeypatch):
    r = fakeredis.FakeRedis(decode_responses=True)
    face_db.redis_client = r
    times = [0, 1, 2]
    monkeypatch.setattr(
        "modules.tracker.face_tracker.time", SimpleNamespace(time=lambda: times.pop(0))
    )
    sharp = [0.1, 0.9, 0.9]
    monkeypatch.setattr(
        "modules.tracker.face_tracker._sharpness", lambda img: sharp.pop(0)
    )
    monkeypatch.setattr("modules.tracker.face_tracker._frontalness", lambda face: 0.5)
    det = _make_detector(
        [
            (20, 10, 50, 40, 0.8),
            (30, 10, 60, 40, 0.9),
            (20, 10, 50, 40, 0.9),
        ]
    )
    emb = np.ones(512, dtype=np.float32)
    model = _make_model(
        [
            {"embedding": emb, "match_score": 0.5},
            {"embedding": emb, "match_score": 0.5},
            {"embedding": emb, "match_score": 0.5},
        ]
    )
    ft = FaceTracker(1, {"cpu_sample_every": 1, "min_face_size": 10}, r)
    ft.detector = det
    ft.model = model
    frame = np.zeros((80, 80, 3), dtype=np.uint8)

    ft.process_frame(frame)
    tid = next(iter(ft.tracks))
    first_best = ft.tracks[tid]["best_q"]
    img1 = ft.tracks[tid]["best_img_ref"]

    ft.process_frame(frame)  # crosses line
    track = ft.tracks[tid]
    assert track["best_q"] > first_best
    assert track["best_img_ref"] != img1

    events_list = r.xrange("attendance:events", "-", "+")
    assert len(events_list) == 1
    payload = {
        (k.decode() if isinstance(k, bytes) else k): (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in events_list[0][1].items()
    }
    assert payload["event"] == events.FACE_IN
    assert payload["camera_id"] == "1"
    assert payload["tid"] == str(tid)
    assert r.get("stats:face_in:1") == "1"

    uuid = track["temp_uuid"]
    stored = r.hgetall(f"face:temp:{uuid}")
    assert stored["camera_id"] == "1"
    assert r.zscore("faces:unlabeled", uuid) is not None

    ft.process_frame(frame)  # crosses back quickly, logs opposite direction
    assert r.xlen("attendance:events") == 2


def test_camera_manager_starts_face_tracker():
    cams = [{"id": 1, "face_recognition": True, "url": "", "type": "http", "tasks": []}]

    async def run():
        r = fakeredis.FakeRedis(decode_responses=True)
        mgr = CameraManager(
            {},
            {},
            {},
            r,
            lambda: cams,
            lambda cam, cfg, tr, r, cb=None: tr.setdefault(cam["id"], object()),
            lambda cid, tr: tr.pop(cid, None),
            lambda cam, cfg, tr, r, cb=None: tr.setdefault(cam["id"], object()),
            lambda cid, tr: tr.pop(cid, None),
        )
        await mgr._start_tracker_background(cams[0])
        return mgr

    mgr = asyncio.run(run())
    assert 1 in mgr.face_trackers
