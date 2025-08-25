from __future__ import annotations

import asyncio
import base64
import io
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from modules.overlay import abs_line_from_ratio, draw_boxes_pil
from modules.registry import get_detector

from modules.utils import require_admin
from routers.cameras import get_camera_manager

try:  # optional heavy dependency
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None

try:  # optional heavy dependency
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    cv2 = None  # type: ignore

try:  # optional heavy dependency
    from PIL import Image, ImageDraw  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    Image = ImageDraw = None  # type: ignore

router = APIRouter(dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


@router.get("/diagnostics/overlay/{cam_id}", response_class=HTMLResponse)
async def diagnostics_overlay(
    cam_id: int,
    request: Request,
    model: str = Query(default="basic", pattern="^(basic|ppe)$"),
    conf: float = Query(default=0.25, ge=0.05, le=0.9),
    tracker: bool = Query(default=False),
    line_orientation: str = Query(
        default="vertical", pattern="^(vertical|horizontal)$"
    ),
    line_ratio: float = Query(default=0.5, ge=0.0, le=1.0),
    src: str | None = Query(default=None),
    simulate: bool = Query(default=False),
):
    """Render diagnostics overlay for a single frame."""

    cm = get_camera_manager()
    ok, frame_bgr, src_detail = await cm.snapshot(cam_id)
    steps = [{"name": "snapshot", "ok": ok, "ms": 0, "detail": src_detail}]
    result = {
        "ok": False,
        "steps": steps,
        "frame": {},
        "dets": [],
        "tracks": [],
        "counts": {"entered": 0, "exited": 0, "inside": 0},
        "line": {
            "orientation": line_orientation,
            "ratio": line_ratio,
            "abs": [0, 0, 0, 0],
        },
        "jpeg": None,
    }

    params = {
        "model": model,
        "conf": conf,
        "tracker": tracker,
        "line_orientation": line_orientation,
        "line_ratio": line_ratio,
        "src": src or "",
        "simulate": simulate,
    }

    if not ok or frame_bgr is None:
        return templates.TemplateResponse(
            "diagnostics_overlay.html",
            {"request": request, "result": result, "params": params, "cam_id": cam_id},
        )

    h, w = frame_bgr.shape[:2]
    result["frame"] = {"w": w, "h": h}

    t0 = time.perf_counter()
    detector = get_detector("basic" if model == "basic" else "ppe")
    try:
        dets = detector.detect(frame_bgr, conf=conf)
        ok_det = True
        detail = f"{len(dets)} boxes"
    except Exception as e:  # pragma: no cover - best effort
        dets = []
        ok_det = False
        detail = str(e)
    steps.append(
        {
            "name": "detect",
            "ok": ok_det,
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )
    result["dets"] = dets
    if not ok_det:
        return templates.TemplateResponse(
            "diagnostics_overlay.html",
            {"request": request, "result": result, "params": params, "cam_id": cam_id},
        )

    # ------------------------------------------------------------------
    # Track step (optional)
    # ------------------------------------------------------------------
    tracks: list[dict] = []
    objs_for_count = dets
    if tracker:
        t0 = time.perf_counter()
        detail = "ok"
        try:
            if DeepSort is None:
                raise RuntimeError("DeepSort not available")
            det_tuples = [
                (d["xyxy"], d.get("conf", 0.0), d.get("cls", "")) for d in dets
            ]
            ds = DeepSort(max_age=10)
            trks = ds.update_tracks(det_tuples, frame=frame_bgr)
            for t in trks:
                if not t.is_confirmed():
                    continue
                x1t, y1t, x2t, y2t = t.to_ltrb()
                tracks.append(
                    {
                        "id": int(t.track_id),
                        "xyxy": [float(x1t), float(y1t), float(x2t), float(y2t)],
                    }
                )
        except Exception as e:  # pragma: no cover - best effort
            detail = str(e)
        steps.append(
            {
                "name": "track",
                "ok": detail == "ok",
                "ms": int((time.perf_counter() - t0) * 1000),
                "detail": detail,
            }
        )
        objs_for_count = tracks or dets
    result["tracks"] = tracks

    # ------------------------------------------------------------------
    # Count step
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    x1, y1, x2, y2 = abs_line_from_ratio(w, h, line_orientation, line_ratio)
    result["line"]["abs"] = [x1, y1, x2, y2]
    detail = "single_frame"
    if simulate:
        entered = exited = 0
        line_start = (x1, y1)
        line_end = (x2, y2)
        for obj in objs_for_count:
            bx1, by1, bx2, by2 = obj["xyxy"]
            cx = (bx1 + bx2) / 2.0
            cy = (by1 + by2) / 2.0
            cur_side = side((cx, cy), line_start, line_end)
            if cur_side == 0:
                continue
            if line_orientation == "vertical":
                prev_pt = (x1 - 20, cy) if cur_side < 0 else (x1 + 20, cy)
            else:
                prev_pt = (cx, y1 + 20) if cur_side < 0 else (cx, y1 - 20)
            prev_side = side(prev_pt, line_start, line_end)
            if prev_side == 0 or prev_side + cur_side != 0:
                continue
            if line_orientation == "horizontal":
                entered_flag = prev_side < 0 and cur_side > 0
            else:
                entered_flag = prev_side > 0 and cur_side < 0
            if entered_flag:
                entered += 1
            else:
                exited += 1
        result["counts"].update({"entered": entered, "exited": exited})
        detail = f"simulated crossings: {entered + exited}"
    steps.append(
        {
            "name": "count",
            "ok": True,
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )

    # ------------------------------------------------------------------
    # Overlay step
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        if Image is None or ImageDraw is None:
            raise RuntimeError("PIL not available")
        img = Image.fromarray(frame_bgr[:, :, ::-1])
        dr = ImageDraw.Draw(img)
        dr.line([(x1, y1), (x2, y2)], fill=(255, 0, 0), width=2)
        draw_boxes_pil(img, dets)
        for trk in tracks:
            tx1, ty1, tx2, ty2 = trk["xyxy"]
            dr.text((tx1, ty1 - 10), f"ID {trk['id']}", fill=(255, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        result["jpeg"] = base64.b64encode(buf.getvalue()).decode("ascii")
        ok_overlay = True
        detail = "ok"
    except Exception as e:  # pragma: no cover - best effort
        ok_overlay = False
        detail = str(e)
    steps.append(
        {
            "name": "overlay",
            "ok": ok_overlay,
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )
    result["ok"] = ok_overlay

    return templates.TemplateResponse(
        "diagnostics_overlay.html",
        {"request": request, "result": result, "params": params, "cam_id": cam_id},
    )


@router.get("/diagnostics/overlay/checks")
async def diagnostics_overlay_checks(
    cam_id: int,
    model: str = Query(default="basic", pattern="^(basic|ppe)$"),
    conf: float = Query(default=0.25, ge=0.05, le=0.9),
    src: str | None = Query(default=None),
):
    """Run basic connectivity and overlay checks for ``cam_id``."""

    steps = []

    url = src
    if url is None:
        cm = get_camera_manager()
        cam = cm._find_cam(cam_id)  # type: ignore[attr-defined]
        if cam:
            url = cam.get("url")
    host = urlsplit(url or "").hostname or ""

    # --------------------------------------------------------------
    # ping host
    # --------------------------------------------------------------
    t0 = time.perf_counter()
    hints: list[str] = []
    detail = "ok"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        ok = proc.returncode == 0
        if not ok:
            detail = (err.decode().strip() or "unreachable")[:200]
            hints = ["verify network", "check host"]
    except Exception as e:  # pragma: no cover - best effort
        ok = False
        detail = str(e)
        hints = ["ping failed"]
    steps.append(
        {
            "name": "ping",
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "hints": hints,
            "detail": detail,
        }
    )

    # --------------------------------------------------------------
    # ffprobe
    # --------------------------------------------------------------
    t0 = time.perf_counter()
    hints = []
    detail = "ok"
    try:
        if not url:
            raise RuntimeError("no_url")
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-t",
            "2",
            url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        ok = proc.returncode == 0
        if not ok:
            detail = (err.decode().strip() or "ffprobe failed")[:200]
            hints = ["verify RTSP URL", "check credentials"]
    except Exception as e:  # pragma: no cover - best effort
        ok = False
        detail = str(e)
        hints = ["ffprobe failed"]
    steps.append(
        {
            "name": "ffprobe",
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "hints": hints,
            "detail": detail,
        }
    )

    # --------------------------------------------------------------
    # snapshot
    # --------------------------------------------------------------
    t0 = time.perf_counter()
    hints = []
    detail = "ok"
    frame_bgr = None
    try:
        if src:
            if cv2 is None:
                raise RuntimeError("cv2 not available")
            cap = cv2.VideoCapture(src)
            start = time.time()
            while time.time() - start < 1.0:
                ret, frm = cap.read()
                if ret and frm is not None:
                    frame_bgr = frm
                    break
                await asyncio.sleep(0.01)
            cap.release()
            if frame_bgr is None:
                detail = "timeout"
        else:
            cm = get_camera_manager()
            ok_snap, frm = await cm.snapshot(cam_id)
            if not ok_snap or frm is None:
                detail = "no_frame"
            else:
                frame_bgr = frm
        ok = detail == "ok"
        if not ok:
            hints = ["snapshot failed"]
    except Exception as e:  # pragma: no cover - best effort
        ok = False
        detail = str(e)
        hints = ["snapshot error"]
    steps.append(
        {
            "name": "snapshot",
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "hints": hints,
            "detail": detail,
        }
    )
    if not ok or frame_bgr is None:
        return {"steps": steps}

    # --------------------------------------------------------------
    # detect
    # --------------------------------------------------------------
    t0 = time.perf_counter()
    hints = []
    detail = "ok"
    dets = []
    try:
        detector = get_detector("basic" if model == "basic" else "ppe")
        dets = detector.detect(frame_bgr, conf=conf)
        ok = len(dets) >= 1
        detail = f"{len(dets)} boxes"
        if not ok:
            hints = ["no detections"]
    except Exception as e:  # pragma: no cover - best effort
        ok = False
        detail = str(e)
        hints = ["detector error"]
    steps.append(
        {
            "name": "detect",
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "hints": hints,
            "detail": detail,
        }
    )
    if not ok:
        return {"steps": steps}

    # --------------------------------------------------------------
    # overlay
    # --------------------------------------------------------------
    t0 = time.perf_counter()
    hints = []
    detail = "ok"
    try:
        if Image is None:
            raise RuntimeError("PIL not available")
        frame_rgb = frame_bgr[:, :, ::-1]
        img = Image.fromarray(frame_rgb)
        draw_boxes_pil(img, dets)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        base64.b64encode(buf.getvalue()).decode("ascii")
        ok = True
    except Exception as e:  # pragma: no cover - best effort
        ok = False
        detail = str(e)
        hints = ["overlay error"]
    steps.append(
        {
            "name": "overlay",
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "hints": hints,
            "detail": detail,
        }
    )

    return {"steps": steps}


# init_context routine
def init_context(
    cfg: dict,
    trackers,
    cams,
    templates_path: str,
    redis_facade=None,
) -> None:  # pragma: no cover - simple hook
    """Initialize router-level state. Diagnostics router does not require context,
    but this stub satisfies the blueprint loader."""
    return None
