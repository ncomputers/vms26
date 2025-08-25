from __future__ import annotations

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


class GstCameraStream:
    def __init__(
        self,
        url: str,
        width: int = 640,
        height: int = 480,
        transport: str = "tcp",
        extra_pipeline: str | None = None,
        buffer_seconds: int = 0,
        start_thread: bool = True,
        **kwargs,
    ) -> None:
        self.url = url
        self.pipeline = _build_pipeline(url, width, height, transport, extra_pipeline)
        self.last_status = ""
        self.last_pipeline = ""
        if start_thread:
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

    def release(self) -> None:
        pass
