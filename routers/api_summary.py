"""API endpoint providing aggregated summary counts.

Fetches daily aggregated counts from redis "summaries" hashes and falls back
 to counting raw events when summary data is missing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, Query

from config import COUNT_GROUPS
from modules.events_store import RedisStore
from utils.deps import get_redis

router = APIRouter()


@router.get("/api/v1/summary")
async def get_summary(
    from_: str = Query(..., alias="from", description="Start date YYYY-MM-DD"),
    to: str = Query(..., description="End date YYYY-MM-DD"),
    group: str = Query("person"),
    metric: str = Query("in"),
    redis=Depends(get_redis),
) -> Dict[str, Dict[str, int]]:
    """Return aggregated counts for the requested groups and metrics.

    The routine first attempts to pull counts from daily ``summaries`` hashes
    (``summaries:YYYY-MM-DD``). If data for a day or metric is missing, raw
    events are counted for that period as a fallback.
    """

    groups: List[str] = [g for g in group.split(",") if g]
    metrics: List[str] = [m for m in metric.split(",") if m]

    start_date = datetime.strptime(from_, "%Y-%m-%d").date()
    end_date = datetime.strptime(to, "%Y-%m-%d").date()

    store = RedisStore(redis)
    result: Dict[str, Dict[str, int]] = {g: {m: 0 for m in metrics} for g in groups}

    day = start_date
    while day <= end_date:
        key = f"summaries:{day.isoformat()}"
        summary = redis.hgetall(key) or {}
        start_ts = int(datetime.combine(day, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(day + timedelta(days=1), datetime.min.time()).timestamp() - 1)
        for g in groups:
            labels = COUNT_GROUPS.get(g, [g])
            for m in metrics:
                field = f"{m}_{g}"
                value = summary.get(field)
                if value is not None:
                    result[g][m] += int(value)
                else:
                    count = store.count_events(labels, m, start_ts, end_ts)
                    result[g][m] += count
        day += timedelta(days=1)

    return result
