"""Object detection utilities for the tracker package."""

from __future__ import annotations

from os import getenv
from typing import Any, List, Tuple

import numpy as np

try:  # optional heavy dependency
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - torch is optional in tests
    torch = None

from app.core.prof import profiled
from modules.profiler import profile_predict

try:  # pragma: no cover - Redis optional in tests
    from redis.exceptions import RedisError

    from utils.redis import get_sync_client
except Exception:  # pragma: no cover - fallback when redis missing
    get_sync_client = None  # type: ignore
    RedisError = Exception  # type: ignore

# Mapping of alias names to sets of YOLO labels. ``track_objects`` may include
# these aliases so the detector will match any of the corresponding labels.
GROUP_ALIASES = {"vehicle": {"car", "truck", "bus", "motorbike", "motorcycle", "bicycle"}}


def resolve_group(label: str, groups: List[str]) -> str | None:
    """Return matching group name for a YOLO label or ``None``."""
    return next(
        (g for g in groups if label == g or label in GROUP_ALIASES.get(g, set())),
        None,
    )


class Detector:
    """Run object detection and format results for tracking."""

    def __init__(self, model: Any, device: Any) -> None:
        self.model = model
        self.device = device
        # Record model/backend info for diagnostics
        try:
            if get_sync_client is not None:
                client = get_sync_client()
                backend = getattr(model, "__class__", type(model)).__name__
                device_name = getattr(device, "type", str(device))
                client.set("detector:warm", f"{backend}:{device_name}")
        except (RedisError, OSError, AttributeError):
            pass

    @profiled("det")
    def detect(self, frame: Any, groups: List[str]) -> List[Tuple[tuple, float, str]]:
        """Return a list of ``(xywh, conf, group)`` detections."""
        conf_thres = float(getenv("VMS26_CONF", "0.25"))
        iou_thres = float(getenv("VMS26_IOU", "0.45"))
        results = profile_predict(
            self.model,
            "Tracker",
            frame,
            device=self.device,
            verbose=False,
            conf=conf_thres,
            iou=iou_thres,
        )[0]
        boxes = results.boxes.data
        if hasattr(boxes, "tolist"):
            boxes = boxes.tolist()
        if torch is not None and hasattr(torch, "tensor"):
            boxes = torch.tensor(boxes)
            tensor_mode = True
        else:
            boxes = np.asarray(boxes)
            tensor_mode = False
        if (boxes.numel() if tensor_mode else boxes.size) > 0:
            cls_idx = boxes[:, 5].long().cpu().numpy() if tensor_mode else boxes[:, 5].astype(int)
            names = [self.model.names[i] for i in range(len(self.model.names))]
            label_groups = np.array([resolve_group(n, groups) for n in names], dtype=object)
            groups_arr = label_groups[cls_idx]
            mask = groups_arr != None
            if mask.any():
                if tensor_mode:
                    mask_t = torch.from_numpy(mask).to(boxes.device)
                    xyxy = boxes[mask_t, :4].cpu().numpy()
                    conf = boxes[mask_t, 4].cpu().numpy()
                else:
                    xyxy = boxes[mask, :4]
                    conf = boxes[mask, 4]
                xywh = xyxy.copy()
                xywh[:, 2:] -= xywh[:, :2]
                detections = [
                    (tuple(bb), cf, gr)
                    for bb, cf, gr in zip(
                        xywh.tolist(), conf.tolist(), groups_arr[mask].tolist(), strict=False
                    )
                    if bb[2] >= 12 and bb[3] >= 12
                ]
            else:
                detections = []
        else:
            detections = []
        return detections

    @profiled("det")
    def detect_batch(
        self, frames: List[Any], groups: List[str]
    ) -> List[List[Tuple[tuple, float, str]]]:
        """Run detection on a batch of frames."""
        conf_thres = float(getenv("VMS26_CONF", "0.25"))
        iou_thres = float(getenv("VMS26_IOU", "0.45"))
        results = profile_predict(
            self.model,
            "Tracker",
            frames,
            device=self.device,
            verbose=False,
            conf=conf_thres,
            iou=iou_thres,
        )
        batch: List[List[Tuple[tuple, float, str]]] = []
        for res in results:
            boxes = res.boxes.data
            if hasattr(boxes, "tolist"):
                boxes = boxes.tolist()
            if torch is not None and hasattr(torch, "tensor"):
                boxes = torch.tensor(boxes)
                tensor_mode = True
            else:
                boxes = np.asarray(boxes)
                tensor_mode = False
            if (boxes.numel() if tensor_mode else boxes.size) > 0:
                cls_idx = (
                    boxes[:, 5].long().cpu().numpy() if tensor_mode else boxes[:, 5].astype(int)
                )
                names = [self.model.names[i] for i in range(len(self.model.names))]
                label_groups = np.array([resolve_group(n, groups) for n in names], dtype=object)
                groups_arr = label_groups[cls_idx]
                mask = groups_arr != None
                if mask.any():
                    if tensor_mode:
                        mask_t = torch.from_numpy(mask).to(boxes.device)
                        xyxy = boxes[mask_t, :4].cpu().numpy()
                        conf = boxes[mask_t, 4].cpu().numpy()
                    else:
                        xyxy = boxes[mask, :4]
                        conf = boxes[mask, 4]
                    xywh = xyxy.copy()
                    xywh[:, 2:] -= xywh[:, :2]
                    dets = [
                        (tuple(bb), cf, gr)
                        for bb, cf, gr in zip(
                            xywh.tolist(), conf.tolist(), groups_arr[mask].tolist(), strict=False
                        )
                        if bb[2] >= 12 and bb[3] >= 12
                    ]
                else:
                    dets = []
            else:
                dets = []
            batch.append(dets)
        return batch


__all__ = ["Detector", "resolve_group", "GROUP_ALIASES"]
