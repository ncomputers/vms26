from __future__ import annotations

"""Lightweight in-memory frame bus.

This module provides helper functions for passing frames between a camera
producer and multiple consumers. Each registered consumer receives frames
published for a camera via an independent :class:`collections.deque`.
"""

from collections import deque
from typing import Any, Deque, Dict, Tuple

# Mapping of (camera_id, consumer_id) -> deque holding (frame, ts_ms) tuples.
_buffers: Dict[Tuple[str, str], Deque[tuple[Any, int]]] = {}


def register(camera_id: str, consumer_id: str, maxlen: int = 10) -> Deque[tuple[Any, int]]:
    """Register a consumer for a given camera and return its frame deque.

    If the consumer is already registered, the existing deque is returned.
    """

    key = (camera_id, consumer_id)
    queue = _buffers.get(key)
    if queue is None or queue.maxlen != maxlen:
        queue = deque(maxlen=maxlen)
        _buffers[key] = queue
    return queue


def unregister(camera_id: str, consumer_id: str) -> None:
    """Remove a previously registered consumer."""

    _buffers.pop((camera_id, consumer_id), None)


def publish(camera_id: str, frame: Any, ts_ms: int) -> None:
    """Publish a frame to all consumers registered for ``camera_id``.

    Frames are appended without blocking. When a consumer's deque is full,
    the oldest frame is discarded automatically by :class:`collections.deque`.
    """

    for (cam, _), queue in list(_buffers.items()):
        if cam == camera_id:
            queue.append((frame, ts_ms))
