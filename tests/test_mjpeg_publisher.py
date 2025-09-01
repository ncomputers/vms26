import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from modules.frame_bus import FrameBus
from modules.preview.mjpeg_publisher import PreviewPublisher


class DummyConnector:
    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1


def test_preview_toggle_no_connector_restart():
    connector = DummyConnector()
    connector.start()
    bus = FrameBus()
    pub = PreviewPublisher({1: bus})
    pub.start_show(1)
    pub.stop_show(1)
    assert connector.start_count == 1
    assert connector.stop_count == 0


@pytest.mark.asyncio
async def test_jpeg_encoding_only_with_clients(monkeypatch):
    bus = FrameBus()
    pub = PreviewPublisher({1: bus})
    calls = SimpleNamespace(count=0)

    def fake_encode(frame):  # type: ignore[override]
        calls.count += 1
        return b"jpeg"

    monkeypatch.setattr("modules.preview.mjpeg_publisher.encode_jpeg", fake_encode)

    pub.start_show(1)
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    bus.put(frame)
    assert calls.count == 0

    gen = pub.stream(1)
    bus.put(frame)
    chunk = await asyncio.wait_for(gen.__anext__(), 1)
    assert chunk.startswith(b"--frame")
    assert calls.count == 1
    await gen.aclose()

    bus.put(frame)
    await asyncio.sleep(0.05)
    assert calls.count == 1
