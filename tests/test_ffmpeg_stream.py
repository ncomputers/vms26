"""Minimal tests for FFmpegCameraStream."""
import io
import subprocess

import numpy as np

from modules.ffmpeg_stream import FFmpegCameraStream


class DummyPopen:
    def __init__(self, *args, **kwargs):
        self.stdout = io.BytesIO(b"\x01\x02\x03" * 4)
        self.stderr = io.BytesIO()
        self._poll = None

    def poll(self):
        return self._poll

    def kill(self):
        self._poll = 0


def test_ffmpeg_stream_read(monkeypatch):
    def fake_popen(cmd, stdin=None, stdout=None, stderr=None, bufsize=None, **kwargs):
        return DummyPopen()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    stream = FFmpegCameraStream("rtsp://test", width=2, height=2, start_thread=False)
    stream.queue.append(np.zeros((2, 2, 3), dtype=np.uint8))
    ret, frame = stream.read()
    assert ret and isinstance(frame, np.ndarray)
    stream.release()


def test_ffmpeg_command_construction(monkeypatch):
    captured = {}

    def fake_popen(cmd, stdin=None, stdout=None, stderr=None, bufsize=None, **kwargs):
        captured["cmd"] = cmd
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        return DummyPopen()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    stream = FFmpegCameraStream("rtsp://demo", width=2, height=2, start_thread=False)
    stream._start_process()
    cmd = captured["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-rtsp_transport" in cmd and "tcp" in cmd
    assert "-rw_timeout" not in cmd
    assert "-vf" in cmd and f"scale={stream.width}:{stream.height}" in ",".join(cmd)
    assert captured["stdout"] is subprocess.PIPE
    assert captured["stderr"] is subprocess.DEVNULL
    stream.release()


def test_udp_transport_omits_rtsp_flags(monkeypatch):
    captured = {}

    def fake_popen(cmd, stdin=None, stdout=None, stderr=None, bufsize=None, **kwargs):
        captured["cmd"] = cmd
        return DummyPopen()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    stream = FFmpegCameraStream("rtsp://demo", width=2, height=2, transport="udp", start_thread=False)
    stream._start_process()
    cmd = captured["cmd"]
    assert "-rtsp_transport" in cmd and "udp" in cmd
    assert "-rtsp_flags" not in cmd
    stream.release()
