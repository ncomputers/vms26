"""API endpoints for identity profiles."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from core.context import AppContext, get_app_context

router = APIRouter()

logger = logger.bind(module="api_identities")


def init_context(*_args, **_kwargs) -> None:
    """Initialize router context.

    The API identities endpoints do not require additional setup, but
    ``routers.blueprints`` expects each router to expose an ``init_context``
    hook.  Defining this no-op function keeps application startup from
    failing when the blueprint initializer calls it.
    """

    return None


@router.get("/api/identities/{identity_id}")
def get_identity(identity_id: str, ctx: AppContext = Depends(get_app_context)):  # noqa: B008
    r = ctx.redis
    if r is None:
        return JSONResponse({"error": "unavailable"}, status_code=500)
    data = r.hgetall(f"identity:{identity_id}")
    if not data:
        raise HTTPException(status_code=404, detail="identity_not_found")
    tags = data.get("tags", "")
    visits = r.lrange(f"identity:{identity_id}:visits", 0, -1)
    cams = list(r.smembers(f"identity:{identity_id}:cameras"))
    return {
        "id": identity_id,
        "name": data.get("name", ""),
        "company": data.get("company", ""),
        "tags": tags.split(",") if tags else [],
        "visits": visits,
        "cameras": cams,
    }


@router.post("/api/identities/{identity_id}")
def update_identity(
    identity_id: str,
    payload: dict = Body(...),  # noqa: B008
    ctx: AppContext = Depends(get_app_context),  # noqa: B008
):
    r = ctx.redis
    if r is None:
        return JSONResponse({"error": "unavailable"}, status_code=500)
    fields: dict[str, str] = {}
    for key in ("name", "company"):
        if key in payload:
            fields[key] = str(payload[key])
    if "tags" in payload:
        tags = payload["tags"]
        if isinstance(tags, list):
            tags = ",".join(tags)
        fields["tags"] = str(tags)
    if fields:
        r.hset(f"identity:{identity_id}", mapping=fields)
    return {"updated": True}
