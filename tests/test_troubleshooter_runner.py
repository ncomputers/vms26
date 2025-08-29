import json
import multiprocessing as mp

from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

import routers.troubleshooter as ts
from modules.troubleshooter_runner import _run_stage


def _cameras():
    return [{"id": 1, "url": "rtsp://localhost/test"}]


def _app(monkeypatch):
    app = FastAPI()
    app.include_router(ts.router)
    app.state.cameras = _cameras()
    return app


def test_troubleshooter_runner_stream(monkeypatch):
    monkeypatch.setenv("TROUBLESHOOTER_DRY_RUN_SECS", "0")
    client = TestClient(_app(monkeypatch))
    res = client.get("/troubleshooter/start", params={"camera_id": 1})
    assert res.status_code == 200
    run_id = res.json()["run_id"]
    assert run_id

    with client.stream("GET", "/troubleshooter/stream", params={"run_id": run_id}) as resp:
        events = []
        for line in resp.iter_lines():
            if not line:
                continue
            assert line.startswith("data: ")
            payload = json.loads(line[6:])
            events.append(payload)
            if payload.get("stage") == "complete":
                break
    stages = [e["stage"] for e in events]
    assert stages[0] == "ping"
    assert stages[-1] == "complete"


def test_run_stage_logs(caplog):
    logger.remove()
    logger.add(caplog.handler, level="INFO")
    q = mp.Queue()
    assert _run_stage("test", lambda: None, q)
    assert '"stage": "test"' in caplog.text
