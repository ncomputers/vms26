import subprocess
from pathlib import Path

import pytest

SAMPLE_MP4 = Path(__file__).with_name("sample.mp4")


@pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample MP4 unavailable")
def test_read_one_frame_as_raw_bgr():
    expected = 320 * 240 * 3
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        str(SAMPLE_MP4),
        "-vf",
        "scale=320:240",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-vframes",
        "1",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        data = proc.stdout.read(expected)
    finally:
        proc.stdout.close()
        proc.wait()
    assert len(data) == expected
