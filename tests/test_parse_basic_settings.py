import sys

import pytest

sys.modules.setdefault("cv2", type("cv2", (), {}))

from routers import settings as settings_mod


def test_boolean_mixed_case():
    settings_mod.cfg = {"show_lines": False}
    res = settings_mod.parse_basic_settings({"show_lines": "TrUe"})
    assert res["show_lines"] is True


def test_boolean_absent_false():
    settings_mod.cfg = {"show_lines": True}
    res = settings_mod.parse_basic_settings({})
    assert res["show_lines"] is False


def test_enable_live_charts_unchecked():
    settings_mod.cfg = {"enable_live_charts": True}
    res = settings_mod.parse_basic_settings({})
    assert res["enable_live_charts"] is False


def test_track_ppe_empty_list():
    settings_mod.cfg = {"track_ppe": ["helmet"]}
    res = settings_mod.parse_basic_settings({"track_ppe": []})
    assert res["track_ppe"] == []


def test_track_ppe_absent_unchanged():
    settings_mod.cfg = {"track_ppe": ["helmet"]}
    res = settings_mod.parse_basic_settings({})
    assert res["track_ppe"] == ["helmet"]


def test_track_ppe_invalid_item():
    settings_mod.cfg = {}
    with pytest.raises(ValueError):
        settings_mod.parse_basic_settings({"track_ppe": ["invalid"]})


def test_alert_anomaly_invalid_item():
    settings_mod.cfg = {}
    with pytest.raises(ValueError):
        settings_mod.parse_basic_settings({"alert_anomalies": ["bad"]})
