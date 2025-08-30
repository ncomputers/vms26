"""Settings management routes."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.datastructures import FormData

from config import ANOMALY_ITEMS, COUNT_GROUPS, PPE_ITEMS
from config.storage import load_branding, save_branding, save_config
from config.versioning import bump_version
from core import events
from core.tracker_manager import reset_counts, save_cameras, start_tracker, stop_tracker
from modules.email_utils import send_email
from modules.tracker import PersonTracker
from modules.utils import require_admin
from schemas.alerts import EmailConfig

# ruff: noqa: B008


router = APIRouter(dependencies=[Depends(require_admin)])
BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_DIR = BASE_DIR / "static" / "logos"
URL_RE = re.compile(r"^https?://")

# Global configuration used when parsing basic settings in tests or scripts.
cfg: dict = {}


@dataclass
class SettingsContext:
    cfg: dict
    trackers_map: Dict[int, "PersonTracker"]
    cams: List[dict]
    redis: Any
    templates: Jinja2Templates
    cfg_path: str
    branding: dict
    branding_path: str
    templates_dir: str
    redisfx: Any | None = None


_context: SettingsContext | None = None


def create_settings_context(
    config: dict,
    trackers: Dict[int, "PersonTracker"],
    cameras: List[dict],
    redis_client,
    templates_path: str,
    config_path: str,
    branding_file: str,
    redis_facade=None,
) -> SettingsContext:
    """Construct and store context for settings routes."""
    global _context
    templates = Jinja2Templates(directory=templates_path)
    templates.env.add_extension("jinja2.ext.do")
    branding = load_branding(branding_file)
    if config.get("helmet_conf_thresh") is not None and "ppe_conf_thresh" not in config:
        config["ppe_conf_thresh"] = config.get("helmet_conf_thresh")
    _context = SettingsContext(
        cfg=config,
        trackers_map=trackers,
        cams=cameras,
        redis=redis_client,
        templates=templates,
        cfg_path=config_path,
        branding=branding,
        branding_path=branding_file,
        templates_dir=templates_path,
        redisfx=redis_facade,
    )
    return _context


def get_settings_context() -> SettingsContext:
    if _context is None:  # pragma: no cover - sanity check
        raise RuntimeError("Settings context not initialised")
    return _context


@router.get("/static/logos/{filename}")
async def serve_logo(filename: str):
    """Serve uploaded logos from a controlled directory."""
    file_path = LOGO_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


def set_cfg(ctx: SettingsContext, new_cfg: dict) -> None:
    """Replace the configuration within the context."""
    ctx.cfg.clear()
    ctx.cfg.update(new_cfg)


def set_branding(ctx: SettingsContext, new_branding: dict) -> None:
    """Replace the branding dictionary within the context."""
    ctx.branding = new_branding


def parse_basic_settings(data: dict, cfg: dict | None = None) -> dict:
    """Return a new configuration with basic settings applied."""
    cfg = cfg or globals().get("cfg", {})
    new_cfg = cfg.copy()
    for key in [
        "max_capacity",
        "warn_threshold",
        "fps",
        "capture_buffer_seconds",
        "frame_skip",
        "line_ratio",
        "v_thresh",
        "debounce",
        "retry_interval",
        "conf_thresh",
        "ppe_conf_thresh",
        "person_model",
        "ppe_model",
        "max_retry",
        "chart_update_freq",
        "profiling_interval",
        "stream_mode",
    ]:
        if key in data:
            val = data[key]
            new_cfg[key] = type(cfg.get(key, val))(val)
    for key in [
        "detect_helmet_color",
        "show_lines",
        "show_ids",
        "show_track_lines",
        "show_counts",
        "enable_live_charts",
        "debug_logs",
        "enable_profiling",
        "enable_person_tracking",
        "email_enabled",
    ]:
        val = str(data.get(key, "")).lower()
        new_cfg[key] = val in {"true", "on", "1"}
    list_fields = {
        "track_ppe": PPE_ITEMS,
        "alert_anomalies": ANOMALY_ITEMS,
        "preview_anomalies": ANOMALY_ITEMS,
        "track_objects": list(COUNT_GROUPS.keys()),
    }
    for field, allowed in list_fields.items():
        if field in data:
            items = data[field] or []
        else:
            items = new_cfg.get(field, [])
        invalid = [item for item in items if item not in allowed]
        if invalid:
            raise ValueError(f"invalid_{field}")
        if field == "track_objects" and "person" not in items:
            items.insert(0, "person")
        new_cfg[field] = items
    if "visitor_mgmt" in data:
        enable = str(data["visitor_mgmt"]).lower() in {"on", "true", "1"}
        licensed = new_cfg.get("license_info", {}).get("features", {}).get("visitor_mgmt", True)
        if enable and not licensed:
            logger.warning("visitor management not licensed; ignoring enable request")
            raise HTTPException(status_code=403)

        new_cfg.setdefault("features", {})["visitor_mgmt"] = enable
    return new_cfg


def parse_email_settings(form: FormData) -> EmailConfig:
    """Extract and validate email settings from a form."""
    data = dict(form)
    email_data: dict = {}
    for key in ["smtp_host", "smtp_user", "from_addr"]:
        val = data.get(key)
        if val:
            email_data[key] = val.strip()
    if data.get("smtp_port"):
        try:
            email_data["smtp_port"] = int(data["smtp_port"])
        except ValueError as exc:  # pragma: no cover - handled by caller
            raise ValueError("invalid_smtp_port") from exc
    if "use_tls" in data:
        email_data["use_tls"] = str(data["use_tls"]).lower() in {"true", "on", "1"}
    if "use_ssl" in data:
        email_data["use_ssl"] = str(data["use_ssl"]).lower() in {"true", "on", "1"}
    if data.get("smtp_pass"):
        email_data["smtp_pass"] = data["smtp_pass"]
    if email_data:
        validated = EmailConfig.model_validate(email_data)
        return validated
    return EmailConfig()


@router.get("/settings")
async def settings_page(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    # Pull the latest config snapshot each request so tests modifying the global
    # config dictionary see the change in rendered templates.
    from jinja2 import TemplateNotFound

    from config import config as current_cfg

    try:
        env = ctx.templates
        return env.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "cfg": current_cfg,
                "now_ts": int(datetime.utcnow().timestamp()),
                "ppe_items": PPE_ITEMS,
                "alert_items": ANOMALY_ITEMS,
                "preview_items": ANOMALY_ITEMS,
                "count_options": list(COUNT_GROUPS.keys()),
            },
        )
    except TemplateNotFound:
        # Some tests initialise the settings router with a temporary template
        # directory that lacks ``settings.html``.  Recreate the templates
        # environment using the original ``templates_dir`` so subsequent
        # requests can still render the built-in templates.
        ctx.templates = Jinja2Templates(directory=ctx.templates_dir)
        ctx.templates.env.add_extension("jinja2.ext.do")
        return ctx.templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "cfg": current_cfg,
                "now_ts": int(datetime.utcnow().timestamp()),
                "ppe_items": PPE_ITEMS,
                "alert_items": ANOMALY_ITEMS,
                "preview_items": ANOMALY_ITEMS,
                "count_options": list(COUNT_GROUPS.keys()),
            },
        )


@router.post("/settings")
async def update_settings(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    form = await request.form()
    data = dict(form)
    data.update(
        {
            "track_ppe": form.getlist("track_ppe"),
            "alert_anomalies": form.getlist("alert_anomalies"),
            "preview_anomalies": form.getlist("preview_anomalies"),
            "track_objects": form.getlist("track_objects"),
        }
    )
    if data.get("password") != ctx.cfg.get("settings_password"):
        return {"saved": False, "error": "auth"}
    raw_email_enabled = data.get("email_enabled")
    force_email = str(data.pop("force_email_enable", "")).lower() in {"true", "on", "1"}
    if raw_email_enabled and not ctx.cfg.get("email", {}).get("last_test_ts"):
        if not force_email:
            return {"saved": False, "error": "email_test_required"}
        logger.warning("email enabled without successful test")
    prev_tracking = ctx.cfg.get("enable_person_tracking", True)
    try:
        new_cfg = parse_basic_settings(data, ctx.cfg)
        email_cfg_obj = parse_email_settings(form)
    except ValueError as exc:
        return {"saved": False, "error": str(exc)}
    email_updates = email_cfg_obj.model_dump(exclude_none=True)
    new_cfg.setdefault("email", {}).update(email_updates)
    branding_updates = ctx.branding.copy()
    branding_updates["company_name"] = data.get(
        "company_name", branding_updates.get("company_name", "")
    )
    branding_updates["site_name"] = data.get("site_name", branding_updates.get("site_name", ""))
    branding_updates["website"] = data.get("website", branding_updates.get("website", ""))
    branding_updates["address"] = data.get("address", branding_updates.get("address", ""))
    branding_updates["phone"] = data.get("phone", branding_updates.get("phone", ""))
    branding_updates["tagline"] = data.get("tagline", branding_updates.get("tagline", ""))
    branding_updates["print_layout"] = data.get(
        "print_layout", branding_updates.get("print_layout", "A5")
    )
    logo = form.get("logo")
    if logo and getattr(logo, "filename", ""):
        LOGO_DIR.mkdir(parents=True, exist_ok=True)
        for old in LOGO_DIR.glob("company_logo.*"):
            old.unlink(missing_ok=True)
        ext = Path(logo.filename).suffix or ".png"
        path = LOGO_DIR / f"company_logo{ext}"
        with path.open("wb") as f:
            f.write(await logo.read())
        branding_updates["company_logo"] = path.name
        branding_updates["company_logo_url"] = f"/static/logos/{path.name}?v={int(time.time())}"
    elif data.get("company_logo_url_input"):
        url = data["company_logo_url_input"].strip()
        if URL_RE.match(url):
            branding_updates["company_logo_url"] = url
            branding_updates["company_logo"] = ""
    footer_logo = form.get("footer_logo")
    if footer_logo and getattr(footer_logo, "filename", ""):
        LOGO_DIR.mkdir(parents=True, exist_ok=True)
        for old in LOGO_DIR.glob("footer_logo.*"):
            old.unlink(missing_ok=True)
        ext = Path(footer_logo.filename).suffix or ".png"
        path = LOGO_DIR / f"footer_logo{ext}"
        with path.open("wb") as f:
            f.write(await footer_logo.read())
        branding_updates["footer_logo"] = path.name
        branding_updates["footer_logo_url"] = f"/static/logos/{path.name}?v={int(time.time())}"
    elif data.get("footer_logo_url_input"):
        url = data["footer_logo_url_input"].strip()
        if URL_RE.match(url):
            branding_updates["footer_logo_url"] = url
            branding_updates["footer_logo"] = ""
    save_branding(branding_updates, ctx.branding_path)
    new_cfg["branding"] = branding_updates
    license_feats = new_cfg.get("license_info", {}).get("features", {})
    user_feats = new_cfg.get("features", {})
    new_cfg["features"] = {
        k: bool(user_feats.get(k)) and bool(license_feats.get(k)) for k in user_feats
    }
    set_branding(ctx, branding_updates)
    set_cfg(ctx, new_cfg)
    save_config(ctx.cfg, ctx.cfg_path, ctx.redis)
    bump_version(ctx.cfg_path)
    if ctx.redisfx:
        await ctx.redisfx.publish("events", json.dumps({"type": events.CONFIG_UPDATED}))
    from config import set_config as set_global_config

    set_global_config(ctx.cfg)
    from routers import cameras as cam_routes

    cam_routes.cfg = ctx.cfg
    cam_routes.get_camera_manager().cfg = ctx.cfg
    for tr in ctx.trackers_map.values():
        tr.update_cfg(ctx.cfg)
    if prev_tracking != ctx.cfg.get("enable_person_tracking", True):
        if ctx.cfg.get("enable_person_tracking", True):
            for cam in ctx.cams:
                if cam.get("enabled", True):
                    start_tracker(cam, ctx.cfg, ctx.trackers_map, ctx.redis)
        else:
            for cid in list(ctx.trackers_map.keys()):
                stop_tracker(cid, ctx.trackers_map)
    from modules.profiler import profiler_manager

    profiler_manager.start(ctx.cfg)
    from routers.config_api import CONFIG_EVENT

    CONFIG_EVENT.set()
    return {
        "saved": True,
        "logo_url": branding_updates.get("company_logo_url"),
        "footer_logo_url": branding_updates.get("footer_logo_url"),
    }


@router.post("/settings/email/test")
async def settings_email_test(
    request: Request, ctx: SettingsContext = Depends(get_settings_context)
):
    data = await request.json()
    recipient = data.get("recipient")
    if not recipient:
        return {"sent": False, "error": "missing_recipient"}
    payload_cfg = {
        k: data.get(k)
        for k in [
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_pass",
            "use_tls",
            "use_ssl",
            "from_addr",
        ]
        if k in data
    }
    merged_cfg = {**ctx.cfg.get("email", {}), **payload_cfg}
    email_cfg = EmailConfig.model_validate(merged_cfg).model_dump(exclude_none=True)
    if not email_cfg.get("smtp_host"):
        return {"sent": False, "error": "missing_smtp_host"}
    email_cfg.setdefault("smtp_port", 587)
    if not email_cfg.get("use_ssl"):
        email_cfg.setdefault("use_tls", True)
    try:
        success, err, response, msg_id = send_email(
            "Test Email",
            "This is a test email from Crowd Manager",
            [recipient],
            cfg=email_cfg,
        )
    except Exception:  # pragma: no cover - handled gracefully
        logger.exception("Test email send failed")
        ctx.cfg.setdefault("email", {})["last_test_ts"] = 0
        save_config(ctx.cfg, ctx.cfg_path, ctx.redis)
        return {"sent": False, "error": "exception"}
    if not success:
        return {"sent": False, "error": err}
    ctx.cfg.setdefault("email", {}).update(email_cfg)
    ctx.cfg["email"]["last_test_ts"] = int(datetime.utcnow().timestamp())
    save_config(ctx.cfg, ctx.cfg_path, ctx.redis)
    return {"sent": True}


@router.post("/settings/branding")
async def branding_update(
    request: Request,
    company_name: str = Form(""),
    logo: UploadFile | None = File(None),
    ctx: SettingsContext = Depends(get_settings_context),
):
    """Handle branding logo uploads with basic validation."""
    if logo is None:
        raise HTTPException(status_code=400, detail="logo required")
    if logo.content_type not in {"image/png", "image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="invalid file")
    data = await logo.read()
    if len(data) > 1_000_000:
        raise HTTPException(status_code=400, detail="file too large")
    return {"saved": True, "company_name": company_name}


@router.get("/settings/export")
async def export_settings(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    """Download configuration and cameras as a single JSON payload."""

    data = {"config": ctx.cfg, "cameras": ctx.cams}
    return JSONResponse(data)


@router.post("/settings/import")
async def import_settings(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    """Import configuration and optional camera list."""
    data = await request.json()
    new_cfg = data.get("config", data)
    cams_data = data.get("cameras")
    ctx.cfg.update(new_cfg)
    save_config(ctx.cfg, ctx.cfg_path, ctx.redis)
    from config import set_config

    set_config(ctx.cfg)
    for tr in ctx.trackers_map.values():
        tr.update_cfg(ctx.cfg)
    from modules.profiler import profiler_manager

    profiler_manager.start(ctx.cfg)
    if isinstance(cams_data, list):
        # stop existing trackers
        for cid in list(ctx.trackers_map.keys()):
            stop_tracker(cid, ctx.trackers_map)
        ctx.cams[:] = cams_data
        save_cameras(ctx.cams, ctx.redis)
        for cam in ctx.cams:
            if cam.get("enabled", True):
                start_tracker(cam, ctx.cfg, ctx.trackers_map, ctx.redis)
    return {"saved": True}


@router.post("/reset")
async def reset_endpoint(ctx: SettingsContext = Depends(get_settings_context)):
    reset_counts(ctx.trackers_map)
    return {"reset": True}


@router.get("/license")
async def license_page(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    """Render a page for entering a license key."""
    return ctx.templates.TemplateResponse("license.html", {"request": request, "cfg": ctx.cfg})


@router.post("/license")
async def activate_license(request: Request, ctx: SettingsContext = Depends(get_settings_context)):
    data = await request.json()
    key = data.get("key")
    from config.license_storage import set as save_license
    from modules.license import verify_license

    info = verify_license(key)
    if not info.get("valid"):
        return {"error": info.get("error")}
    ctx.cfg["license_key"] = key
    ctx.cfg["license_info"] = info
    ctx.cfg["features"] = info.get("features", ctx.cfg.get("features", {}))
    save_config(ctx.cfg, ctx.cfg_path, ctx.redis)
    save_license({"key": key, "info": info})
    ctx.redis.set("license_info", json.dumps(info))
    from config import set_config

    set_config(ctx.cfg)
    return {"activated": True, "features": ctx.cfg["features"]}
