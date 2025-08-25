import sys
from pathlib import Path

import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from types import SimpleNamespace

sys.modules.setdefault(
    "cv2",
    SimpleNamespace(
        COLOR_BGR2RGB=0,
        cvtColor=lambda img, code: img,
        imwrite=lambda p, img: True,
    ),
)

from routers import cameras


def test_face_recognition_enables_counting(tmp_path, monkeypatch):
    cfg = {
        "features": {"face_recognition": True},
        "license_info": {"features": {"face_recognition": True}},
        "branding": {},
        "logo_url": "",
        "logo2_url": "",
    }
    cams = [
        {
            "id": 1,
            "name": "C1",
            "url": "u",
            "type": "http",
            "tasks": [],
            "ppe": False,
            "visitor_mgmt": False,
            "face_recognition": False,
            "enable_face_counting": False,
        }
    ]
    r = fakeredis.FakeRedis()
    cameras.init_context(cfg, cams, {}, r, str(tmp_path))
    from config import set_config

    set_config(cfg)
    app = FastAPI()
    app.post("/cameras/{cam_id}/face_recog")(cameras.toggle_face_recog)
    monkeypatch.setattr(cameras, "require_roles", lambda r, roles: True)
    client = TestClient(app)
    resp = client.post("/cameras/1/face_recog")
    assert resp.status_code == 200
    assert cams[0]["face_recognition"] is True
