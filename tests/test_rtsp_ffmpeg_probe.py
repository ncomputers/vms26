import logging

import ffmpeg

from modules.capture.rtsp_ffmpeg import RtspFfmpegSource


def test_probe_retries_on_unspecified_size(monkeypatch, caplog):
    calls = []

    def fake_probe(uri, probesize=None, analyzeduration=None, **kwargs):
        calls.append((probesize, analyzeduration))
        return {"streams": [{"codec_type": "video"}]}

    monkeypatch.setattr(ffmpeg, "probe", fake_probe)
    src = RtspFfmpegSource("rtsp://example")
    with caplog.at_level(logging.WARNING):
        src._probe_resolution()
    assert len(calls) == 2
    assert "HINT: increase probesize/analyzeduration" in caplog.text
    assert src.width == 0 and src.height == 0
