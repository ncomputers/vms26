import io
import os
import subprocess

from modules.capture.rtsp_ffmpeg import RtspFfmpegSource


def test_drain_stderr_handles_proc_termination(monkeypatch):
    r_fd, w_fd = os.pipe()
    stderr_reader = os.fdopen(r_fd, "rb", buffering=0)

    class DummyProc:
        def __init__(self):
            self.stdout = io.BytesIO()
            self.stderr = stderr_reader

        def terminate(self):
            pass

    def fake_popen(cmd, stdout=None, stderr=None, bufsize=None):
        return DummyProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    src = RtspFfmpegSource("rtsp://demo")
    src.open()
    os.close(w_fd)
    if src._stderr_thread:
        src._stderr_thread.join(timeout=1)
    src._stop_proc()
    src.close()
