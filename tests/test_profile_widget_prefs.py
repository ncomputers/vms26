import asyncio
import json

import fakeredis

import routers.profile as profile
from config.storage import load_config


def test_widget_prefs_persist(tmp_path):
    cfg = {"redis_url": "redis://localhost:6379/0"}
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    r = fakeredis.FakeRedis()
    profile.init_context(cfg, r, str(tmp_path), str(cfg_path))
    prefs = {"a": True, "b": False}
    asyncio.run(profile.save_widget_prefs(prefs))
    loaded = load_config(str(cfg_path), r)
    assert loaded["widget_prefs"] == prefs
