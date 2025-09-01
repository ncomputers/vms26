"""Dashboard and stats routes."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import queue
import threading
import time
from typing import Annotated, AsyncIterator, Dict, Iterable

try:  # pragma: no cover - OpenCV is optional
    import cv2  # type: ignore
except Exception:  # pragma: no cover - dependency may be missing
    cv2 = None  # type: ignore[assignment]
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.utils import getenv_num
from config import ANOMALY_ITEMS, PPE_ITEMS, PPE_TASKS
from modules.email_utils import sign_token
from modules.tracker import PersonTracker
from modules.utils import require_roles
from utils.async_utils import run_with_timeout
from utils.deps import (
    get_cameras,
    get_redis,
    get_redis_facade,
    get_settings,
    get_templates,
    get_trackers,
)
from utils.logx import log_throttled
from utils.time import parse_range

# ruff: noqa


# ruff: noqa: B008


router = APIRouter()

logger = logger.bind(module="dashboard")

TARGET_FPS = getenv_num("VMS26_TARGET_FPS", 15, int)


async def _load_stats_totals(redis) -> dict:
    """Fetch totals from Redis or stream and normalize the result."""

    def _decode(val):
        return val.decode() if isinstance(val, (bytes, bytearray)) else val

    def _to_int(val) -> int:
        try:
            return int(_decode(val))
        except Exception:
            return 0

    def _to_json(val) -> dict:
        val = _decode(val)
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return {}
        if isinstance(val, dict):
            return val
        return {}

    try:
        totals = redis.hgetall("stats_totals")
        if inspect.isawaitable(totals):
            totals = await totals
    except Exception:
        totals = None

    if not totals:
        try:
            entries = redis.xrevrange("stats_stream", count=1)
            if inspect.isawaitable(entries):
                entries = await entries
            if entries:
                _id, fields = entries[0]
                raw = fields.get(b"data") or fields.get("data")
                if raw:
                    raw = _decode(raw)
                    totals = json.loads(raw)
        except Exception:
            totals = None

    if not isinstance(totals, dict):
        totals = {}

    clean = {_decode(k): _decode(v) for k, v in totals.items()}
    return {
        "in_count": _to_int(clean.get("in_count", 0)),
        "out_count": _to_int(clean.get("out_count", 0)),
        "current": _to_int(clean.get("current", 0)),
        "anomaly_counts": _to_json(clean.get("anomaly_counts", {})),
        "group_counts": _to_json(clean.get("group_counts", {})),
    }


async def fetch_stats(
    redis, start_ts: int, end_ts: int
) -> tuple[list[int], list[int], list[int], list[int], list[int], dict[str, int]]:
    """Retrieve cumulative stats from Redis."""
    totals = await _load_stats_totals(redis)

    timeline = [end_ts]
    in_counts = [totals["in_count"]]
    out_counts = [totals["out_count"]]
    current_vals = [totals["current"]]
    vehicle_counts = [(totals["group_counts"].get("vehicle", {}) or {}).get("current", 0)]
    anomaly_totals: dict[str, int] = totals["anomaly_counts"]
    return (
        timeline,
        in_counts,
        out_counts,
        vehicle_counts,
        current_vals,
        anomaly_totals,
    )


def aggregate_metrics(
    data: tuple[list[int], list[int], list[int], list[int], list[int], dict[str, int]],
) -> dict:
    """Compute aggregates from raw timeline data."""
    (
        timeline,
        in_counts,
        out_counts,
        vehicle_counts,
        current_vals,
        anomaly_totals,
    ) = data
    current_val = current_vals[-1] if current_vals else 0
    return {
        "timeline": timeline,
        "in_counts": in_counts,
        "out_counts": out_counts,
        "vehicle_counts": vehicle_counts,
        "anomaly_counts": anomaly_totals,
        "current": current_val,
        "current_occupancy": current_val,
        "total_visitors": sum(in_counts),
        "vehicles_detected": sum(vehicle_counts),
        "safety_violations": sum(anomaly_totals.values()),
    }


def compute_group_counts(
    trackers_map: Dict[int, "PersonTracker"], groups: Iterable[str]
) -> dict[str, dict[str, int]]:
    """Aggregate per-group in/out/current counts across trackers."""

    group_counts: dict[str, dict[str, int]] = {}
    for g in groups:
        in_g = sum(getattr(t, "in_counts", {}).get(g, 0) for t in trackers_map.values())
        out_g = sum(getattr(t, "out_counts", {}).get(g, 0) for t in trackers_map.values())
        group_counts[g] = {"in": in_g, "out": out_g, "current": in_g - out_g}
    return group_counts


@router.get("/")
async def index(
    request: Request,
    cfg: dict = Depends(get_settings),
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    cams: list = Depends(get_cameras),
    redis=Depends(get_redis),
    templates: Jinja2Templates = Depends(get_templates),
):
    res = require_roles(request, ["admin", "viewer"])
    if isinstance(res, RedirectResponse):
        return res
    error_message = request.query_params.get("error")
    groups = cfg.get("track_objects", ["person", "vehicle"])
    group_counts = compute_group_counts(trackers_map, groups)
    current = group_counts.get("person", {"current": 0})["current"]
    in_c = group_counts.get("person", {"in": 0})["in"]
    out_c = group_counts.get("person", {"out": 0})["out"]
    max_cap = cfg["max_capacity"]
    warn_lim = max_cap * cfg["warn_threshold"] / 100
    status = "green" if current < warn_lim else "yellow" if current < max_cap else "red"
    active = [c for c in cams if c.get("show", False)]
    secret = cfg.get("secret_key", "secret")
    for cam in active:
        try:
            cam["token"] = sign_token(str(cam.get("id")), secret)
        except Exception:
            cam["token"] = ""
    count_keys = [f"{item}_count" for item in ANOMALY_ITEMS]
    try:
        count_vals = await run_with_timeout(redis.mget, count_keys, timeout=5)
    except asyncio.TimeoutError:
        logger.error("Timed out fetching anomaly counts from Redis")
        return RedirectResponse("/dashboard?error=Unable%20to%20load%20stats", status_code=303)
    anomaly_counts = {
        item: int(val or 0) for item, val in zip(ANOMALY_ITEMS, count_vals, strict=False)
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "max_capacity": max_cap,
            "status": status,
            "current": current,
            "cameras": active,
            "cfg": cfg,
            "anomaly_counts": anomaly_counts,
            "group_counts": group_counts,
            "error_message": error_message,
            "alert_items": ANOMALY_ITEMS,
            "ppe_items": PPE_ITEMS,
        },
    )


async def _stream_response(
    cam_id: int,
    request: Request,
    trackers_map: Dict[int, "PersonTracker"],
    *,
    raw: bool = False,
):
    res = require_roles(request, ["admin", "viewer"])
    if isinstance(res, RedirectResponse):
        return res
    tr = trackers_map.get(cam_id)
    if not tr:
        return HTMLResponse("Not found", status_code=404)

    async def gen():
        if not raw:
            tr.viewers += 1
            if tr.viewers == 1:
                tr.restart_capture = True
        no_frame_logged = False
        last_buf: bytes | None = None
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        interval = 1 / (min(tr.fps, TARGET_FPS) if not raw else TARGET_FPS)
        last_sent = 0.0
        try:
            while True:
                frame = tr.raw_frame if raw else tr.output_frame
                if frame is not None:
                    if no_frame_logged:
                        logger.info(
                            f"[{cam_id}] Resumed frames for {'clean' if raw else 'preview'}"
                        )
                        no_frame_logged = False
                    if raw and hasattr(frame, "download"):
                        frame = frame.download()
                    _, buf = cv2.imencode(".jpg", frame)
                    last_buf = buf.tobytes()
                else:
                    if not no_frame_logged:
                        logger.warning(f"[{cam_id}] No frame for {'clean' if raw else 'preview'}")
                        no_frame_logged = True
                    if last_buf is None:
                        await asyncio.sleep(0.1)
                        continue
                now = time.time()
                wait = interval - (now - last_sent)
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    yield boundary + last_buf + b"\r\n"
                except Exception as exc:
                    log_throttled(
                        logger.warning,
                        f"[{cam_id}] mjpeg broken pipe: {exc}",
                        key=f"dash:{cam_id}:broken_pipe",
                        interval=5,
                    )
                    break
                last_sent = time.time()
        finally:
            if not raw:
                tr.viewers -= 1
                if tr.viewers == 0:
                    tr.restart_capture = True
                    proc = getattr(tr, "proc", None)
                    if proc and hasattr(proc, "kill"):
                        try:
                            proc.kill()
                        except Exception:
                            pass

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/stream/preview/{cam_id}")
async def stream_preview(
    cam_id: int,
    request: Request,
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
):
    return await _stream_response(cam_id, request, trackers_map)


@router.get("/stream/clean/{cam_id}")
async def stream_clean(
    cam_id: int,
    request: Request,
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
):
    return await _stream_response(cam_id, request, trackers_map, raw=True)


async def stats_event_source(
    redis, trackers_map: Dict[int, "PersonTracker"], use_stream: bool
) -> AsyncIterator[str]:
    """Yield dashboard stats as SSE events from Redis."""

    from core.stats import gather_stats
    from modules.events_store import RedisStore

    store = RedisStore(redis)
    while True:
        try:
            init = gather_stats(trackers_map, redis, store)
            yield f"data: {json.dumps(init)}\n\n"
            if use_stream:
                last_id = "$"
                while True:
                    try:
                        msgs = await asyncio.to_thread(
                            redis.xread,
                            {"stats_stream": last_id},
                            block=5000,
                            count=1,
                        )
                    except RedisConnectionError:
                        break
                    if msgs:
                        _name, entries = msgs[0]
                        for entry_id, fields in entries:
                            last_id = entry_id
                            raw = fields.get(b"data")
                            if raw is None:
                                continue
                            data = raw.decode()
                            yield f"data: {data}\n\n"
                    else:
                        yield ": ping\n\n"
            else:
                channel = "stats_updates"
                pubsub = redis.pubsub(ignore_subscribe_messages=True)
                try:
                    pubsub.subscribe(channel)
                    q: queue.Queue = queue.Queue()

                    def reader() -> None:
                        try:
                            for msg in pubsub.listen():
                                q.put(msg)
                        except RedisConnectionError:
                            q.put(None)

                    threading.Thread(target=reader, daemon=True).start()
                    last_msg = time.time()
                    while True:
                        try:
                            msg = await asyncio.to_thread(q.get, timeout=5)
                        except queue.Empty:
                            if time.time() - last_msg > 30:
                                try:
                                    pubsub.ping()
                                    last_msg = time.time()
                                except RedisConnectionError:
                                    break
                            yield ": ping\n\n"
                            continue
                        if msg is None:
                            break
                        if msg.get("type") != "message":
                            continue
                        data = msg["data"]
                        if isinstance(data, bytes):
                            data = data.decode()
                        yield f"data: {data}\n\n"
                        last_msg = time.time()
                finally:
                    try:
                        pubsub.close()
                    except Exception:
                        pass
            await asyncio.sleep(1)
        except RedisConnectionError:
            logger.warning("Redis connection failed; retrying")
            await asyncio.sleep(1)


@router.get("/sse/stats")
async def sse_stats(
    request: Request,
    stream: bool | None = Query(None),
    use_stream: bool | None = Query(None),
    cfg: dict = Depends(get_settings),
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    redis=Depends(get_redis),
):
    """Server-Sent Events endpoint for dashboard stats.

    Defaults to using the Redis stream for reliability. Either ``stream`` or
    ``use_stream`` query parameters may toggle the behaviour."""

    if stream is None:
        stream = use_stream if use_stream is not None else True
    try:
        from core.stats import gather_stats
        from modules.events_store import RedisStore

        gather_stats(trackers_map, redis, RedisStore(redis))
    except (RuntimeError, RedisConnectionError) as e:
        logger.warning("Stats unavailable: {}", e)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve statistics. Check network connection or credentials.",
        )

    return StreamingResponse(
        stats_event_source(redis, trackers_map, stream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/latest_images")
async def latest_images(
    status: str = "no_helmet",
    count: int = 5,
    redisfx=Depends(get_redis_facade),
):
    """Return recent PPE snapshots filtered by status."""
    try:
        entries = await redisfx.zrevrange("ppe_logs", 0, 999)
    except Exception:
        logger.exception("Failed to fetch latest images")
        entries = []
    imgs: list[str] = []
    for item in entries:
        e = json.loads(item)
        if e.get("status") == status and e.get("path"):
            fname = os.path.basename(e["path"])
            imgs.append(f"/snapshots/{fname}")
            if len(imgs) >= count:
                break
    return {"images": imgs}


@router.get("/api/stats")
async def api_stats(
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    redisfx=Depends(get_redis_facade),
    redis=Depends(get_redis),
):
    """Return current dashboard metrics for polling."""
    try:
        entries = await redisfx.call("xrevrange", "stats_stream", count=1)
        if entries:
            _id, fields = entries[0]
            raw = fields.get(b"data") or fields.get("data")
            if raw:
                data = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
                return JSONResponse(content=json.loads(data))
    except Exception:
        logger.exception("Failed to fetch stats from Redis stream")
    from core.stats import gather_stats
    from modules.events_store import RedisStore

    data = gather_stats(trackers_map, redis, RedisStore(redis))
    return JSONResponse(content=data)


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    request: Request,
    range_: Annotated[str, Query(alias="range")] = "7d",
    compare: Annotated[bool, Query()] = False,
    redis=Depends(get_redis),
    cfg: dict = Depends(get_settings),
):
    """Return aggregated dashboard metrics over a timeframe.

    If ``compare`` is true, include metrics for the previous period of equal
    duration under the ``previous`` key.
    """

    start_ts, end_ts = parse_range(range_)
    data = await fetch_stats(redis, start_ts, end_ts)
    result = aggregate_metrics(data)
    result["max_capacity"] = cfg.get("max_capacity", 0)
    return JSONResponse(content=result)


@router.get("/api/camera_info")
async def api_camera_info(
    cams: list = Depends(get_cameras),
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
):
    """Return camera backend information for debugging."""
    data = []
    for cam in cams:
        tr = trackers_map.get(cam["id"])
        info = {
            "id": cam["id"],
            "name": cam["name"],
            "backend": tr.capture_backend if tr else None,
            "pipeline": tr.pipeline_info if tr else "",
            "ppe_running": bool(tr and any(t in PPE_TASKS for t in tr.tasks)),
            "stream_status": getattr(tr, "stream_status", ""),
            "stream_error": getattr(tr, "stream_error", ""),
            "latitude": cam.get("latitude"),
            "longitude": cam.get("longitude"),
        }
        data.append(info)
    return {"cameras": data}
