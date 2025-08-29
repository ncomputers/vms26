"""Application entry point instantiating the FastAPI app."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.sessions import SessionMiddleware

from app.web import api_perf
from core.config import get_config
from core.logging import setup_json_logger
from modules.utils import SNAP_DIR
from server.config import _load_secret_key
from server.startup import handle_unexpected_error
from server.startup import init_app as _init_app
from server.startup import lifespan


def init_app(
    config_path: str = "config.json",
    stream_url: str | None = None,
    workers: int | None = None,
):
    return _init_app(app, config_path=config_path, stream_url=stream_url, workers=workers)


try:  # pragma: no cover - middleware optional
    from fastapi_csrf_protect import CsrfProtectMiddleware
except ImportError:  # pragma: no cover - middleware optional
    CsrfProtectMiddleware = None


logger = logger.bind(module="app")
setup_json_logger()
_cfg = get_config()

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=_load_secret_key())
app.state.ready = False
app.add_exception_handler(Exception, handle_unexpected_error)

app.mount("/snapshots", StaticFiles(directory=str(SNAP_DIR)), name="snapshots")
static_mounts = [
    ("/static", "static"),
    ("/invite_photos", "public/invite_photos"),
    ("/logos", "uploads/logos"),
]
for route, directory_name in static_mounts:
    directory = SNAP_DIR.parent / directory_name
    if directory.is_dir():
        app.mount(route, StaticFiles(directory=str(directory)), name=directory.name)

app.include_router(api_perf.router)


@app.get("/api/v1/health")
async def health_ping() -> dict:
    return {"ok": True, "ts": datetime.utcnow().isoformat()}


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest() -> FileResponse:
    return FileResponse("static/manifest.webmanifest", media_type="application/manifest+json")


def _sw_response(path: str) -> FileResponse:
    response = FileResponse(path, media_type="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return _sw_response("static/service-worker.js")


@app.get("/sw-dev.js", include_in_schema=False)
async def sw_dev() -> FileResponse:
    return _sw_response("static/sw-dev.js")


@app.get("/offline.html", include_in_schema=False)
async def offline() -> FileResponse:
    return FileResponse("static/offline.html", media_type="text/html")


if CsrfProtectMiddleware:
    app.add_middleware(CsrfProtectMiddleware)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
