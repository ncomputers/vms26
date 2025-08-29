"""Email and alert rule management routes."""

from __future__ import annotations

import json
import os
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_csrf_protect import CsrfProtect
from loguru import logger
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from config import ANOMALY_ITEMS, config
from config.storage import save_config
from core import events
from modules.utils import require_roles
from schemas.alerts import AlertRule
from utils.deps import get_redis

router = APIRouter()
cfg: dict = {}
redisfx = None

logger = logger.bind(module="alerts")


class CsrfSettings(BaseSettings):
    secret_key: str


@CsrfProtect.load_config
def get_csrf_config() -> CsrfSettings:
    """Provide CSRF settings using environment or config values."""
    secret = (
        os.getenv("CSRF_SECRET_KEY")
        or cfg.get("secret_key")
        or config.get("secret_key", "change-me")
    )
    return CsrfSettings(secret_key=secret)


csrf_protect = CsrfProtect()


# init_context routine
def init_context(
    config: dict,
    trackers: Dict[int, "PersonTracker"],
    redis_client,
    templates_path,
    config_path: str,
    redis_facade=None,
):
    """Initialize module globals for routing and template access."""
    global cfg, trackers_map, redis, templates, cfg_path, redisfx
    cfg = config
    trackers_map = trackers
    redis = redis_client
    redisfx = redis_facade
    templates = Jinja2Templates(directory=templates_path)
    templates.env.add_extension("jinja2.ext.do")
    cfg_path = config_path


@router.get("/alerts")
async def alerts_page(request: Request):
    """Render the email alerts configuration page."""
    res = require_roles(request, ["admin"])
    if isinstance(res, RedirectResponse):
        return res
    items = list(ANOMALY_ITEMS) + sorted(events.ALL_EVENTS - {events.VISITOR_REGISTERED})
    if cfg.get("features", {}).get("visitor_mgmt"):
        items.append(events.VISITOR_REGISTERED)
    token, signed = csrf_protect.generate_csrf_tokens()
    # Render the template immediately so tests can access ``response.body``
    html = templates.get_template("email_alerts.html").render(
        {
            "request": request,
            "rules": cfg.get("alert_rules", []),
            "anomaly_items": items,
            "cfg": config,
            "csrf_token": token,
        }
    )
    response = HTMLResponse(html)
    csrf_protect.set_csrf_cookie(signed, response)
    return response


@router.post("/alerts")
async def save_alerts(request: Request):
    """Persist alert rule updates from the settings form."""
    res = require_roles(request, ["admin"])
    if isinstance(res, RedirectResponse):
        return res
    data = await request.json()
    rules_data = data.get("rules", [])
    allowed = set(ANOMALY_ITEMS) | events.ALL_EVENTS
    if not cfg.get("features", {}).get("visitor_mgmt"):
        allowed.discard(events.VISITOR_REGISTERED)
    AlertRule.allowed_metrics = allowed
    validated = []
    for r in rules_data:
        try:
            rule = AlertRule.model_validate(r)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=json.loads(exc.json()))
        rd = rule.model_dump()
        rd["recipients"] = ",".join(rd["recipients"])
        validated.append(rd)
    cfg["alert_rules"] = validated
    try:
        save_config(cfg, cfg_path, redis)
    except Exception:
        user = request.session.get("user", {}).get("name")
        logger.bind(user=user).exception("Failed to save alert rules")
        raise HTTPException(status_code=500, detail="save_failed")
    return {"saved": True}


@router.get("/api/alerts/recent")
async def recent_alerts(redis=Depends(get_redis)):
    try:
        entries = redis.lrange("recent_alerts", 0, 19)
    except Exception:
        return []
    items = []
    for e in entries or []:
        try:
            items.append(json.loads(e if isinstance(e, str) else e.decode()))
        except Exception:
            continue
    return items
