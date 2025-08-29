from __future__ import annotations

"""Utilities for standardized API error responses."""

from typing import Any, Mapping

from fastapi.responses import JSONResponse


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


def error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    details: Mapping[str, Any] | None = None,
) -> JSONResponse:
    """Return a JSONResponse with a standardized error payload.

    Args:
        code: Machine-readable error code.
        message: Human-readable error message.
        status_code: HTTP status code for the response.
        details: Optional additional information about the error.
    """

    payload: dict[str, Any] = {"ok": False, "code": code, "message": message}
    if details:
        payload["details"] = details
    return JSONResponse(payload, status_code=status_code)
