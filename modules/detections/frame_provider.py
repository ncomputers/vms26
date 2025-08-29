"""Utilities for lazily decoding frames from capture streams."""

from __future__ import annotations

from modules.capture import IFrameSource


def request_decoded_frame(stream: IFrameSource):
    """Return the latest frame decoded from *stream* on demand."""
    return stream.read()
