from __future__ import annotations

import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=2)
def _ffmpeg_has_option(opt: str) -> bool:
    """Return True if ``ffmpeg`` help lists ``opt``."""
    try:
        res = subprocess.run(["ffmpeg", "-h"], capture_output=True, text=True, check=False)
    except Exception:
        return False
    return f"-{opt}" in res.stdout


RTSP_STIMEOUT_USEC = os.getenv("RTSP_STIMEOUT_USEC", "5000000")


def _build_timeout_flags() -> list[str]:
    """Return ``-stimeout`` flag sourced from ``RTSP_STIMEOUT_USEC``."""
    if not RTSP_STIMEOUT_USEC:
        return []
    if _ffmpeg_has_option("stimeout"):
        return ["-stimeout", RTSP_STIMEOUT_USEC]
    return []


def build_preview_cmd(url: str, transport: str, downscale: int | None = None) -> list[str]:
    """Return ffmpeg command for generating an MJPEG preview."""
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-rtsp_transport",
        transport,
    ]
    flags = _build_timeout_flags()
    cmd += flags
    cmd += ["-i", url, "-an"]
    cmd += ["-flags", "low_delay", "-fflags", "nobuffer"]
    if downscale and downscale > 1:
        vf = f"scale=trunc(iw/{downscale}/2)*2:trunc(ih/{downscale}/2)*2"
        cmd += ["-vf", vf]
    cmd += [
        "-threads",
        "1",
        "-f",
        "mpjpeg",
        "-q:v",
        "5",
        "pipe:1",
    ]
    return cmd


def build_snapshot_cmd(url: str, transport: str, downscale: int | None = None) -> list[str]:
    """Return ffmpeg command for capturing a single JPEG frame."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-nostats"]
    if url.startswith("rtsp://"):
        stimeout = os.getenv("RTSP_STIMEOUT_USEC", "20000000")
        rw_timeout = os.getenv("RTSP_RW_TIMEOUT_USEC", "2000000")
        cmd += [
            "-rtsp_transport",
            transport,
            "-stimeout",
            stimeout,
            "-rw_timeout",
            rw_timeout,
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "1000000",
            "-analyzeduration",
            "0",
            "-max_delay",
            "500000",
            "-reorder_queue_size",
            "0",
            "-avioflags",
            "direct",
            "-an",
            "-i",
            url,
        ]
    else:
        cmd += ["-i", url, "-an", "-flags", "low_delay", "-fflags", "nobuffer"]
    if downscale and downscale > 1:
        vf = f"scale=trunc(iw/{downscale}/2)*2:trunc(ih/{downscale}/2)*2"
        cmd += ["-vf", vf]
    cmd += [
        "-threads",
        "1",
        "-frames:v",
        "1",
        "-f",
        "image2",
        "-q:v",
        "5",
        "pipe:1",
    ]
    return cmd
