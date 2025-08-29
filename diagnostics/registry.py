"""Diagnostic test registry and utility helpers.

This module exposes a decorator based registry for diagnostic checks.
Registered tests are asynchronous callables returning a mapping with the
following keys::

    {
        "id": str,
        "status": str,
        "reason": str,
        "detail": str,
        "suggestion": str,
        "duration_ms": int,
    }

The registry preserves insertion order. ``list_tests`` returns the
default sequence of diagnostic tests, ``get_source_mode`` inspects the
configured cameras to report their active mode and ``now_ms`` yields the
current timestamp in milliseconds.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Awaitable, Callable, Dict

from app.core.utils import now_ms

try:  # pragma: no cover - best effort if config package missing
    from config import config as app_config
except Exception:  # pragma: no cover - fallback when config unavailable
    app_config: Dict[str, object] = {}

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

REGISTRY: "OrderedDict[str, Callable[..., Awaitable[dict]]]" = OrderedDict()


def register(
    name: str,
) -> Callable[[Callable[..., Awaitable[dict]]], Callable[..., Awaitable[dict]]]:
    """Decorator to register a diagnostic test function.

    Registration preserves definition order using an :class:`OrderedDict`.
    The wrapped function is returned unchanged.
    """

    def decorator(fn: Callable[..., Awaitable[dict]]) -> Callable[..., Awaitable[dict]]:
        REGISTRY[name] = fn
        return fn

    return decorator


def list_tests() -> "OrderedDict[str, Callable[..., Awaitable[dict]]]":
    """Return the default diagnostic tests in execution order."""

    order = [
        "camera_found",
        "ping",
        "rtsp_probe",
        "mjpeg_probe",
        "snapshot_fresh",
        "stream_metrics",
        "detector_warm",
        "inference_latency",
        "queues_depth",
        "redis_rtt",
        "gpu_stats",
        "report_consistency",
        "license_limits",
    ]
    return OrderedDict((name, REGISTRY[name]) for name in order if name in REGISTRY)


def get_source_mode(cam_id: int) -> str:
    """Inspect configured cameras and deduce the source mode for ``cam_id``.

    Uses ``config.config['cameras']`` if available. The mode is normalised
    to one of ``rtsp``, ``mjpeg`", "local" or "screen". An empty string is
    returned when the camera cannot be resolved.
    """

    cameras = app_config.get("cameras") or []
    for cam in cameras:
        if cam.get("id") == cam_id:
            mode = (cam.get("mode") or cam.get("type") or "").lower()
            if mode == "http":
                mode = "mjpeg"
            if mode not in {"rtsp", "mjpeg", "local", "screen"}:
                url = cam.get("url", "")
                if url.startswith("rtsp://"):
                    mode = "rtsp"
                elif url.startswith("http://") or url.startswith("https://"):
                    mode = "mjpeg"
                elif url:
                    mode = "local"
                else:
                    mode = "screen"
            return mode
    return ""


# ---------------------------------------------------------------------------
# Default test implementations
# ---------------------------------------------------------------------------


async def _template_result(test_id: str) -> dict:
    """Return a generic placeholder test result."""

    start = now_ms()
    return {
        "id": test_id,
        "status": "ok",
        "reason": "",
        "detail": "",
        "suggestion": "",
        "duration_ms": now_ms() - start,
    }


@register("camera_found")
async def camera_found(*_, **__) -> dict:
    return await _template_result("camera_found")


@register("source_mode")
async def source_mode(*_, **__) -> dict:
    return await _template_result("source_mode")


@register("ping_host")
async def ping_host(*_, **__) -> dict:
    return await _template_result("ping_host")


@register("mjpeg_probe")
async def mjpeg_probe(*_, **__) -> dict:
    return await _template_result("mjpeg_probe")


@register("rtsp_probe")
async def rtsp_probe(*_, **__) -> dict:
    return await _template_result("rtsp_probe")


@register("recent_frame")
async def recent_frame(*_, **__) -> dict:
    return await _template_result("recent_frame")


@register("license_limits")
async def license_limits(*_, **__) -> dict:
    return await _template_result("license_limits")


# Eagerly import test implementations to populate the registry
try:  # pragma: no cover - import for side effects
    from . import tests  # type: ignore  # noqa: F401
except Exception:
    pass

__all__ = [
    "REGISTRY",
    "register",
    "list_tests",
    "get_source_mode",
    "now_ms",
    "camera_found",
    "source_mode",
    "ping_host",
    "mjpeg_probe",
    "rtsp_probe",
    "recent_frame",
    "license_limits",
]
