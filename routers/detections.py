"""WebSocket endpoint emitting sample detections and demo page."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Annotated, Any, Dict, cast

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect, WebSocketState

from modules.email_utils import sign_token
from utils.deps import get_cameras, get_settings, get_templates, get_trackers
from utils.video import async_get_stream_resolution

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from modules.tracker import PersonTracker
else:  # pragma: no cover - fallback when tracker deps missing
    PersonTracker = Any  # type: ignore


def get_stop_event() -> Any:
    return None


logger = logging.getLogger(__name__)

router = APIRouter()


async def _build_payload(
    cam_id: int,
    tracker: PersonTracker | None,
    cam_cfg: dict,
    enabled_ppe: set[str],
    show_lines: bool = False,
    probe_timeout: float | None = None,
    fallback_ttl: float | None = None,
) -> dict[str, Any]:
    """Construct a single detection payload for ``cam_id``."""
    ori = cam_cfg.get("line_orientation", "vertical")
    if ori not in {"vertical", "horizontal"}:
        ori = "vertical"
    lines: list[list[float]] = []
    ratio: float
    # attempt to load saved line from redis first
    try:  # pragma: no cover - redis not required in tests
        from utils.redis import get_sync_client

        r = get_sync_client()
        data = r.hgetall(f"cam:{cam_id}:line")
        if data:
            x1 = float(data.get("x1", 0.0))
            y1 = float(data.get("y1", 0.0))
            x2 = float(data.get("x2", 1.0))
            y2 = float(data.get("y2", 1.0))
            ori = data.get("orientation", ori)
            lines = [[x1, y1, x2, y2]]
            ratio = x1 if ori == "vertical" else y1
        else:
            raise ValueError
    except Exception:
        # fall back to camera config if redis misses or errors
        line_cfg = cam_cfg.get("line")
        if isinstance(line_cfg, (list, tuple)) and len(line_cfg) == 4:
            x1, y1, x2, y2 = map(float, line_cfg)
            lines = [[x1, y1, x2, y2]]
            ori = cam_cfg.get("line_orientation", ori)
            ratio = x1 if ori == "vertical" else y1
        else:
            try:
                ratio = float(cam_cfg.get("line_ratio", 0.5))
            except (TypeError, ValueError):
                ratio = 0.5
            ratio = max(0.0, min(1.0, ratio))
            lines = [[ratio, 0.0, ratio, 1.0]] if ori == "vertical" else [[0.0, ratio, 1.0, ratio]]
    try:
        if tracker is not None and getattr(tracker, "last_frame_shape", None):
            src_h, src_w = tracker.last_frame_shape
        elif cam_cfg.get("resolution"):
            res = cam_cfg.get("resolution")
            match = re.match(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$", str(res))
            if not match:
                raise ValueError(f"Invalid resolution format: {res}")
            src_w, src_h = map(int, match.groups())
            if src_w <= 0 or src_h <= 0:
                raise ValueError(f"Invalid resolution dimensions: {res}")
            cam_cfg["resolution"] = f"{src_w}x{src_h}"
        else:
            url = cam_cfg.get("url", "")
            if probe_timeout is None:
                probe_timeout = cam_cfg.get("stream_probe_timeout", 10)
            if fallback_ttl is None:
                fallback_ttl = cam_cfg.get("stream_probe_fallback_ttl")
            src_w, src_h = await async_get_stream_resolution(
                url, timeout=probe_timeout, fallback_ttl=fallback_ttl
            )
            cam_cfg["resolution"] = f"{src_w}x{src_h}"
    except Exception:
        src_w, src_h = await async_get_stream_resolution(
            cam_cfg.get("url", ""),
            timeout=probe_timeout or 10,
            fallback_ttl=fallback_ttl,
        )
        cam_cfg["resolution"] = f"{src_w}x{src_h}"

    in_c = out_c = 0
    if tracker is not None:
        in_counts = getattr(tracker, "in_counts", None)
        out_counts = getattr(tracker, "out_counts", None)
        if isinstance(in_counts, dict):
            in_c = int(sum(in_counts.values()))
        else:
            in_c = int(getattr(tracker, "in_count", 0) or 0)
        if isinstance(out_counts, dict):
            out_c = int(sum(out_counts.values()))
        else:
            out_c = int(getattr(tracker, "out_count", 0) or 0)
    counts = {
        k: int(val) for k, val in {"entered": in_c, "exited": out_c, "inside": in_c - out_c}.items()
    }
    counts["inside"] = max(0, counts["inside"])

    tracks: list[dict[str, Any]] = []
    if tracker is not None:
        for tid, info in getattr(tracker, "tracks", {}).items():
            bbox = info.get("bbox") if isinstance(info, dict) else None
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            label = info.get("label") if isinstance(info, dict) else None
            conf_val = info.get("conf") if isinstance(info, dict) else None
            if conf_val is None:
                conf_val = info.get("score") if isinstance(info, dict) else None
            track: dict[str, Any] = {
                "id": tid,
                "box": [x1, y1, x2 - x1, y2 - y1],
                "label": label or "",
                "conf": float(conf_val or 0.0),
            }
            if isinstance(info, dict) and info.get("trail") is not None:
                track["trail"] = info["trail"]
            tracks.append(track)

    ppe_items: list[dict[str, Any]] = []
    if tracker is not None:
        ppe_src = getattr(tracker, "ppe", None)
        if ppe_src is None:
            ppe_src = getattr(tracker, "last_ppe", None)
        if isinstance(ppe_src, list):
            for item in ppe_src:
                if not isinstance(item, dict):
                    continue
                p_type = item.get("type")
                if enabled_ppe and p_type not in enabled_ppe:
                    continue
                box = item.get("box")
                if not (isinstance(box, (list, tuple)) and len(box) == 4):
                    continue
                entry = {"type": p_type, "box": list(box)}
                score = item.get("score")
                if score is not None:
                    entry["score"] = float(score)
                ppe_items.append(entry)

    payload = {
        "camera": cam_id,
        "src": {"w": src_w, "h": src_h},
        "line_orientation": ori,
        "line_ratio": ratio,
        "lines": lines,
        "tracks": tracks,
        "ppe": ppe_items,
        "counts": counts,
    }
    return payload


@router.get("/detections", response_class=HTMLResponse)
async def detections_page(
    request: Request, templates: Jinja2Templates = Depends(get_templates)
) -> HTMLResponse:
    """Serve the simple detections demo page."""
    return templates.TemplateResponse("detections.html", {"request": request})


@router.websocket("/ws/detections")
async def detections_ws(
    ws: WebSocket,
    stop_event: Annotated[Any, Depends(get_stop_event)],
    cfg: dict = Depends(get_settings),
    trackers: Dict[int, PersonTracker] = Depends(get_trackers),
    cameras: list[dict] = Depends(get_cameras),
) -> None:
    cam_q = ws.query_params.get("cam")
    token = ws.query_params.get("token")
    if cam_q is None:
        await ws.close(code=1008)
        return
    try:
        cam_id = int(cam_q)
    except ValueError:
        await ws.close(code=1008)
        return
    expected = sign_token(str(cam_id), cfg.get("secret_key", "secret"))
    if token != expected:
        await ws.accept()
        await ws.send_json({"error": "unauthorized"})
        await ws.close(code=1008)
        return
    await ws.accept()
    stop_event = cast("asyncio.Event | None", stop_event)
    cam_map = {c.get("id"): c for c in cameras}
    cam_cfg = cam_map.get(cam_id)
    if cam_cfg is None:
        await ws.close()
        return

    async def _loop() -> None:
        last_payload: dict[str, Any] | None = None
        while not (stop_event and stop_event.is_set()):
            enabled_ppe = set(cfg.get("track_ppe", []))
            show_lines = bool(cfg.get("show_lines"))
            tracker = trackers.get(cam_id)
            cfg_for_cam = getattr(tracker, "cfg", cam_cfg)
            payload = await _build_payload(
                cam_id,
                tracker,
                cfg_for_cam,
                enabled_ppe,
                show_lines,
                probe_timeout=cfg.get("stream_probe_timeout", 10),
                fallback_ttl=cfg.get("stream_probe_fallback_ttl"),
            )
            if payload != last_payload:
                await ws.send_json(payload)
                last_payload = payload
            await asyncio.sleep(0.2)

    try:
        await _loop()
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover - unexpected errors
        logger.exception("Unexpected error in detections_ws")
        if ws.client_state != WebSocketState.DISCONNECTED:
            await ws.close()
