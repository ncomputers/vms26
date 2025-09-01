import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

# Stub heavy modules before importing startup
sys.modules.setdefault(
    "core.tracker_manager",
    types.SimpleNamespace(start_tracker=lambda *a, **k: None, start_watchdog=lambda *a, **k: None),
)
sys.modules.setdefault("modules.alerts", types.SimpleNamespace(AlertWorker=object))
sys.modules.setdefault("modules.ppe_worker", types.SimpleNamespace(PPEDetector=object))
sys.modules.setdefault("modules.tracker", types.SimpleNamespace(PersonTracker=object))
sys.modules.setdefault("modules.utils", types.SimpleNamespace(SNAP_DIR=None))
sys.modules.setdefault(
    "modules.stream_probe", types.SimpleNamespace(probe_stream=lambda *a, **k: None)
)
sys.modules.setdefault("modules.camera_factory", types.SimpleNamespace())

startup = importlib.import_module("startup")
preload_models = startup.preload_models


def test_preload_models_cpu_skips_insightface(monkeypatch):
    calls = []

    def fake_get_yolo(path, device):
        calls.append(("yolo", path))

    def fake_get_insightface(name):
        calls.append(("face", name))

    monkeypatch.setattr("startup.get_yolo", fake_get_yolo)
    monkeypatch.setattr("startup.get_insightface", fake_get_insightface)
    monkeypatch.setattr("startup.get_device", lambda device=None: SimpleNamespace(type="cpu"))

    cfg = {
        "person_model": "p.pt",
        "plate_model": "pl.pt",
    }

    cams = [{"tasks": ["in_count"]}]

    asyncio.run(preload_models(cfg, cams))

    assert ("yolo", "pl.pt") in calls
    assert not any(c == ("yolo", "p.pt") for c in calls)
    assert not any(c[0] == "face" for c in calls)
    assert cfg["features"]["face_recognition"] is False
    assert cfg["enable_person_tracking"] is False


def test_preload_models_gpu_loads_insightface(monkeypatch):
    calls = []

    def fake_get_yolo(path, device):
        calls.append(("yolo", path))

    def fake_get_insightface(name):
        calls.append(("face", name))

    monkeypatch.setattr("startup.get_yolo", fake_get_yolo)
    monkeypatch.setattr("startup.get_insightface", fake_get_insightface)
    monkeypatch.setattr("startup.get_device", lambda device=None: SimpleNamespace(type="cuda"))

    cfg = {
        "person_model": "p.pt",
        "plate_model": "pl.pt",
    }

    cams = [{"tasks": ["in_count"]}]

    asyncio.run(preload_models(cfg, cams))

    assert ("yolo", "p.pt") in calls
    assert ("yolo", "pl.pt") in calls
    assert ("face", "buffalo_l") in calls
    assert cfg.get("enable_person_tracking", True) is True


def test_preload_models_gpu_loads_insightface_face_recognition(monkeypatch):
    calls = []

    def fake_get_yolo(path, device):
        calls.append(("yolo", path))

    def fake_get_insightface(name):
        calls.append(("face", name))

    monkeypatch.setattr("startup.get_yolo", fake_get_yolo)
    monkeypatch.setattr("startup.get_insightface", fake_get_insightface)
    monkeypatch.setattr("startup.get_device", lambda device=None: SimpleNamespace(type="cuda"))

    cfg = {
        "person_model": "p.pt",
        "plate_model": "pl.pt",
        "features": {"face_recognition": True},
    }

    cams = [{"tasks": ["in_count"]}]

    asyncio.run(preload_models(cfg, cams))

    assert ("yolo", "p.pt") in calls
    assert ("yolo", "pl.pt") in calls
    assert ("face", "buffalo_l") in calls
    assert cfg["features"].get("face_recognition") is True
    assert cfg.get("enable_person_tracking", True) is True


def test_preload_models_skips_person_when_no_counting_tasks(monkeypatch):
    calls = []

    def fake_get_yolo(path, device):
        calls.append(path)

    monkeypatch.setattr("startup.get_yolo", fake_get_yolo)
    monkeypatch.setattr("startup.get_device", lambda device=None: SimpleNamespace(type="cuda"))

    cfg = {"person_model": "p.pt", "plate_model": "pl.pt", "features": {}}

    asyncio.run(preload_models(cfg, cams))

    assert calls == []
    assert cfg["enable_person_tracking"] is False


def test_preload_models_skips_person_when_features_disabled(monkeypatch):
    calls = []

    def fake_get_yolo(path, device):
        calls.append(path)

    monkeypatch.setattr("startup.get_yolo", fake_get_yolo)
    monkeypatch.setattr("startup.get_device", lambda device=None: SimpleNamespace(type="cuda"))

    cfg = {
        "person_model": "p.pt",
        "plate_model": "pl.pt",
        "features": {"in_out_counting": False, "ppe_detection": False},
    }
    cams = [{"tasks": ["in_count", "helmet"]}]

    asyncio.run(preload_models(cfg, cams))

    assert calls == []
    assert cfg["enable_person_tracking"] is False
    assert cams[0]["tasks"] == []
