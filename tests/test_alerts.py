"""Purpose: Test alerts module."""

import asyncio
import json
import time
from pathlib import Path

import fakeredis
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from modules import alerts as alerts_module
from routers import alerts


# DummyRequest class encapsulates dummyrequest behavior
class DummyRequest:
    # __init__ routine
    def __init__(self, data=None):
        self.session = {"user": {"role": "admin"}}
        self._data = data or {}

    async def json(self):
        return self._data


# Test alerts page metrics
def test_alerts_page_metrics(tmp_path):
    cfg = {"alert_rules": [], "email": {}, "features": {}}
    r = fakeredis.FakeRedis()
    (tmp_path / "email_alerts.html").write_text(
        '<button id="toggleMetrics"></button><span id="metric_person_in"></span>{{ anomaly_items }}'
    )
    alerts.init_context(cfg, {}, r, str(tmp_path), str(tmp_path / "cfg.json"))
    req = DummyRequest()
    resp = asyncio.run(alerts.alerts_page(req))
    html = resp.body.decode()
    assert "visitor_registered" in html
    assert 'id="toggleMetrics"' in html


def test_alert_worker_threshold(tmp_path, monkeypatch):
    calls = []

    def mock_send(*a, **k):
        calls.append(a)
        return True, None

    monkeypatch.setattr(alerts_module, "send_email", mock_send)
    r = fakeredis.FakeRedis()
    now = int(time.time())
    cfg = {
        "alert_rules": [
            {
                "metric": "no_helmet",
                "type": "threshold",
                "value": 2,
                "window": 1,
                "recipients": "a@example.com",
            }
        ],
        "email": {},
        "email_enabled": True,
    }
    worker = alerts_module.AlertWorker(cfg, "redis://localhost", tmp_path, start=False)
    worker.redis = r
    r.zadd(
        "ppe_logs",
        {
            json.dumps({"ts": now - 30, "status": "no_helmet"}): now - 30,
            json.dumps({"ts": now - 10, "status": "no_helmet"}): now - 10,
        },
    )
    worker.check_rules()
    assert calls
    assert int(worker.redis.get("alert_rule_0_last") or 0) > 0


def test_save_alerts_validation(client):
    resp = client.post(
        "/alerts",
        json={"rules": [{"metric": "bad", "value": 1, "recipients": "a@example.com"}]},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/alerts",
        json={"rules": [{"metric": "no_helmet", "value": 0, "recipients": "a@example.com"}]},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/alerts",
        json={"rules": [{"metric": "no_helmet", "value": 1, "recipients": "bad"}]},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/alerts",
        json={
            "rules": [
                {
                    "metric": "no_helmet",
                    "type": "threshold",
                    "value": 1,
                    "window": 3,
                    "recipients": "a@example.com",
                }
            ]
        },
    )
    assert resp.status_code == 400
    ok = client.post(
        "/alerts",
        json={"rules": [{"metric": "no_helmet", "value": 1, "recipients": "a@example.com"}]},
    )
    assert ok.status_code == 200 and ok.json()["saved"]


def test_update_email_validation(client):
    resp = client.post("/email", json={"from_addr": "not-an-email"})
    assert resp.status_code == 400
    ok = client.post("/email", json={"from_addr": "test@example.com"})
    assert ok.status_code == 200 and ok.json()["saved"]


def test_consume_events_triggers_check_rules(tmp_path, monkeypatch):
    worker = alerts_module.AlertWorker({}, None, tmp_path, start=False)
    called = []

    monkeypatch.setattr(worker, "check_rules", lambda: called.append(True))

    class DummyPubSub:
        def get_message(self, timeout=1):
            return {"type": "message"}

    worker._consume_events(DummyPubSub())
    assert called


def test_run_periodic_tasks_executes(tmp_path, monkeypatch):
    worker = alerts_module.AlertWorker({}, None, tmp_path, start=False)
    calls = []

    monkeypatch.setattr(worker, "check_rules", lambda: calls.append("rules"))
    monkeypatch.setattr(worker, "check_overdue_gatepasses", lambda: calls.append("gate"))
    monkeypatch.setattr(worker, "_log_cycle", lambda elapsed: calls.append(elapsed))

    last = 0
    now = 61
    new_last = worker._run_periodic_tasks(now, last)
    assert calls == ["rules", "gate", 61]
    assert new_last == now


def test_handle_loop_error_logs_exception(tmp_path, monkeypatch):
    worker = alerts_module.AlertWorker({}, None, tmp_path, start=False)
    captured = {}

    def fake_exception(msg, exc):
        captured["exc"] = exc

    monkeypatch.setattr(alerts_module.logger, "exception", fake_exception)
    err = ValueError("boom")
    worker._handle_loop_error(err)
    assert captured["exc"] is err
