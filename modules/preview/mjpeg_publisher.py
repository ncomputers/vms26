from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator, Dict

from modules.frame_bus import FrameBus
from utils.jpeg import encode_jpeg
from utils import logx


class PreviewPublisher:
    """Publish MJPEG frames from :class:`FrameBus` instances."""

    def __init__(self, buses: Dict[int, FrameBus] | None = None) -> None:
        self._buses: Dict[int, FrameBus] = buses or {}
        self._showing: set[int] = set()
        self._clients: defaultdict[int, int] = defaultdict(int)

    # ------------------------------------------------------------------
    def start_show(self, camera_id: int) -> None:
        """Enable preview streaming for ``camera_id``."""
        if camera_id not in self._showing:
            self._showing.add(camera_id)
            logx.event("PREVIEW_SHOW", camera_id=camera_id)

    def stop_show(self, camera_id: int) -> None:
        """Disable preview streaming for ``camera_id``."""
        if camera_id in self._showing:
            self._showing.remove(camera_id)
            logx.event("PREVIEW_HIDE", camera_id=camera_id)

    def is_showing(self, camera_id: int) -> bool:
        """Return ``True`` if preview is enabled for ``camera_id``."""
        return camera_id in self._showing

    # ------------------------------------------------------------------
    async def stream(self, camera_id: int) -> AsyncIterator[bytes]:
        """Yield MJPEG ``--frame`` chunks for ``camera_id``."""
        bus = self._buses.get(camera_id)
        if not bus:
            return
        self._clients[camera_id] += 1
        logx.event("PREVIEW_CLIENT_OPEN", camera_id=camera_id)
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        try:
            while self.is_showing(camera_id):
                frame = await asyncio.to_thread(bus.get_latest, 1000)
                if frame is None:
                    continue
                jpeg = encode_jpeg(frame)
                yield boundary + jpeg + b"\r\n"
        finally:
            self._clients[camera_id] -= 1
            logx.event("PREVIEW_CLIENT_CLOSE", camera_id=camera_id)
