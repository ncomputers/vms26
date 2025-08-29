"""Unified capture sources."""

from .base import Backoff, FrameSourceError, IFrameSource
from .local_cv import LocalCvSource
from .rtsp_ffmpeg import RtspFfmpegSource

try:  # pragma: no cover - optional dependency
    from .rtsp_gst import RtspGstSource, ensure_gst
except Exception:  # pragma: no cover - gstreamer/opencv missing
    RtspGstSource = None  # type: ignore[assignment]

    def ensure_gst() -> bool:
        return False


from .http_mjpeg import HttpMjpegSource
from .pipeline_ffmpeg import FfmpegPipeline

__all__ = [
    "IFrameSource",
    "FrameSourceError",
    "Backoff",
    "LocalCvSource",
    "RtspFfmpegSource",
    "RtspGstSource",
    "HttpMjpegSource",
    "FfmpegPipeline",
    "ensure_gst",
]
