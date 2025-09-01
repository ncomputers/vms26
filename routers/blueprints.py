"""Helper to initialize and register all router modules."""

from __future__ import annotations

from fastapi import FastAPI

from . import alerts, api_identities, api_summary, auth
from . import cameras as cam_routes
from . import config_api, dashboard, debug, detections, diagnostics, feedback, health
from . import help as help_pages
from . import logs, mcp, ppe_reports, profile, reports, rtsp, settings, troubleshooter
from .admin import users as admin_users

# Ordered registry of router modules
MODULES = [
    debug,
    dashboard,
    settings,
    cam_routes,
    reports,
    ppe_reports,
    alerts,
    auth,
    admin_users,
    api_identities,
    api_summary,
    health,
    profile,
    feedback,
    help_pages,
    mcp,
    config_api,
    detections,
    diagnostics,
    troubleshooter,
    rtsp,
    logs,
]


# Prepare shared context for each router
# init_all routine
def init_all(
    cfg: dict,
    trackers,
    cams,
    redis_client,
    templates_dir: str,
    config_path: str,
    branding_path: str,
    redis_facade=None,
) -> None:
    """Initialize shared context for all routers."""
    settings.create_settings_context(
        cfg,
        trackers,
        cams,
        redis_client,
        templates_dir,
        config_path,
        branding_path,
        redis_facade,
    )
    cam_routes.init_context(cfg, cams, trackers, redis_client, templates_dir, redis_facade)
    reports.init_context(cfg, trackers, redis_client, templates_dir, cams, redis_facade)
    ppe_reports.init_context(cfg, trackers, redis_client, templates_dir, redis_facade)
    alerts.init_context(cfg, trackers, redis_client, templates_dir, config_path, redis_facade)
    admin_users.init_context(cfg, redis_client, templates_dir, config_path, redis_facade)
    api_identities.init_context(cfg, redis_client, redis_facade)
    diagnostics.init_context(cfg, trackers, cams, templates_dir, redis_facade)
    troubleshooter.init_context(cfg, trackers, cams, templates_dir, redis_facade)

    profile.init_context(cfg, redis_client, templates_dir, config_path, redis_facade)
    help_pages.init_context(cfg, templates_dir, redis_facade)
    mcp.init_context(cfg, templates_dir, redis_facade)


# Attach initialized routers to the app
# register_blueprints routine
def register_blueprints(app: FastAPI) -> None:
    """Attach all routers to the given FastAPI app."""
    for mod in MODULES:
        app.include_router(mod.router)
