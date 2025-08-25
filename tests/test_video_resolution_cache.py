"""Tests for cached stream resolution probing."""

import json
import types

from utils import video


def test_get_stream_resolution_cache(monkeypatch):
    video._RES_CACHE.clear()
    calls = {"count": 0}

    def fake_run(cmd, capture_output, text, check, timeout):
        calls["count"] += 1
        data = {"streams": [{"width": 100, "height": 200}]}
        return types.SimpleNamespace(stdout=json.dumps(data))

    monkeypatch.setattr(video.subprocess, "run", fake_run)

    url = "rtsp://example"
    assert video.get_stream_resolution(url, cache_seconds=60) == (100, 200)
    # second call uses cache
    assert video.get_stream_resolution(url, cache_seconds=60) == (100, 200)
    assert calls["count"] == 1

    # invalidate forces a re-probe
    assert video.get_stream_resolution(url, cache_seconds=60, invalidate=True) == (
        100,
        200,
    )
    assert calls["count"] == 2


def test_rtsp_uses_tcp_transport(monkeypatch):
    video._RES_CACHE.clear()
    captured = {}

    def fake_run(cmd, capture_output, text, check, timeout):
        captured["cmd"] = cmd
        data = {"streams": [{"width": 100, "height": 200}]}
        return types.SimpleNamespace(stdout=json.dumps(data))

    monkeypatch.setattr(video.subprocess, "run", fake_run)

    video.get_stream_resolution("rtsp://example")
    assert captured["cmd"][1:3] == ["-rtsp_transport", "tcp"]


def test_get_stream_resolution_cache_expiry(monkeypatch):
    video._RES_CACHE.clear()
    calls = {"count": 0}
    now = [0]

    def fake_run(cmd, capture_output, text, check, timeout):
        calls["count"] += 1
        data = {"streams": [{"width": 100, "height": 200}]}
        return types.SimpleNamespace(stdout=json.dumps(data))

    def fake_monotonic():
        return now[0]

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    monkeypatch.setattr(video.time, "monotonic", fake_monotonic)

    url = "rtsp://example"
    assert video.get_stream_resolution(url, cache_seconds=1) == (100, 200)
    assert video.get_stream_resolution(url, cache_seconds=1) == (100, 200)
    assert calls["count"] == 1

    # advance time beyond TTL
    now[0] += 2
    assert video.get_stream_resolution(url, cache_seconds=1) == (100, 200)
    assert calls["count"] == 2
