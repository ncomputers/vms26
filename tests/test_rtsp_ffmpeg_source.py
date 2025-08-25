import io
import logging
import subprocess
import pytest

from modules.capture.rtsp_ffmpeg import RtspFfmpegSource
from modules.capture import FrameSourceError


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
