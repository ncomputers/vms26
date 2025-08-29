"""Health check endpoints for liveness and readiness."""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger

from core.tracker_manager import get_tracker_status

router = APIRouter()


def _workers_ready(app) -> bool:
    """Return True if all critical workers report running."""
    trackers = get_tracker_status()
    trackers_ready = all(
        info["capture_alive"] and info["process_alive"] for info in trackers.values()
    )
    ppe_worker = getattr(app.state, "ppe_worker", None)
    visitor_worker = getattr(app.state, "visitor_worker", None)
    alert_worker = getattr(app.state, "alert_worker", None)
    return (
        trackers_ready
        and (ppe_worker is None or getattr(ppe_worker, "running", False))
        and (visitor_worker is None or getattr(visitor_worker, "running", False))
        and (alert_worker is None or getattr(alert_worker, "running", False))
    )


def monitor_readiness(app) -> None:
    """Update app.state.ready once all workers are initialized."""
    app.state.ready = False

    def _wait() -> None:
        while not _workers_ready(app):
            time.sleep(0.5)
        app.state.ready = True

    threading.Thread(target=_wait, daemon=True).start()


@router.get("/health/live")
async def live() -> dict:
    """Liveness probe that always succeeds."""
    try:
        return {"ok": True, "message": "live", "data": None}
    except Exception:
        logger.exception("live check failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "internal error", "data": None},
        )


@router.get("/health/ready")
async def ready(request: Request):
    """Readiness probe that verifies critical workers are running."""
    try:
        app = request.app
        if getattr(app.state, "ready", False) and _workers_ready(app):
            return {"ok": True, "message": "ready", "data": None}
        return JSONResponse(
            status_code=503,
            content={"ok": False, "message": "not ready", "data": None},
        )
    except Exception:
        logger.exception("ready check failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "internal error", "data": None},
        )


@router.get("/health")
async def health() -> dict:
    """Simple health check endpoint."""
    try:
        return {"ok": True, "message": "healthy", "data": None}
    except Exception:
        logger.exception("health check failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": "internal error", "data": None},
        )
