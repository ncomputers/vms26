import importlib
import json
import os
import sys
import types

import pytest

from server import config as server_config


def test_early_cpu_setup_sets_env(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    monkeypatch.setenv("CONFIG_PATH", str(cfg))
    sys.modules["cv2"] = types.ModuleType("cv2")
    hardware = importlib.import_module("server.hardware")
    monkeypatch.setattr(hardware, "_calc_w", lambda w, p, c: 2)
    for var in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        monkeypatch.delenv(var, raising=False)
    hardware._early_cpu_setup()
    for var in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        assert os.environ[var] == "2"
    sys.modules.pop("cv2", None)


def test_load_secret_key(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"secret_key": "test"}))
    monkeypatch.setenv("CONFIG_PATH", str(cfg))
    assert server_config._load_secret_key() == "test"


def test_connect_redis(monkeypatch):
    client = object()

    def fake_client(url):
        assert url == "redis://localhost"
        return client

    monkeypatch.setattr(server_config.redis_utils, "get_sync_client", fake_client)
    assert server_config._connect_redis("redis://localhost") is client


def test_load_camera_profiles(monkeypatch):
    class DummyRedis:
        def __init__(self):
            self.store = {}

        def get(self, key):
            return self.store.get(key)

        def set(self, key, value):
            self.store[key] = value

    cams = [{"id": 1}]

    def fake_load(redis_client, default_url):
        assert default_url == ""
        return cams

    monkeypatch.setattr(server_config, "load_cameras", fake_load)
    redis_client = DummyRedis()
    cfg = {"stream_url": ""}
    assert server_config._load_camera_profiles(redis_client, cfg, None) == cams
