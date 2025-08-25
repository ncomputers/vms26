"""API routes for retrieving structured log events."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from utils.deps import get_redis

router = APIRouter()


@router.get("/api/logs/events")
async def api_log_events(
    camera_id: int | None = Query(None),
    event: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    redis=Depends(get_redis),
):
    try:
        raw_items = await redis.lrange("logs:events", 0, limit - 1)
    except Exception:
        raw_items = []
    items = []
    for raw in raw_items:
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if camera_id is not None and item.get("camera_id") != camera_id:
            continue
        if event and item.get("event") != event:
            continue
        items.append(item)
    return JSONResponse(content=items)


async def events_source(redis, camera_id: int | None) -> AsyncIterator[str]:
    last_ts = 0.0
    while True:
        try:
            raw_items = await redis.lrange("logs:events", 0, -1)
        except Exception:
            raw_items = []
        new_events = []
        for raw in reversed(raw_items):
            try:
                item = json.loads(raw)
            except Exception:
                continue
            ts = float(item.get("ts", 0))
            if ts <= last_ts:
                continue
            if camera_id is not None and item.get("camera_id") != camera_id:
                continue
            new_events.append(item)
        for item in new_events:
            last_ts = max(last_ts, float(item.get("ts", 0)))
            yield f"data: {json.dumps(item)}\n\n"
        await asyncio.sleep(1)


@router.get("/sse/logs/events")
async def sse_log_events(
    camera_id: int | None = Query(None),
    redis=Depends(get_redis),
):
    return StreamingResponse(
        events_source(redis, camera_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
