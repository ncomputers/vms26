from __future__ import annotations

"""Utilities for standardized API error messages."""

STREAM_ERROR_MESSAGES: dict[str, str] = {
    "auth": "auth failed",
    "codec": "codec unsupported; set camera to H.264 or enable hevc",
    "url": "invalid URL/path",
    "transport": "transport failure; try switching TCP/UDP",
    "timeout": "timeout – camera unreachable",
}


def stream_error_message(code: str) -> str | None:
    """Return human-readable message for capture error *code*."""

    return STREAM_ERROR_MESSAGES.get(code)
