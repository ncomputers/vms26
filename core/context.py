from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from fastapi import Request
from fastapi.templating import Jinja2Templates
from redis import Redis


@dataclass
class AppContext:
    """Container for shared application resources."""

    config: dict
    redis: Redis | None
    trackers: Dict[int, Any]
    templates: Jinja2Templates
    branding: dict
    cameras: List[dict]
    redisfx: Any | None = None


def get_app_context(request: Request) -> AppContext:
    """Return application context from the FastAPI app state."""
    ctx = getattr(request.state, "app_context", None)
    if ctx is None:
        app = request.app
        ctx = AppContext(
            config=getattr(app.state, "config", {}),
            redis=getattr(app.state, "redis_client", None),
            trackers=getattr(app.state, "trackers", {}),
            templates=app.state.templates,
            branding=getattr(app.state, "config", {}).get("branding", {}),
            cameras=getattr(app.state, "cameras", []),
            redisfx=getattr(app.state, "redis_facade", None),
        )
        request.state.app_context = ctx
    return ctx
