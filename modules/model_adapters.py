from __future__ import annotations

from typing import Dict, List

import numpy as np

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - torch optional
    torch = None

from ultralytics import YOLO

__all__ = ["BasicAdapter", "PPEAdapter", "get_adapter"]

# Classes to keep for the basic model
COCO_KEEP = {
    0: "person",
    2: "car",
    7: "truck",
    5: "bus",
    3: "motorcycle",
    1: "bicycle",
}


class _BaseAdapter:
    """Common helper for YOLO-based adapters."""

    def __init__(self, weights: str) -> None:
        device = "cpu"
        if torch and torch.cuda.is_available():
            device = "cuda:0"
        self.device = device
        self.model = YOLO(weights)
        self.model.to(device)

    def infer(
        self, bgr: np.ndarray, conf: float = 0.25
    ) -> List[Dict]:  # pragma: no cover - interface
        raise NotImplementedError


class BasicAdapter(_BaseAdapter):
    """Adapter for the COCO-pretrained YOLO model."""

    def __init__(self, weights: str = "models/yolov8n.pt") -> None:
        super().__init__(weights)

    def infer(self, bgr: np.ndarray, conf: float = 0.25) -> List[Dict]:
        res = self.model.predict(bgr[:, :, ::-1], conf=conf, verbose=False)[0]
        out: List[Dict] = []
        for box in res.boxes:
            cid = int(box.cls.item())
            label = COCO_KEEP.get(cid)
            if not label:
                continue
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            out.append(
                {
                    "cls": label,
                    "conf": float(box.conf.item()),
                    "xyxy": [x1, y1, x2, y2],
                }
            )
        return out


class PPEAdapter(_BaseAdapter):
    """Adapter for PPE detection model."""

    def __init__(self, weights: str = "models/ppe.pt") -> None:
        super().__init__(weights)

    def infer(self, bgr: np.ndarray, conf: float = 0.25) -> List[Dict]:
        res = self.model.predict(bgr[:, :, ::-1], conf=conf, verbose=False)[0]
        names = self.model.model.names if hasattr(self.model.model, "names") else self.model.names
        out: List[Dict] = []
        for box in res.boxes:
            cid = int(box.cls.item())
            label = str(names.get(cid, f"cls_{cid}"))
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            out.append(
                {
                    "cls": label,
                    "conf": float(box.conf.item()),
                    "xyxy": [x1, y1, x2, y2],
                }
            )
        return out


def get_adapter(kind: str | None = None) -> _BaseAdapter:
    kind = (kind or "basic").lower()
    if kind == "ppe":
        return PPEAdapter()
    return BasicAdapter()
