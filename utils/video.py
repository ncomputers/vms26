"""Video utilities."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from collections import OrderedDict

from config import config as app_config
from utils.housekeeping import register_cache

logger = logging.getLogger(__name__)

# URL -> ((width, height), expiry)
_RES_CACHE: OrderedDict[str, tuple[tuple[int, int], float]] = OrderedDict()
_CACHE_MAX = 128
register_cache("resolution", _RES_CACHE)


_FALLBACK_TTL = 120


def get_stream_resolution(
    url: str,
    *,
    cache_seconds: float = 300,
    invalidate: bool = False,
    timeout: float = 10,
    fallback_ttl: float | None = None,
) -> tuple[int, int]:
    """Return ``(width, height)`` for the first video stream in ``url``.

    Results are cached per-URL for ``cache_seconds``. Successful probes are
    stored in an LRU cache. Set ``invalidate`` to ``True`` to force a refresh.
    Falls back to ``(640, 480)`` if probing fails and logs a warning.
    Fallback results are cached for ``fallback_ttl`` seconds to avoid repeated
    probes. When ``fallback_ttl`` is ``None``, the value from the global
    ``config`` is used (``stream_probe_fallback_ttl``) falling back to
    ``_FALLBACK_TTL``. The ``timeout`` parameter controls how long ``ffprobe``
    is allowed to run.
    """
    now = time.monotonic()
    if invalidate:
        _RES_CACHE.pop(url, None)
    else:
        cached = _RES_CACHE.get(url)
        if cached:
            if cached[1] > now:
                _RES_CACHE.move_to_end(url)
                return cached[0]
            _RES_CACHE.pop(url, None)
    cmd = ["ffprobe"]
    if url.startswith("rtsp://"):
        cmd.extend(["-rtsp_transport", "tcp"])
    cmd.extend(
        [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            url,
        ]
    )
    fallback = (640, 480)
    logger.debug("ffprobe command: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        info = json.loads(proc.stdout or "{}")
        streams = info.get("streams", [])
        if streams:
            stream = streams[0]
            width = int(stream.get("width", fallback[0]))
            height = int(stream.get("height", fallback[1]))
            # Overwrite any previous cache entry (including fallbacks)
            _RES_CACHE.pop(url, None)
            _RES_CACHE[url] = ((width, height), now + cache_seconds)
            _RES_CACHE.move_to_end(url)
            while len(_RES_CACHE) > _CACHE_MAX:
                _RES_CACHE.popitem(last=False)
            return width, height
        logger.debug("ffprobe stdout: %s", proc.stdout)
        logger.debug("ffprobe stderr: %s", proc.stderr)
        logger.warning("ffprobe returned no streams for %s; falling back to %dx%d", url, *fallback)
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as exc:
        logger.debug("ffprobe stdout: %s", getattr(exc, "stdout", ""))
        logger.debug("ffprobe stderr: %s", getattr(exc, "stderr", ""))
        logger.warning(
            "ffprobe failed for %s (%s: %s); falling back to %dx%d",
            url,
            type(exc).__name__,
            exc,
            *fallback,
        )
    except (OSError, ValueError) as exc:
        logger.warning(
            "ffprobe error for %s (%s: %s); falling back to %dx%d",
            url,
            type(exc).__name__,
            exc,
            *fallback,
        )

    ttl = (
        fallback_ttl
        if fallback_ttl is not None
        else app_config.get("stream_probe_fallback_ttl", _FALLBACK_TTL)
    )
    _RES_CACHE[url] = (fallback, now + ttl)
    _RES_CACHE.move_to_end(url)
    while len(_RES_CACHE) > _CACHE_MAX:
        _RES_CACHE.popitem(last=False)
    return fallback


async def async_get_stream_resolution(
    url: str,
    *,
    cache_seconds: float = 300,
    invalidate: bool = False,
    timeout: float = 10,
    fallback_ttl: float | None = None,
) -> tuple[int, int]:
    """Async wrapper around :func:`get_stream_resolution`.

    Executes the blocking probe in a thread and returns ``(640, 480)`` on
    failure or timeout. The ``timeout`` and ``fallback_ttl`` parameters are
    forwarded to the underlying probe.
    """
    fallback = (640, 480)
    try:
        return await asyncio.to_thread(
            get_stream_resolution,
            url,
            cache_seconds=cache_seconds,
            invalidate=invalidate,
            timeout=timeout,
            fallback_ttl=fallback_ttl,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning(
            "async probe failed for %s (%s: %s); falling back to %dx%d",
            url,
            type(exc).__name__,
            exc,
            *fallback,
        )
        return fallback
