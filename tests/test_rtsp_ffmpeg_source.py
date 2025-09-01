import io
import logging
import subprocess
import threading

import pytest

from modules.capture import FrameSourceError
from modules.capture.rtsp_ffmpeg import RtspFfmpegSource


def test_stderr_capture_and_close(monkeypatch, caplog):
    class DummyProc:
        def __init__(self):
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO(b"line1\nline2\n")

        def terminate(self):
            pass

    dummy = DummyProc()

    def fake_popen(cmd, stdout=None, stderr=None, bufsize=None):
        return dummy

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    src = RtspFfmpegSource("rtsp://demo")
    src.open()
    if src._stderr_thread:
        src._stderr_thread.join(timeout=1)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(FrameSourceError):
            src.read()
    assert "line1" in src.last_stderr
    assert any("line1" in r.message for r in caplog.records)
    src.close()
    assert dummy.stdout.closed and dummy.stderr.closed


def test_startup_cmd_excludes_rw_timeout(monkeypatch):
    class DummyProc:
        def __init__(self):
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()

        def terminate(self):
            pass

    captured: dict[str, list[str]] = {}

    def fake_popen(cmd, stdout=None, stderr=None, bufsize=None):
        captured["cmd"] = cmd
        return DummyProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    src = RtspFfmpegSource("rtsp://demo")
    src.open()
    assert "cmd" in captured and "-rw_timeout" not in captured["cmd"]
    src.close()


def test_restart_attempt_threshold(monkeypatch):
    src = RtspFfmpegSource("rtsp://user:pass@host")
    src._stop_event = threading.Event()
    src._stderr_buffer.append("rtsp://user:pass@host error")

    monkeypatch.setattr(src, "_stop_proc", lambda: None)
    monkeypatch.setattr(src, "_start_proc", lambda: None)

    for _ in range(5):
        src._restart_proc()
    with pytest.raises(FrameSourceError) as exc:
        src._restart_proc()
    assert "CONNECT_FAILED" in str(exc.value)
    assert "***:***@" in str(exc.value)


def test_operation_not_permitted_error(monkeypatch):
    src = RtspFfmpegSource("rtsp://demo")
    src._stderr_buffer.append("Operation not permitted")
    src._stop_event = threading.Event()
    monkeypatch.setattr(src, "_stop_proc", lambda: None)
    monkeypatch.setattr(src, "_start_proc", lambda: None)
    with pytest.raises(FrameSourceError) as exc:
        src._restart_proc()
    msg = str(exc.value).lower()
    assert "connect_failed" in msg
    assert "operation not permitted" in msg
    assert "firewall" in msg
