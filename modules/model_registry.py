"""Shared registry for heavy ML models to avoid redundant loads."""

from __future__ import annotations

from os import getenv
from typing import Dict, Tuple

import psutil
from loguru import logger

from utils.housekeeping import register_cache

try:  # optional heavy dependency
    import torch  # type: ignore

    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
except ModuleNotFoundError:  # pragma: no cover - torch optional in tests
    torch = None

from utils.gpu import get_device

try:  # optional heavy dependency
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover - optional in tests
    YOLO = None

_yolo_models: Dict[Tuple[str, str], YOLO] = {}
register_cache("yolo_models", _yolo_models)


def _log_mem(note: str, device: "torch.device | None" = None) -> None:
    mem = psutil.virtual_memory()
    logger.debug(f"{note}: RAM available {mem.available / (1024**3):.2f} GB")
    if torch and device and device.type == "cuda":
        free, _ = torch.cuda.mem_get_info(device)
        logger.debug(f"{note}: GPU available {free / (1024**3):.2f} GB")


def _resolve_device(device: "torch.device | str | None" = None) -> "torch.device":
    if torch is None:
        raise RuntimeError("torch not available")
    if device is None or (isinstance(device, str) and device == "auto"):
        return get_device()
    if isinstance(device, str):
        device = torch.device(device)
    if device.type.startswith("cuda") and getattr(get_device(), "type", "") != "cuda":
        raise RuntimeError("CUDA requested but not available")
    return device


def get_yolo(path: str, device: "torch.device | str | None" = None) -> YOLO:
    """Return a cached YOLO model for ``path`` on ``device``."""
    if YOLO is None:
        raise RuntimeError("YOLO not available")
    dev = _resolve_device(device)
    key = (path, dev.type)
    model = _yolo_models.get(key)
    if model is None:
        _log_mem(f"Before loading YOLO model {path}", dev)
        model = YOLO(path)
        fp16 = getenv("VMS26_FP16", "auto")
        if dev.type == "cuda":
            model.model.to("cuda")
            if fp16 in ("auto", "1"):
                try:
                    model.model.half()
                except Exception:
                    pass
        else:
            model.model.to("cpu")
        if torch is not None:
            with torch.no_grad():
                dummy = torch.zeros(1, 3, 640, 640, device=dev)
                if dev.type == "cuda" and fp16 in ("auto", "1"):
                    dummy = dummy.half()
                for _ in range(2):
                    model.model(dummy)
        _yolo_models[key] = model
    return model
