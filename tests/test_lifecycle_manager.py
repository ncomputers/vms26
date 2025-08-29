import signal
import time
import types

import pytest

from app.core.lifecycle import LifecycleManager


def test_register_signal_handlers_idempotent(monkeypatch):
    mgr = LifecycleManager()
    calls = []

    def fake_signal(sig, handler):
        calls.append(sig)

    monkeypatch.setattr("signal.signal", fake_signal)
    mgr.register_signal_handlers()
    mgr.register_signal_handlers()
    assert calls.count(signal.SIGINT) == 1
    assert calls.count(signal.SIGTERM) == 1


def test_watchdog_start_stop():
    mgr = LifecycleManager()
    dummy = types.SimpleNamespace(
        process=types.SimpleNamespace(last_processed_ts=time.time()), cam_cfg={}
    )
    mgr.register_pipeline(dummy)
    assert mgr._watchdog is not None
    mgr.unregister_pipeline(dummy)
    assert mgr._watchdog is None
