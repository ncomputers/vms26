from __future__ import annotations

"""Time-related helper functions."""

from datetime import datetime
from zoneinfo import ZoneInfo

from config import config as shared_config


def format_ts(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Return formatted string for the given timestamp."""
    tzname = shared_config.get("timezone", "Asia/Kolkata")
    tz = ZoneInfo(tzname)
    return datetime.fromtimestamp(ts, tz).strftime(fmt)


def parse_range(range_str: str) -> tuple[int, int]:
    """Return start and end timestamps for the given range string.

    The range string is case-insensitive and may be one of:
    - "today" or "1d": start of current day to now
    - "this_month" or "month": start of current month to now
    - anything else: last 7 days
    """

    tzname = shared_config.get("timezone", "Asia/Kolkata")
    tz = ZoneInfo(tzname)
    now_dt = datetime.now(tz)
    now = int(now_dt.timestamp())
    tf = (range_str if isinstance(range_str, str) else "7d").lower()
    today = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if tf in {"today", "1d"}:
        start_ts = int(today.timestamp())
    elif tf in {"this_month", "month"}:
        start_ts = int(today.replace(day=1).timestamp())
    else:
        start_ts = now - 7 * 86400
    return start_ts, now
