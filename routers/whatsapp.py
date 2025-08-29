"""Proxy endpoints for the external WhatsApp service."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import WHATSAPP_SERVICE_URL, WHATSAPP_SHARED_SECRET, config

router = APIRouter(prefix="/whatsapp")

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


async def _proxy_request(method: str, endpoint: str, data: dict | None = None) -> dict:
    """Forward a request to the WhatsApp service."""
    url = f"{WHATSAPP_SERVICE_URL.rstrip('/')}{endpoint}"
    headers = (
        {"x-shared-secret": WHATSAPP_SHARED_SECRET} if WHATSAPP_SHARED_SECRET else {}
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(method, url, json=data, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    return resp.json()


@router.get("/", response_class=HTMLResponse)
async def whatsapp_page(request: Request) -> HTMLResponse:
    """Render the WhatsApp service status/QR page."""
    return templates.TemplateResponse(
        "whatsapp.html",
        {
            "request": request,
            "service_url": WHATSAPP_SERVICE_URL,
            "shared_secret": WHATSAPP_SHARED_SECRET,
            "cfg": config,
        },
    )


@router.post("/sendText")
async def send_text(request: Request) -> dict:
    """Proxy a text message send request."""
    data = await request.json()
    return await _proxy_request("POST", "/sendText", data)


@router.post("/sendMedia")
async def send_media(request: Request) -> dict:
    """Proxy a media send request."""
    data = await request.json()
    return await _proxy_request("POST", "/sendMedia", data)


@router.get("/status")
async def status() -> dict:
    """Fetch connection status from the WhatsApp service."""
    return await _proxy_request("GET", "/status")
