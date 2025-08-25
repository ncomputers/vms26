"""Count report routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from redis.exceptions import RedisError

from config import config
from modules import export
from modules.events_store import RedisStore
from modules.utils import require_roles
from schemas.report import ReportQuery
from utils.time import format_ts

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
redisfx = None


# init_context routine
def init_context(
    config: dict,
    trackers: Dict[int, "PersonTracker"],
    redis_client,
    templates_path,
    cameras: List[dict],
    redis_facade=None,
) -> None:
    """Initialize shared context for report routes."""
    global cfg, trackers_map, redis, templates, cams, store, redisfx
    cfg = config
    trackers_map = trackers
    redis = redis_client
    redisfx = redis_facade
    store = RedisStore(redis_client)
    templates = Jinja2Templates(directory=templates_path)
    templates.env.add_extension("jinja2.ext.do")
    cams = cameras


@router.get("/report")
async def report_page(
    request: Request,
    type: str = "person",
    range: str = "",
    include_archived: bool = False,
):
    res = require_roles(request, ["admin"])
    if isinstance(res, RedirectResponse):
        return res
    no_data = True
    no_data_message = "No report data available. Verify the tracker is running or adjust log retention settings."
    error_message = None
    try:
        if (
            redis.zcard("history")
            or redis.zcard("person_logs")
            or redis.zcard("vehicle_logs")
            or redis.zcard("face_logs")
        ):
            no_data = False
    except Exception as exc:
        error_message = "Error retrieving report data"
        logger.exception("report data check failed: {}", exc)
    quick_map = {"7d": "week", "this_month": "month"}
    selected_quick = quick_map.get(range, range)
    cam_list = cams if include_archived else [c for c in cams if not c.get("archived")]
    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "vehicle_enabled": "vehicle" in cfg.get("track_objects", ["person", "vehicle"]),
            "face_enabled": "face" in cfg.get("track_objects", []),
            "plate_enabled": "number_plate" in cfg.get("track_objects", []),
            "cameras": cam_list,
            "labels": cfg.get("count_classes", []),
            "cfg": config,
            "no_data": no_data,
            "error_message": error_message,
            "no_data_message": no_data_message,
            "selected_type": type,
            "selected_quick": selected_quick,
            "include_archived": include_archived,
        },
    )


async def _report_data(query: ReportQuery):
    start_ts = int(query.start.timestamp())
    end_ts = int(query.end.timestamp())
    if query.view == "graph":

        entries = [
            json.loads(e)
            for e in await redisfx.call("zrangebyscore", "history", start_ts, end_ts)
        ]
        times, ins, outs, currents = [], [], [], []
        key_in = f"in_{query.type}"
        key_out = f"out_{query.type}"
        # Baseline to normalize current series to the first sample within the window
        base_in = entries[0].get(key_in, 0) if entries else 0
        base_out = entries[0].get(key_out, 0) if entries else 0
        base = base_in - base_out
        prev_in, prev_out = 0, 0
        for entry in entries:
            ts = entry.get("ts")
            times.append(format_ts(ts, "%Y-%m-%d %H:%M"))
            i = entry.get(key_in, 0)
            o = entry.get(key_out, 0)
            ins.append(i - prev_in)
            outs.append(o - prev_out)
            currents.append(max(0, (i - o) - base))
            prev_in, prev_out = i, o
        data = {"times": times, "ins": ins, "outs": outs, "current": currents}
    else:
        cursor = query.cursor
        last_ts = None
        if isinstance(cursor, int) and cursor > 0:
            last_ts = cursor
        else:
            try:
                cur_data = json.loads(cursor)
                last_ts = cur_data.get("last_ts")
                cur_data.get("last_id")
            except Exception:
                last_ts = None

        key = "events"
        if query.label == "person":
            key = "person_logs"
        elif query.label == "vehicle":
            key = "vehicle_logs"
        elif query.label == "face":
            key = "face_logs"

        if last_ts is None:
            raw_entries = redis.zrevrangebyscore(
                key, end_ts, start_ts, start=0, num=query.rows
            )
        else:
            raw_entries = redis.zrevrangebyscore(
                key, last_ts, start_ts, start=1, num=query.rows
            )

        events = []
        for item in raw_entries:
            try:
                e = json.loads(item)
            except Exception:  # pragma: no cover - bad data
                continue
            if query.cam_id is not None and e.get("cam_id") != query.cam_id:
                continue
            events.append(e)

        next_cursor = None
        if events:
            last_event = events[-1]
            ts_val = last_event.get("ts") or last_event.get("ts_utc")
            next_cursor = {
                "last_ts": ts_val,
                "last_id": str(last_event.get("track_id")),
            }

        rows_out = []
        for e in events:
            ts_utc = e.get("ts") or e.get("ts_utc")
            img_url = None
            path = e.get("path") or e.get("image_path")
            if path:
                img_url = f"/snapshots/{os.path.basename(path)}"
            row = {
                "time": format_ts(ts_utc, "%Y-%m-%d %H:%M") if ts_utc else "",
                "cam_id": e.get("cam_id") or e.get("camera_id"),
                "track_id": e.get("track_id"),
                "direction": e.get("direction"),
                "path": img_url,
                "plate_path": None,
                "label": e.get("label"),
            }
            rows_out.append(row)
        data = {"rows": rows_out, "next_cursor": next_cursor}

    return data


@router.get("/report_data")
async def report_data(query: ReportQuery = Depends(), request: Request = None):
    res = require_roles(request, ["admin"])
    if isinstance(res, RedirectResponse):
        return res
    try:
        return await _report_data(query)
    except RedisError:
        return JSONResponse(
            {"status": "error", "reason": "storage_unavailable"}, status_code=503
        )


@router.get("/report/export")
async def report_export(query: ReportQuery = Depends(), request: Request = None):
    res = require_roles(request, ["admin"])
    if isinstance(res, RedirectResponse):
        return res
    try:
        data = await _report_data(query)
    except RedisError:
        return JSONResponse(
            {"status": "error", "reason": "storage_unavailable"}, status_code=503
        )
    if query.view == "graph":
        try:
            columns = [
                ("time", "Time"),
                ("in", "In"),
                ("out", "Out"),
                ("current", "Current"),
            ]
            rows = [
                {"time": t, "in": i, "out": o, "current": c}
                for t, i, o, c in zip(
                    data["times"], data["ins"], data["outs"], data["current"]
                )
            ]
            return export.export_csv(rows, columns, "count_report")
        except Exception as exc:
            logger.exception("report export failed: {}", exc)
            return JSONResponse(
                {"status": "error", "reason": "export_failed"}, status_code=500
            )
    else:
        rows = data["rows"]
        for row in rows:
            if row.get("path"):
                row["img_file"] = os.path.join(BASE_DIR, row["path"].lstrip("/"))
            if row.get("plate_path"):
                row["plate_file"] = os.path.join(
                    BASE_DIR, row["plate_path"].lstrip("/")
                )
        columns = [
            ("time", "Time"),
            ("cam_id", "Camera"),
            ("track_id", "Track"),
            ("direction", "Direction"),
        ]
        if query.type == "face":
            columns.append(("label", "Face ID"))
        else:
            columns.append(("label", "Label"))
        try:
            # export first image column, ignore second due to simplicity
            img_label = "Snapshot" if query.type == "face" else "Image"
            return export.export_excel(
                rows,
                columns,
                "count_report",
                image_key="img_file",
                image_label=img_label,
            )
        except Exception as exc:
            logger.exception("report export failed: {}", exc)
            return JSONResponse(
                {"status": "error", "reason": "export_failed"}, status_code=500
            )
