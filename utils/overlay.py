"""Drawing helpers for overlays on image frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class OverlayThrottler:
    """Decide whether to render debug overlays for a frame."""

    every_n: int = 1
    min_ms: int = 0
    frame_idx: int = 0
    last_draw_ms: int | None = None

    # should_draw routine
    def should_draw(self, now_ms: int) -> bool:
        """Return ``True`` if overlays should be drawn for this frame."""

        draw = self.frame_idx % max(1, self.every_n) == 0
        if draw and self.last_draw_ms is not None:
            if now_ms - self.last_draw_ms < self.min_ms:
                draw = False
        if draw:
            self.last_draw_ms = now_ms
        self.frame_idx += 1
        return draw


def draw_boxes_np(
    img_rgb: np.ndarray, dets: List[Dict], thickness: int = 2
) -> np.ndarray:
    """Draw bounding boxes and optional labels on ``img_rgb``.

    Parameters
    ----------
    img_rgb:
        RGB image as a NumPy array.
    dets:
        List of detection dictionaries with ``bbox`` coordinates and
        optional ``cls``/``conf`` or preformatted ``label``.
    thickness:
        Line thickness for rectangles.

    Returns
    -------
    np.ndarray
        Image array with drawings applied.
    """

    img = Image.fromarray(img_rgb, mode="RGB").copy()
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover - font load errors
        font = None
    H, W = img_rgb.shape[:2]
    for det in dets:
        try:
            x1, y1, x2, y2 = [
                int(max(0, min(W - 1 if i % 2 == 0 else H - 1, v)))
                for i, v in enumerate(det.get("bbox", (0, 0, 0, 0)))
            ]
        except Exception:
            continue
        label = det.get("label") or f"{det.get('cls', '?')} {det.get('conf', 0):.2f}"
        d.rectangle([(x1, y1), (x2, y2)], outline=(0, 255, 0), width=thickness)
        if label:
            if hasattr(d, "textlength"):
                tw = int(d.textlength(label, font=font))
            else:  # pragma: no cover - older Pillow
                tw = len(label) * 7
            th = (getattr(font, "size", 14) if font else 14) + 4
            d.rectangle([(x1, max(0, y1 - th)), (x1 + tw + 6, y1)], fill=(0, 255, 0))
            d.text((x1 + 3, max(0, y1 - th) + 2), label, fill=(0, 0, 0), font=font)
    return np.asarray(img, dtype=np.uint8)


__all__ = ["OverlayThrottler", "draw_boxes_np"]
