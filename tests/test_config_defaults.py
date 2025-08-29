import fakeredis

from config import CONFIG_DEFAULTS
from config.storage import load_config


def test_load_config_populates_defaults(tmp_path):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text('{"redis_url": "redis://localhost:6379/0"}')
    r = fakeredis.FakeRedis()
    cfg = load_config(str(cfg_path), r)
    assert cfg["frame_skip"] == CONFIG_DEFAULTS["frame_skip"]
    assert cfg["ffmpeg_flags"] == CONFIG_DEFAULTS["ffmpeg_flags"]
    assert cfg["detector_fps"] == CONFIG_DEFAULTS["detector_fps"]
    assert cfg["adaptive_skip"] == CONFIG_DEFAULTS["adaptive_skip"]
    assert cfg["track_max_age"] == CONFIG_DEFAULTS["track_max_age"]
    assert cfg["cross_hysteresis"] == CONFIG_DEFAULTS["cross_hysteresis"]
    assert cfg["track_max_age"] == CONFIG_DEFAULTS["track_max_age"]
    assert cfg["cross_min_travel_px"] == CONFIG_DEFAULTS["cross_min_travel_px"]
    assert cfg["cross_min_frames"] == CONFIG_DEFAULTS["cross_min_frames"]
