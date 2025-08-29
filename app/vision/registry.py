"""Lazy model registry for vision models.

Provides a single entry point to load and share YOLO models across
workers. Models are loaded on first use and cached keyed by
``(name, device, half)``.

Environment variables:
    VMS21_YOLO_PERSON: path to person detection model (default ``yolov8s.pt``)
    VMS21_YOLO_PPE: path to PPE detection model (default ``ppe.pt``)

Example::

    from app.vision import registry
    model = registry.get("yolo_person")

"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

from loguru import logger

from utils.housekeeping import register_cache

try:  # heavy optional dependency
    import torch  # type: ignore
except Exception:  # pragma: no cover - torch optional
    torch = None

try:  # heavy optional dependency
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover - ultralytics optional
    YOLO = None

# map registry names to env vars and defaults
_MODEL_ENVS = {
    "yolo_person": ("VMS21_YOLO_PERSON", "yolov8s.pt"),
    "yolo_ppe": ("VMS21_YOLO_PPE", "ppe.pt"),
}

# internal cache for loaded models
_CACHE: Dict[Tuple[str, str, bool], YOLO] = {}
register_cache("vision_models", _CACHE)


def _resolve_device(device: str | None) -> str:
    """Return a device string, preferring CUDA when available."""
    if torch is None:
        if device and device not in {"cpu", "auto"}:
            raise RuntimeError("torch not available; only CPU supported")
        return "cpu"
    if device in (None, "auto"):
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def _model_path(name: str) -> str:
    """Resolve model path from environment or defaults."""
    env, default = _MODEL_ENVS[name]
    path = os.getenv(env, default)
    if not Path(path).exists():
        raise RuntimeError(f"Model file for '{name}' not found: {path}")
    return path


def get(name: str, device: str | None = None, half: bool = True):
    """Return a cached YOLO model instance."""
    if YOLO is None:
        raise RuntimeError("ultralytics YOLO not available")
    if name not in _MODEL_ENVS:
        raise KeyError(name)
    dev = _resolve_device(device)
    key = (name, dev, half)
    model = _CACHE.get(key)
    if model is None:
        path = _model_path(name)
        model = YOLO(path)
        model.model.to(dev)
        if half and dev.startswith("cuda"):
            model.model.half()
        _CACHE[key] = model
        if dev.startswith("cuda") and torch is not None:
            try:
                idx = torch.cuda.current_device()
                free, total = torch.cuda.mem_get_info(idx)
                gpu_name = torch.cuda.get_device_name(idx)
                logger.info(
                    "Loaded %s from %s on %s (VRAM free %.2f/%.2f GB)",
                    name,
                    path,
                    gpu_name,
                    free / (1024**3),
                    total / (1024**3),
                )
            except Exception:
                logger.info("Loaded %s from %s on CUDA device", name, path)
        else:
            logger.info("Loaded %s from %s on %s", name, path, dev)
    return model


def unload_all() -> None:
    """Clear cached models and free GPU memory."""
    _CACHE.clear()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


__all__ = ["get", "unload_all"]
