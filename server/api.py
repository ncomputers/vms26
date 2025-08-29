from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Any, Callable, Generator, Optional

import yaml
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse

PipelineType = Any
app: FastAPI

# Global pipeline instance and loaded configuration
pipeline: Optional[PipelineType] = None
config: dict[str, Any] = {}


def _load_config(path: str) -> dict[str, Any]:
    """Load configuration from ``path`` with environment overrides.

    Supports JSON or YAML files. Missing or malformed files simply return an
    empty configuration allowing the server to start with defaults during
    tests."""

    try:
        with open(path) as fh:
            if path.endswith((".yml", ".yaml")):
                cfg: dict[str, Any] = yaml.safe_load(fh) or {}
            else:
                cfg = json.load(fh)
    except Exception:
        return {}

    env_map = {
        "rtsp_url": "RTSP_URL",
        "prefer_tcp": "PREFER_TCP",
        "read_timeout_ms": "READ_TIMEOUT_MS",
        "pipeline": "PIPELINE",
        "show_stream": "SHOW_STREAM",
        "target_width": "TARGET_WIDTH",
        "target_height": "TARGET_HEIGHT",
        "force_codec": "FORCE_CODEC",
    }
    for key, env in env_map.items():
        val = os.getenv(env)
        if val is not None:
            if key in {"prefer_tcp", "show_stream"}:
                cfg[key] = val.lower() in {"1", "true", "yes"}
            elif key in {"read_timeout_ms", "target_width", "target_height"}:
                with suppress(ValueError):
                    cfg[key] = int(val)
            else:
                cfg[key] = val

    return cfg


def _create_pipeline(cfg: dict[str, Any]) -> PipelineType:
    """Create a capture pipeline based on configuration."""

    uri = cfg.get("rtsp_url") or cfg.get("camera", {}).get("uri") or cfg.get("uri") or ""
    backend = cfg.get("pipeline") or cfg.get("stream_mode")
    if backend is None:
        backend = "gstreamer" if cfg.get("use_gstreamer") else "ffmpeg"

    if backend == "gstreamer":
        from capture.pipeline_gst import GstPipeline

        return GstPipeline(uri)
    else:
        from modules.capture.pipeline_ffmpeg import FfmpegPipeline

        return FfmpegPipeline(url=uri)


def _start_pipeline(p: PipelineType) -> None:
    start: Optional[Callable[[], None]] = getattr(p, "start", None)
    if start:
        start()


def _stop_pipeline(p: PipelineType) -> None:
    stop: Optional[Callable[[], None]] = getattr(p, "stop", None)
    if stop:
        with suppress(Exception):
            stop()


@asynccontextmanager
def lifespan(app: FastAPI):
    """Create a single pipeline instance for the application lifetime."""

    global pipeline, config
    config_path = os.getenv("PIPELINE_CONFIG", "config/default.yaml")
    config = _load_config(config_path)
    pipeline = _create_pipeline(config)
    _start_pipeline(pipeline)
    try:
        yield
    finally:
        if pipeline is not None:
            _stop_pipeline(pipeline)
            pipeline = None


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
@app.get("/snapshot", response_class=Response)
def get_snapshot() -> Response:
    """Return a single JPEG frame from the active pipeline."""

    if pipeline is None:
        raise HTTPException(status_code=503, detail="pipeline not running")
    getter: Optional[Callable[[], bytes]] = getattr(pipeline, "get_snapshot", None)
    if getter is None:
        getter = getattr(pipeline, "snapshot", None)
    if getter is None:
        raise HTTPException(status_code=500, detail="snapshot not supported")
    data = getter()
    return Response(content=data, media_type="image/jpeg")


@app.get("/stream.mjpeg")
def stream() -> StreamingResponse:
    """Return a multipart MJPEG stream from the active pipeline."""

    if pipeline is None:
        raise HTTPException(status_code=503, detail="pipeline not running")

    def gen() -> Generator[bytes, None, None]:
        frames = pipeline.frames()
        try:
            for frame in frames:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        finally:
            close = getattr(frames, "close", None)
            if close:
                close()

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/health")
def health() -> dict[str, Any]:
    """Return pipeline metrics if available."""

    if pipeline is None:
        return {"connected": False}
    metrics = getattr(pipeline, "metrics", lambda: {})()
    return metrics


@app.get("/config")
def get_config() -> dict[str, Any]:
    """Expose the loaded configuration for observability."""

    return config


@app.post("/restart")
def restart() -> dict[str, str]:
    """Restart the underlying pipeline."""

    global pipeline
    if pipeline is not None:
        _stop_pipeline(pipeline)
    pipeline = _create_pipeline(config)
    _start_pipeline(pipeline)
    return {"status": "restarted"}


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import uvicorn

    uvicorn.run("server.api:app", host="0.0.0.0", port=8000)
