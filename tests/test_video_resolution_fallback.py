import logging
import subprocess

import utils.video as video


def test_get_stream_resolution_calledprocesserror(monkeypatch, caplog):
    video._RES_CACHE.clear()

    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(video.subprocess, "run", _raise)
    with caplog.at_level(logging.WARNING):
        res = video.get_stream_resolution("rtsp://example")
    assert res == (640, 480)
    assert "CalledProcessError" in caplog.text


def test_get_stream_resolution_oserror(monkeypatch, caplog):
    video._RES_CACHE.clear()

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(video.subprocess, "run", _raise)
    with caplog.at_level(logging.WARNING):
        res = video.get_stream_resolution("rtsp://example")
    assert res == (640, 480)
    assert "OSError" in caplog.text


def test_get_stream_resolution_valueerror(monkeypatch, caplog):
    video._RES_CACHE.clear()

    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"streams":[{"width":"bad","height":480}]}',
            stderr="",
        )

    monkeypatch.setattr(video.subprocess, "run", _run)
    with caplog.at_level(logging.WARNING):
        res = video.get_stream_resolution("rtsp://example")
    assert res == (640, 480)
    assert "ValueError" in caplog.text


def test_fallback_ttl(monkeypatch):
    video._RES_CACHE.clear()
    calls = {"count": 0}
    now = [0]

    def fake_run(cmd, capture_output, text, check, timeout):
        calls["count"] += 1
        raise subprocess.CalledProcessError(1, cmd)

    def fake_monotonic():
        return now[0]

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    monkeypatch.setattr(video.time, "monotonic", fake_monotonic)

    url = "rtsp://example"
    video.get_stream_resolution(url, fallback_ttl=1)
    # Cached fallback prevents second call
    video.get_stream_resolution(url, fallback_ttl=1)
    assert calls["count"] == 1
    # Expire cache and retry
    now[0] += 2
    video.get_stream_resolution(url, fallback_ttl=1)
    assert calls["count"] == 2
