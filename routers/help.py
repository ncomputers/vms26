"""Routes for help and contact pages."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

cfg: dict = {}
templates: Jinja2Templates
FAQ_PATH = Path(__file__).resolve().parent.parent / "docs" / "faq.json"
redisfx = None


def init_context(config: dict, templates_path: str, redis_facade=None) -> None:
    """Initialize shared module state."""
    global cfg, templates, redisfx
    cfg = config
    redisfx = redis_facade
    templates = Jinja2Templates(directory=templates_path)
    templates.env.add_extension("jinja2.ext.do")


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request) -> HTMLResponse:
    """Render the help/FAQ page."""
    faqs = []
    if FAQ_PATH.exists():
        with open(FAQ_PATH) as f:
            faqs = json.load(f)
    return templates.TemplateResponse("help.html", {"request": request, "cfg": cfg, "faqs": faqs})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request) -> HTMLResponse:
    """Render the contact page."""
    return templates.TemplateResponse("contact.html", {"request": request, "cfg": cfg})
