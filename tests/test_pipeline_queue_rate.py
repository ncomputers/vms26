"""Test pipeline queue behavior and processing rate control."""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.pipeline import Pipeline


def test_pipeline_queue_and_rate():
    os.environ["VMS26_QUEUE_MAX"] = "2"
    os.environ["VMS26_TARGET_FPS"] = "10"
    pipe = Pipeline({})
    pipe.start()
    times = []
    prev = 0.0
    deadline = time.time() + 0.5
    while time.time() < deadline and len(times) < 3:
        ts = pipe.process.last_ts
        if ts and ts != prev:
            times.append(ts)
            prev = ts
        time.sleep(0.01)
    pipe.stop()
    pipe.capture.join(timeout=1)
    pipe.process.join(timeout=1)
    assert len(pipe.queue) <= 2
    if len(times) >= 2:
        intervals = [b - a for a, b in zip(times, times[1:], strict=False)]
        assert all(i >= 0.09 for i in intervals)
