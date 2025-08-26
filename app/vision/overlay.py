"""Pure overlay rendering utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils.jpeg import encode_jpeg


@dataclass
class LineCfg:
    orientation: str = "vertical"
    ratio: float = 0.5


@dataclass
class Track:
    box: tuple[float, float, float, float]
    id: Optional[int] = None
    label: str = ""
    conf: Optional[float] = None


@dataclass
class PpeItem:
    type: str
    box: tuple[float, float, float, float]
    score: Optional[float] = None


@dataclass
class OverlayInput:
    frame_np: np.ndarray
    src_w: int
    src_h: int
    counts: Dict[str, int]
    tracks: List[Track]
    ppe: List[PpeItem]
    line: Optional[LineCfg] = None
    camera_id: str = ""


def _load_font():
    try:
        return ImageFont.load_default()
    except Exception:  # pragma: no cover - font load errors
        return None


def render(
    input: OverlayInput,
    show_boxes: bool = True,
    show_counts: bool = True,
    show_ppe: bool = True,
    quality: int | None = None,
) -> bytes:
    """Render overlays on ``input.frame_np`` and return JPEG bytes.

    The input frame array is never mutated.
    """

    img = Image.fromarray(input.frame_np).copy()
    draw = ImageDraw.Draw(img)
    font = _load_font()

    scale_x = img.width / max(1, input.src_w)
    scale_y = img.height / max(1, input.src_h)

    if input.line:
        if input.line.orientation == "vertical":
            x = int(input.line.ratio * img.width)
            draw.line([(x, 0), (x, img.height)], fill=(255, 0, 0), width=2)
        else:
            y = int(input.line.ratio * img.height)
            draw.line([(0, y), (img.width, y)], fill=(255, 0, 0), width=2)

    if show_boxes:
        for tr in input.tracks:
            x1, y1, x2, y2 = tr.box
            xi1 = int(x1 * scale_x)
            yi1 = int(y1 * scale_y)
            xi2 = int(x2 * scale_x)
            yi2 = int(y2 * scale_y)
            draw.rectangle([xi1, yi1, xi2, yi2], outline=(0, 255, 0), width=2)
            label = tr.label or ""
            if tr.id is not None:
                label = f"{label} {tr.id}".strip()
            if tr.conf is not None:
                label = f"{label} {tr.conf:.2f}".strip()
            if label:
                tw = (
                    draw.textlength(label, font=font)
                    if hasattr(draw, "textlength")
                    else len(label) * 7
                )
                th = (getattr(font, "size", 14) if font else 14) + 4
                draw.rectangle(
                    [xi1, max(0, yi1 - th), xi1 + int(tw) + 6, yi1],
                    fill=(0, 255, 0),
                )
                draw.text(
                    (xi1 + 3, max(0, yi1 - th) + 2),
                    label,
                    fill=(0, 0, 0),
                    font=font,
                )

    if show_ppe:
        for item in input.ppe:
            x1, y1, x2, y2 = item.box
            xi1 = int(x1 * scale_x)
            yi1 = int(y1 * scale_y)
            xi2 = int(x2 * scale_x)
            yi2 = int(y2 * scale_y)
            draw.rectangle([xi1, yi1, xi2, yi2], outline=(255, 255, 0), width=2)
            label = item.type
            if item.score is not None:
                label = f"{label} {item.score:.2f}".strip()
            if label:
                tw = (
                    draw.textlength(label, font=font)
                    if hasattr(draw, "textlength")
                    else len(label) * 7
                )
                th = (getattr(font, "size", 14) if font else 14) + 4
                draw.rectangle(
                    [xi1, max(0, yi1 - th), xi1 + int(tw) + 6, yi1],
                    fill=(255, 255, 0),
                )
                draw.text(
                    (xi1 + 3, max(0, yi1 - th) + 2),
                    label,
                    fill=(0, 0, 0),
                    font=font,
                )

    if show_counts:
        in_count = int(input.counts.get("entered", 0))
        out_count = int(input.counts.get("exited", 0))
        inside = int(input.counts.get("inside", in_count - out_count))
        inside = max(0, inside)
        draw.text((10, 10), f"Entered: {in_count}", fill=(0, 255, 0), font=font)
        draw.text((10, 30), f"Exited: {out_count}", fill=(255, 0, 0), font=font)
        draw.text((10, 50), f"Inside: {inside}", fill=(255, 255, 0), font=font)

    arr_rgb = np.asarray(img)
    arr_bgr = arr_rgb[:, :, ::-1]
    return encode_jpeg(arr_bgr, quality)


def render_from_legacy(
    frame_np: np.ndarray,
    src_w: int,
    src_h: int,
    counts_dict: Dict[str, int] | None,
    tracks_list: List[Dict] | None,
    ppe_list: List[Dict] | None,
    line_cfg: Dict | None,
    camera_id: str,
) -> bytes:
    """Compatibility adapter converting legacy shapes to :class:`OverlayInput`."""

    counts = counts_dict or {}

    tracks: List[Track] = []
    for t in tracks_list or []:
        box = t.get("box") or t.get("bbox")
        if not box or len(box) != 4:
            continue
        x1, y1, x2, y2 = box
        if x2 <= x1 or y2 <= y1:
            w = x2
            h = y2
            x2 = x1 + w
            y2 = y1 + h
        tracks.append(
            Track(
                box=(float(x1), float(y1), float(x2), float(y2)),
                id=t.get("id"),
                label=t.get("label") or t.get("cls") or "",
                conf=t.get("conf"),
            )
        )

    ppe_items: List[PpeItem] = []
    for p in ppe_list or []:
        box = p.get("box") or p.get("bbox")
        if not box or len(box) != 4:
            continue
        x1, y1, x2, y2 = box
        if x2 <= x1 or y2 <= y1:
            w = x2
            h = y2
            x2 = x1 + w
            y2 = y1 + h
        ppe_items.append(
            PpeItem(
                type=p.get("type", ""),
                box=(float(x1), float(y1), float(x2), float(y2)),
                score=p.get("score"),
            )
        )

    line = None
    if line_cfg:
        ori = (
            line_cfg.get("orientation")
            or line_cfg.get("line_orientation")
            or "vertical"
        )
        ratio = (
            line_cfg.get("ratio")
            or line_cfg.get("line_ratio")
            or line_cfg.get("x1")
            or line_cfg.get("y1")
            or 0.5
        )
        try:
            ratio_f = float(ratio)
        except Exception:
            ratio_f = 0.5
        line = LineCfg(orientation=str(ori), ratio=ratio_f)

    inp = OverlayInput(
        frame_np=frame_np,
        src_w=src_w,
        src_h=src_h,
        counts=counts,
        tracks=tracks,
        ppe=ppe_items,
        line=line,
        camera_id=camera_id,
    )
    return render(inp)


__all__ = ["OverlayInput", "render", "render_from_legacy"]
