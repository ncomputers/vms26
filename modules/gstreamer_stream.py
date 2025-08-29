from __future__ import annotations

from typing import Optional

from .base_stream import BaseStream

Gst = None


def _ensure_gst() -> bool:
    return True


def _build_pipeline(
    url: str,
    width: int,
    height: int,
    transport: str = "tcp",
    extra_pipeline: str | None = None,
) -> str:
    parts = [
        f'rtspsrc location="{url}" protocols={transport} latency=100',
        "rtph264depay",
        "h264parse",
        "avdec_h264",
        "videoconvert",
    ]
    if extra_pipeline:
        parts.append(extra_pipeline)
    parts.append(f"video/x-raw,format=BGR,width={width},height={height}")
    parts.append("queue max-size-buffers=1 leaky=downstream")
    parts.append("appsink name=appsink drop=true sync=false max-buffers=1")
    return " ! ".join(parts)


class GstCameraStream(BaseStream):
    def __init__(
        self,
        url: str,
        width: int | None = None,
        height: int | None = None,
        transport: str = "tcp",
        extra_pipeline: str | None = None,
        start_thread: bool = True,
        **kwargs,
    ) -> None:
        width = width or 640
        height = height or 480
        self.pipeline = _build_pipeline(url, width, height, transport, extra_pipeline)
        self.last_status = ""
        self.last_pipeline = ""
        super().__init__(
            url=url,
            width=width,
            height=height,
            transport=transport,
            queue_size=1,
            start_thread=start_thread,
        )

    # ------------------------------------------------------------------
    def _start_backend(self) -> None:
        self._init_stream()

    def _init_stream(self) -> None:
        self.last_pipeline = self.pipeline
        try:
            _ensure_gst()
            if Gst:
                Gst.parse_launch(self.pipeline)
            self.last_status = "ok"
        except Exception:
            self.last_status = "error"
            self.last_pipeline = self.pipeline

    def _read_frame(self) -> Optional[object]:
        return None

    def _release_backend(self) -> None:
        pass
