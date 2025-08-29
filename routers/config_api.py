"""Expose runtime configuration details."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect

from utils.deps import get_settings

router = APIRouter()
CONFIG_EVENT = asyncio.Event()


def _display_settings(cfg: dict) -> dict:
    """Extract front-end relevant display settings from ``cfg``."""
    return {
        "show_lines": cfg.get("show_lines", False),
        "show_track_lines": cfg.get("show_track_lines", False),
        "show_counts": cfg.get("show_counts", False),
        "show_ids": cfg.get("show_ids", False),
        "debug_logs": cfg.get("debug_logs", False),
        "enable_live_charts": cfg.get("enable_live_charts", False),
        "track_ppe": cfg.get("track_ppe", []),
        "alert_anomalies": cfg.get("alert_anomalies", []),
        "preview_anomalies": cfg.get("preview_anomalies", []),
    }


@router.get("/config")
async def config_endpoint(cfg: dict = Depends(get_settings)) -> dict:
    """Return selected configuration flags for client use."""
    return _display_settings(cfg)


@router.websocket("/ws/config")
async def config_ws(ws: WebSocket, cfg: dict = Depends(get_settings)) -> None:
    """Push configuration changes to connected clients."""
    await ws.accept()
    await ws.send_json({"type": "settings", "data": _display_settings(cfg)})
    try:
        while True:
            await CONFIG_EVENT.wait()
            await ws.send_json({"type": "settings", "data": _display_settings(cfg)})
            CONFIG_EVENT.clear()
    except WebSocketDisconnect:  # pragma: no cover - network error
        pass
