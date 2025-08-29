import sys
import types

import pytest

sys.modules.setdefault("cv2", types.SimpleNamespace())


@pytest.fixture(autouse=True, scope="session")
def _patch_health_loop():
    import routers.cameras as cam

    if not hasattr(cam, "_health_loop"):
        cam._health_loop = lambda: None


def test_email_test_uses_payload_config(client, monkeypatch):
    from routers import settings

    ctx = settings.get_settings_context()
    monkeypatch.setitem(ctx.cfg, "email", {})

    captured = {}

    def fake_send_email(*args, **kwargs):
        captured.update(kwargs.get("cfg", {}))
        return True, "", None, None

    monkeypatch.setattr("routers.settings.send_email", fake_send_email)

    payload = {
        "recipient": "to@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_user": "user",
        "smtp_pass": "pass",
        "from_addr": "from@example.com",
    }

    r = client.post("/settings/email/test", json=payload)
    assert r.status_code == 200
    assert r.json() == {"sent": True}
    assert captured["smtp_host"] == "smtp.example.com"
    assert captured["smtp_port"] == 587
    assert captured["use_tls"] is True
    assert captured["from_addr"] == "from@example.com"


def test_email_test_sets_last_ts_allows_save(client, monkeypatch):
    from routers import settings

    ctx = settings.get_settings_context()
    monkeypatch.setitem(ctx.cfg, "email", {})
    monkeypatch.setitem(ctx.cfg, "settings_password", "pass")

    monkeypatch.setattr("routers.settings.save_config", lambda *a, **k: None)
    monkeypatch.setattr("routers.settings.save_branding", lambda *a, **k: None)
    monkeypatch.setattr("routers.settings.start_profiler", lambda *a, **k: None)
    monkeypatch.setattr("routers.settings.send_email", lambda *a, **k: (True, "", None, None))

    payload = {"recipient": "to@example.com", "smtp_host": "smtp.example.com"}
    r = client.post("/settings/email/test", json=payload)
    assert r.status_code == 200
    assert r.json() == {"sent": True}
    assert ctx.cfg["email"]["last_test_ts"] > 0

    resp = client.post(
        "/settings",
        data={
            "password": "pass",
            "email_enabled": "true",
            "smtp_host": "smtp.example.com",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["saved"] is True
