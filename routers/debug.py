"""Debug routes exposing internal testing helpers."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.websockets import WebSocketDisconnect

from modules.capture import ensure_gst as _ensure_gst
from modules.email_utils import sign_token
from modules.rtsp_probe import CANDIDATES
from utils.deps import (
    get_cameras,
    get_redis,
    get_redis_facade,
    get_settings,
    get_templates,
    get_trackers,
)

router = APIRouter()


@router.get("/debug", response_class=HTMLResponse)
async def debug_stats(
    request: Request,
    cfg: dict = Depends(get_settings),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    gst_available = _ensure_gst()
    return templates.TemplateResponse(
        "debug_stats.html",
        {"request": request, "cfg": cfg, "gst_available": gst_available},
    )


async def _run_ffprobe(url: str, use_tcp: bool = True) -> tuple[bool, Dict[str, Any], str]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height",
        "-of",
        "json",
        "-stimeout",
        "15000000",
    ]
    if use_tcp:
        cmd += ["-rtsp_transport", "tcp"]
    cmd.append(url)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except Exception as exc:  # pragma: no cover - subprocess errors
        return False, {}, str(exc)
    ok = proc.returncode == 0
    meta: Dict[str, Any] = {}
    try:
        data = json.loads(stdout.decode())
        if data.get("streams"):
            s = data["streams"][0]
            meta = {
                "width": s.get("width"),
                "height": s.get("height"),
                "codec": s.get("codec_name"),
            }
    except Exception:
        pass
    return ok, meta, stderr.decode()


async def _collect_cam_info(cams, trackers_map, redisfx, secret):
    cam_info = []
    for cam in cams:
        cid = cam.get("id")
        tr = trackers_map.get(cid)
        try:
            raw = await redisfx.get(f"camera_debug:{cid}") or ""
        except Exception:
            logger.bind(cam_id=cid).exception("Failed to fetch camera debug info")
            raw = ""
        debug = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
        attempts = []
        summary = ""
        runtime = []
        if debug:
            try:
                data = json.loads(debug)
                if isinstance(data, dict) and "attempts" in data:
                    for att in data.get("attempts", []):
                        attempts.append(
                            {
                                "backend": att.get("backend", ""),
                                "command": att.get("command") or att.get("pipeline", ""),
                                "error": att.get("error", ""),
                                "exit_code": att.get("exit_code"),
                                "stderr": att.get("stderr", ""),
                            }
                        )
                    summary = data.get("summary") or data.get("final", "")
                    for ev in data.get("runtime", []):
                        ts = ev.get("ts")
                        ev_ts = (
                            datetime.fromtimestamp(ts).isoformat()
                            if isinstance(ts, (int, float))
                            else ""
                        )
                        runtime.append(
                            {
                                "ts": ev_ts,
                                "backend": ev.get("backend", ""),
                                "message": ev.get("message", ""),
                            }
                        )
                else:
                    summary = debug
            except Exception:
                summary = debug
        stats = tr.get_debug_stats() if tr and hasattr(tr, "get_debug_stats") else {}
        # Merge in RTSP connector stats and preview state.
        try:
            from routers import cameras as cam_router

            conn = cam_router.rtsp_connectors.get(cid)
            if conn:
                stats.update(conn.stats())
            stats["preview"] = cam_router.preview_publisher.is_showing(cid)
        except Exception:  # pragma: no cover - defensive
            stats["preview"] = False
        if stats.get("last_capture_ts"):
            stats["last_capture_ts"] = datetime.fromtimestamp(stats["last_capture_ts"]).isoformat()
        if stats.get("last_process_ts"):
            stats["last_process_ts"] = datetime.fromtimestamp(stats["last_process_ts"]).isoformat()
        restart_ts = getattr(tr, "debug_restart_ts", None)
        restart_str = datetime.fromtimestamp(restart_ts).isoformat() if restart_ts else None
        pipeline = getattr(tr, "pipeline_info", "") or ""
        if not pipeline:
            if attempts:
                pipeline = attempts[-1].get("command", "")
            else:
                pipeline = "ffmpeg -rtsp_transport tcp -i {url} -an -f rawvideo -pix_fmt bgr24 -"
        token = ""
        try:
            token = sign_token(str(cid), secret)
        except Exception:
            pass
        info = {
            "id": cid,
            "name": cam.get("name", f"Camera {cid}"),
            "pipeline": pipeline,
            "backend": getattr(tr, "capture_backend", ""),
            "restart_ts": restart_str,
            "debug_attempts": attempts,
            "debug_summary": summary,
            "debug_runtime": runtime,
            "flags": json.dumps(
                {
                    "url": getattr(tr, "src", ""),
                    "type": getattr(tr, "src_type", ""),
                    "resolution": getattr(tr, "resolution", ""),
                    "rtsp_transport": getattr(tr, "rtsp_transport", ""),
                    "stream_mode": getattr(tr, "stream_mode", ""),
                    "ffmpeg_flags": getattr(tr, "cfg", {}).get("ffmpeg_flags", ""),
                },
                indent=2,
            ),
            "stats": stats,
            "rtsp_transport": getattr(tr, "rtsp_transport", ""),
            "ffmpeg_flags": getattr(tr, "cfg", {}).get("ffmpeg_flags", ""),
            "token": token,
            "status": summary or "ok",
        }
        cam_info.append(info)
    return cam_info


@router.get("/debug/camera", response_class=HTMLResponse)
async def debug_overview(
    request: Request,
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    cams: list = Depends(get_cameras),
    redisfx=Depends(get_redis_facade),
    cfg: dict = Depends(get_settings),
    templates: Jinja2Templates = Depends(get_templates),
):
    secret = cfg.get("secret_key", "secret")
    cam_info = await _collect_cam_info(cams, trackers_map, redisfx, secret)
    accept = getattr(request, "headers", {}).get("accept", "")
    if "application/json" in accept:
        return JSONResponse(cam_info)
    return templates.TemplateResponse(
        "debug_overview.html", {"request": request, "cameras": cam_info}
    )


@router.get("/debug/camera/{cam_id}", response_class=HTMLResponse)
async def debug_camera_page(
    request: Request,
    cam_id: int,
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    cams: list = Depends(get_cameras),
    redisfx=Depends(get_redis_facade),
    cfg: dict = Depends(get_settings),
    templates: Jinja2Templates = Depends(get_templates),
):
    secret = cfg.get("secret_key", "secret")
    cam = next((c for c in cams if c.get("id") == cam_id), None)
    if not cam:
        return HTMLResponse("Not found", status_code=404)
    cam_info = await _collect_cam_info([cam], trackers_map, redisfx, secret)
    accept = getattr(request, "headers", {}).get("accept", "")
    if "application/json" in accept:
        return JSONResponse(cam_info[0])
    return templates.TemplateResponse(
        "debug_camera.html", {"request": request, "cameras": cam_info}
    )


@router.post("/debug/camera")
async def debug_camera_update(
    request: Request,
    trackers_map: Dict[int, "PersonTracker"] = Depends(get_trackers),
    redisfx=Depends(get_redis_facade),
):
    data = await request.json()
    cam_id_raw = data.get("cam_id")
    if cam_id_raw is None:
        return JSONResponse({"error": "cam_id required"}, status_code=400)
    try:
        cam_id = int(cam_id_raw)
    except ValueError:
        return JSONResponse({"error": "cam_id must be integer"}, status_code=400)
    tr = trackers_map.get(cam_id)
    if not tr:
        return JSONResponse({"error": "Not found"}, status_code=404)
    params = {k: v for k, v in data.items() if k != "cam_id"}
    flags = params.pop("flags", None)
    pipeline = params.pop("pipeline", None)
    if isinstance(flags, str):
        try:
            params.update(json.loads(flags))
        except json.JSONDecodeError:
            pass
    tr.apply_debug_pipeline(pipeline=pipeline, **params)
    updates = {
        k: v
        for k, v in params.items()
        if k in {"rtsp_transport", "ffmpeg_flags", "url", "backend", "resolution"}
    }
    if pipeline is not None:
        updates["pipeline"] = pipeline
    if updates:
        try:
            await redisfx.hset(f"camera:{cam_id}", mapping=updates)
        except Exception:
            logger.exception("Failed to update camera overrides in Redis")
    tr.restart_capture = True
    command = " ".join((tr.pipeline_info or "").split())
    return {
        "cam_id": cam_id,
        "pipeline": tr.pipeline_info,
        "backend": tr.capture_backend,
        "command": command,
        "restart_ts": getattr(tr, "debug_restart_ts", None),
        "restarting": True,
    }


@router.post("/debug/rtsp-probe")
async def debug_rtsp_probe(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "url required"}, status_code=400)

    tcp_ok, meta, err = await _run_ffprobe(url, use_tcp=True)
    alternates = []

    if not tcp_ok and "404" in err:
        parsed = urlparse(url)
        auth = ""
        if parsed.username:
            auth = parsed.username
            if parsed.password:
                auth += f":{parsed.password}"
            auth += "@"
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        base = f"{parsed.scheme}://{auth}{host}"
        for path in CANDIDATES:
            alt_url = base + path
            ok_alt, meta_alt, _ = await _run_ffprobe(alt_url, use_tcp=True)
            alternates.append({"url": alt_url, "ok": ok_alt, **meta_alt})
            if ok_alt and not meta:
                meta = meta_alt

    if not tcp_ok and not meta:
        _, meta_udp, _ = await _run_ffprobe(url, use_tcp=False)
        meta = meta_udp

    result: Dict[str, Any] = {"tcp": tcp_ok, **meta}
    if alternates:
        result["alternates"] = alternates
    return JSONResponse(result)


@router.get("/debug/yolo", response_class=HTMLResponse)
async def debug_page(
    request: Request, templates: Jinja2Templates = Depends(get_templates)
) -> HTMLResponse:
    """Serve the YOLO debug page."""
    return templates.TemplateResponse("debug_yolo.html", {"request": request})


@router.websocket("/ws/debug/yolo")
async def debug_ws(ws: WebSocket, trackers: Dict[int, Any] = Depends(get_trackers)) -> None:
    await ws.accept()
    tracker = next(iter(trackers.values()), None)
    if tracker is None:
        await ws.send_text("no tracker")
        await ws.close()
        return
    q: deque[Dict[str, Any]] = deque(maxlen=5)
    last = None
    try:
        while True:
            await asyncio.sleep(0.2)
            current = getattr(tracker, "last_detections", None)
            if current is not None and current != last:
                last = current
                payload = {
                    "detections": current,
                    "in_counts": getattr(tracker, "in_counts", {}),
                    "out_counts": getattr(tracker, "out_counts", {}),
                }
                q.append(payload)
                lines = "\n".join(json.dumps(p) for p in q)
                await ws.send_text(lines)
    except WebSocketDisconnect:
        pass
