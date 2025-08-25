"""Dependency providers for shared application state."""

from __future__ import annotations

from typing import Dict, List

import redis.asyncio as redis
from fastapi.templating import Jinja2Templates
from starlette.requests import HTTPConnection

from modules.tracker import PersonTracker


def get_settings(request: HTTPConnection) -> dict:
    return request.app.state.config


def get_trackers(request: HTTPConnection) -> Dict[int, PersonTracker]:
    return request.app.state.trackers


def get_cameras(request: HTTPConnection) -> List[dict]:
    cams = request.app.state.cameras
    include = False
    if request.scope.get("type") == "http" and request.query_params.get("include_archived"):
        include = True
    if include:
        return cams
    return [c for c in cams if not c.get("archived")]


def get_redis(request: HTTPConnection) -> redis.Redis:
    return request.app.state.redis_client


def get_redis_facade(request: HTTPConnection):
    return request.app.state.redis_facade


def get_templates(request: HTTPConnection) -> Jinja2Templates:
    return request.app.state.templates
