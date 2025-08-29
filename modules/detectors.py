from __future__ import annotations

from typing import Dict, List

import numpy as np
from ultralytics import YOLO

# COCO class ids of interest for "basic"
COCO_KEEP = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck", 1: "bicycle"}


class BasicDetector:
    def __init__(self, weights_path: str = "models/yolov8n.pt", device: str | None = None):
        self.model = YOLO(weights_path)
        if device:
            self.model.to(device)

    def detect(self, bgr: np.ndarray, conf: float = 0.25) -> List[Dict]:
        """
        Return list of dict: {"cls_id": int, "cls": str, "conf": float, "xyxy": [x1,y1,x2,y2]}
        Coordinates are in the source frame space (NO letterbox scaling needed by caller).
        """
        res = self.model.predict(bgr[:, :, ::-1], conf=conf, verbose=False)[0]  # pass RGB
        out: List[Dict] = []
        for b in res.boxes:
            cid = int(b.cls.item())
            if cid not in COCO_KEEP:
                continue
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            out.append(
                {
                    "cls_id": cid,
                    "cls": COCO_KEEP[cid],
                    "conf": float(b.conf.item()),
                    "xyxy": [x1, y1, x2, y2],
                }
            )
        return out


class PPEDetector:
    def __init__(self, weights_path: str = "models/ppe.pt", device: str | None = None):
        self.model = YOLO(weights_path)
        if device:
            self.model.to(device)

    def detect(self, bgr: np.ndarray, conf: float = 0.25) -> List[Dict]:
        """
        Return list of dict: {"cls": str, "conf": float, "xyxy": [x1,y1,x2,y2]}
        Class names come from model.names.
        """
        res = self.model.predict(bgr[:, :, ::-1], conf=conf, verbose=False)[0]
        names = self.model.model.names if hasattr(self.model.model, "names") else self.model.names
        out: List[Dict] = []
        for b in res.boxes:
            cid = int(b.cls.item())
            label = str(names.get(cid, f"cls_{cid}"))
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            out.append(
                {
                    "cls_id": cid,
                    "cls": label,
                    "conf": float(b.conf.item()),
                    "xyxy": [x1, y1, x2, y2],
                }
            )
        return out


def make_detector(kind: str, device: str | None = None):
    kind = (kind or "basic").lower()
    if kind == "ppe":
        return PPEDetector(device=device)
    return BasicDetector(device=device)
