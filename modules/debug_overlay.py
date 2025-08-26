from __future__ import annotations

import base64
import io
import logging
import time
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw

from modules.detectors import make_detector
from modules.overlay import abs_line_from_ratio, draw_boxes_pil
from routers.cameras import get_camera_manager

try:  # optional heavy dependency
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    cv2 = None  # type: ignore

try:  # optional heavy dependency
    from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    DeepSort = None

try:
    from pathlib import Path
    from PIL import ImageFont

    font_path = Path(__file__).resolve().parents[1] / "static" / "fonts" / "DejaVuSans.ttf"
    FONT = ImageFont.truetype(str(font_path), 14)
except Exception:  # pragma: no cover - font is optional
    from PIL import ImageFont as _IF

    FONT = _IF.load_default()


def side(
    point: Tuple[float, float],
    a: Tuple[float, float],
    b: Tuple[float, float],
    eps: float = 2.0,
) -> int:
    ax, ay = a
    bx, by = b
    px, py = point
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) < eps:
        return 0
    return 1 if cross > 0 else -1


async def run_overlay_probe(
    cam_id: int,
    *,
    src: str | None = None,
    model: str = "basic",
    conf: float = 0.25,
    tracker: bool = False,
    line_orientation: str = "vertical",
    line_ratio: float = 0.5,
    simulate: bool = False,
) -> Dict:
    """Run a single-frame probe with optional tracking and overlay.

    Returns a dictionary with detailed step timing and overlay information.
    """

    result: Dict = {
        "ok": False,
        "steps": [],
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

    steps: List[Dict] = result["steps"]

    # ------------------------------------------------------------------
    # Snapshot step
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    frame_bgr = None
    detail = "ok"
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
                time.sleep(0.01)
            cap.release()
            if frame_bgr is None:
                detail = "timeout"
        else:
            cm = get_camera_manager()
            ok, frm = await cm.snapshot(cam_id)
            if not ok or frm is None:
                detail = "no_frame"
            else:
                frame_bgr = frm
    except Exception as e:  # pragma: no cover - best effort
        detail = str(e)

    steps.append(
        {
            "name": "snapshot",
            "ok": detail == "ok",
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )
    if detail != "ok" or frame_bgr is None:
        return result

    h, w = frame_bgr.shape[:2]
    result["frame"] = {"w": w, "h": h}

    # ------------------------------------------------------------------
    # Detect step
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    detail = "ok"
    dets: List[Dict] = []
    try:
        detector = make_detector(model, device=None)
        dets = detector.detect(frame_bgr, conf=conf)
    except Exception as e:  # pragma: no cover - best effort
        detail = str(e)
    steps.append(
        {
            "name": "detect",
            "ok": detail == "ok",
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )
    if detail != "ok":
        return result
    result["dets"] = dets

    # sanity clamp
    warned = False
    for d in dets:
        x1, y1, x2, y2 = d["xyxy"]
        xi1, yi1, xi2, yi2 = int(x1), int(y1), int(x2), int(y2)
        if not (0 <= xi1 < w and 0 <= yi1 < h and 0 <= xi2 < w and 0 <= yi2 < h):
            xi1 = max(0, min(xi1, w - 1))
            yi1 = max(0, min(yi1, h - 1))
            xi2 = max(0, min(xi2, w - 1))
            yi2 = max(0, min(yi2, h - 1))
            d["xyxy"] = [float(xi1), float(yi1), float(xi2), float(yi2)]
            if not warned:
                logging.warning("detection bbox outside frame bounds; clamping")
                warned = True

    # ------------------------------------------------------------------
    # Track step (optional)
    # ------------------------------------------------------------------
    tracks: List[Dict] = []
    if tracker:
        t0 = time.perf_counter()
        detail = "ok"
        try:
            if DeepSort is None:
                raise RuntimeError("DeepSort not available")
            ds = DeepSort(max_age=1)
            det_tuples = [
                (
                    (d["xyxy"][0], d["xyxy"][1], d["xyxy"][2], d["xyxy"][3]),
                    d["conf"],
                    d["cls"],
                )
                for d in dets
            ]
            trks = ds.update_tracks(det_tuples, frame=frame_bgr)
            for t in trks:
                if not t.is_confirmed():
                    continue
                x1, y1, x2, y2 = t.to_ltrb()
                tracks.append(
                    {
                        "id": int(t.track_id),
                        "xyxy": [float(x1), float(y1), float(x2), float(y2)],
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
        if detail != "ok":
            result["tracks"] = tracks
            return result
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
        for d in dets:
            bx1, by1, bx2, by2 = d["xyxy"]
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
    detail = "ok"
    try:
        img = Image.fromarray(frame_bgr[:, :, ::-1])
        dr = ImageDraw.Draw(img)
        dr.line([(x1, y1), (x2, y2)], fill=(255, 0, 0), width=2)
        draw_boxes_pil(img, dets, thickness=2, font=FONT)
        for trk in tracks:
            tx1, ty1, _, _ = trk["xyxy"]
            dr.text((tx1 + 4, ty1 + 4), str(trk["id"]), fill=(255, 0, 0), font=FONT)
        bio = io.BytesIO()
        img.save(bio, format="JPEG", quality=85)
        result["jpeg"] = base64.b64encode(bio.getvalue()).decode()
    except Exception as e:  # pragma: no cover - best effort
        detail = str(e)
    steps.append(
        {
            "name": "overlay",
            "ok": detail == "ok",
            "ms": int((time.perf_counter() - t0) * 1000),
            "detail": detail,
        }
    )
    if detail != "ok":
        return result

    result["ok"] = True
    return result
