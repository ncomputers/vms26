"""Factory helpers for opening camera frame sources."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from config import config, use_gstreamer
from modules.capture import (
    FrameSourceError,
    HttpMjpegSource,
    IFrameSource,
    LocalCvSource,
    RtspFfmpegSource,
    RtspGstSource,
)
from utils.url import mask_creds, with_rtsp_transport


class StreamUnavailable(Exception):
    """Raised when no capture backend can provide frames."""


__all__ = ["open_capture", "StreamUnavailable"]


logger = logging.getLogger(__name__)


async def _probe_rtsp(url: str) -> tuple[str, str, int, int, float]:
    """Probe ``url`` with ``ffprobe`` trying UDP then TCP.

    Returns the working URL (possibly annotated with transport), the chosen
    transport, and the detected width, height and FPS. On failure the original
    URL and default metadata are returned.
    """

    async def _run(u: str) -> tuple[int, int, float]:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate",
            "-of",
            "json",
            u,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=2.0)
        if proc.returncode != 0:
            raise RuntimeError(err.decode().strip())
        data = json.loads(out.decode() or "{}")
        stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        fps_txt = stream.get("avg_frame_rate") or "0/1"
        try:
            num, den = fps_txt.split("/", 1)
            fps = float(num) / float(den)
        except Exception:
            fps = 0.0
        return width, height, fps

    try:
        w, h, fps = await _run(url)
        logger.debug("ffprobe succeeded over udp for %s", mask_creds(url))
        return url, "udp", w, h, fps
    except Exception as exc:
        logger.debug("ffprobe udp failed for %s: %s", mask_creds(url), exc)

    tcp_url = with_rtsp_transport(url, "tcp")
    try:
        w, h, fps = await _run(tcp_url)
        logger.debug("ffprobe succeeded over tcp for %s", mask_creds(tcp_url))
        return tcp_url, "tcp", w, h, fps
    except Exception as exc:
        logger.debug("ffprobe tcp failed for %s: %s", mask_creds(tcp_url), exc)

    return url, "udp", 0, 0, 0.0


def _clamp_latency(value: int) -> int:
    return max(50, min(300, int(value)))


def _build(cam_cfg: dict[str, Any], cam_id: int) -> IFrameSource:
    mode = cam_cfg.get("mode", "rtsp")
    uri = cam_cfg.get("uri", "")
    latency = _clamp_latency(cam_cfg.get("latency_ms", 100))
    tcp = bool(cam_cfg.get("tcp", True))
    if mode == "local":
        return LocalCvSource(uri or 0, cam_id=cam_id)
    if mode == "http":
        return HttpMjpegSource(
            uri, cam_id=cam_id, max_queue=cam_cfg.get("max_queue", 1)
        )
    if mode == "rtsp":
        if config.get("use_gstreamer", use_gstreamer) and RtspGstSource is not None:
            return RtspGstSource(uri, tcp=tcp, latency_ms=latency, cam_id=cam_id)
        return RtspFfmpegSource(uri, tcp=tcp, latency_ms=latency, cam_id=cam_id)
    raise StreamUnavailable(f"unknown mode {mode}")


def open_capture(
    src: str | int | None = None,
    cam_id: int | None = None,
    src_type: str | None = None,
    resolution: tuple[int, int] | None = None,
    rtsp_transport: str | None = None,
    use_gpu: bool = False,
    **kwargs: Any,
) -> tuple[IFrameSource, str]:
    """Instantiate and open a frame source.

    Parameters mirror the documented public API. ``src`` may be omitted for
    backwards compatibility, in which case the value is read from global
    configuration. Unknown keyword arguments are accepted but ignored.
    """

    # allow legacy ``open_capture(cam_id)`` usage
    if cam_id is None and isinstance(src, int):
        cam_id = src
        src = None

    cam_cfg = config.get("camera", {})
    cam_id = cam_id if cam_id is not None else 0
    if src is None:
        src = cam_cfg.get("uri", "")
    if src_type is None:
        src_type = cam_cfg.get("mode", "rtsp")

    # resolve common options
    transport = rtsp_transport
    width, height = (None, None)
    if resolution and len(resolution) == 2:
        width, height = resolution
    latency = _clamp_latency(kwargs.pop("latency_ms", cam_cfg.get("latency_ms", 100)))
    capture_buffer = kwargs.pop("capture_buffer", None)
    backend_priority = kwargs.pop("backend_priority", None)

    if src_type == "rtsp" and transport is None and isinstance(src, str):
        try:
            probed_url, transport, w_p, h_p, _ = asyncio.run(_probe_rtsp(src))
            src = probed_url
            if not width and not height and w_p and h_p:
                width, height = w_p, h_p
        except Exception as exc:  # pragma: no cover - probe failures are non fatal
            logger.debug("probe failed for %s: %s", mask_creds(str(src)), exc)

    if transport is None:
        transport = "tcp" if cam_cfg.get("tcp", True) else "udp"

    if src_type == "local":
        cap = LocalCvSource(src or 0, cam_id=cam_id)
        cap.open()
        return cap, transport
    if src_type == "http":
        max_queue = capture_buffer or cam_cfg.get("max_queue", 1)
        cap = HttpMjpegSource(str(src), cam_id=cam_id, max_queue=max_queue)
        cap.open()
        return cap, transport
    if src_type != "rtsp":
        raise StreamUnavailable(f"unknown mode {src_type}")

    # rtsp with optional backend fallback
    if backend_priority is None:
        if config.get("use_gstreamer", use_gstreamer) and RtspGstSource is not None:
            backend_priority = ["gst", "ffmpeg"]
        elif RtspGstSource is not None:
            backend_priority = ["ffmpeg", "gst"]
        else:
            backend_priority = ["ffmpeg"]
    while True:
        last_err = ""
        for be in backend_priority:
            if be == "gst":
                if RtspGstSource is None:
                    continue
                cap = RtspGstSource(
                    str(src),
                    tcp=transport == "tcp",
                    latency_ms=latency,
                    use_nv=use_gpu,
                    cam_id=cam_id,
                )
            elif be == "ffmpeg":
                cap_kwargs: dict[str, Any] = {
                    "tcp": transport == "tcp",
                    "latency_ms": latency,
                    "cam_id": cam_id,
                }
                if width and height:
                    cap_kwargs["width"] = width
                    cap_kwargs["height"] = height
                cap = RtspFfmpegSource(str(src), **cap_kwargs)
            else:
                continue
            try:
                cap.open()
                logger.info(
                    "[cap:%s] opened stream using %s transport",
                    cam_id,
                    transport,
                )
                return cap, transport
            except FrameSourceError as exc:
                if str(exc) in {
                    "NO_VIDEO_STREAM",
                    "CONNECT_TIMEOUT",
                    "UNSUPPORTED_CODEC",
                }:
                    last_err = str(exc)
                    continue
                raise
        if last_err == "NO_VIDEO_STREAM" and transport == "tcp":
            logger.info("[cap:%s] no video over TCP, retrying with UDP", cam_id)
            transport = "udp"
            continue
        raise StreamUnavailable(last_err or "failed to open stream")
