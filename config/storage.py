"""Helpers for loading and saving configuration."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import redis

from .constants import (
    AVAILABLE_CLASSES,
    BRANDING_DEFAULTS,
    CONFIG_DEFAULTS,
    COUNT_GROUPS,
    PPE_ITEMS,
    PPE_PAIRS,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows doesn't provide fcntl
    fcntl = None

SAVE_CONFIG_LOCK = threading.Lock()


def _sanitize_track_ppe(items: list[str]) -> list[str]:
    """Normalize user-selected PPE classes."""

    cleaned: list[str] = []
    for raw in items:
        base = raw.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        while base.startswith("no_"):
            base = base[3:]
        if base in PPE_ITEMS and base not in cleaned:
            cleaned.append(base)
    return cleaned


# Internal helpers ---------------------------------------------------------


def _read_config_file(path: str) -> dict:
    """Read a JSON configuration file from ``path``."""

    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path) as f:
        return json.load(f)


def _apply_defaults(data: dict) -> dict:
    """Populate missing configuration keys and normalize fields."""
    if "use_gstreamer" not in data and "enable_gstreamer" in data:
        data["use_gstreamer"] = bool(data.pop("enable_gstreamer"))

    for key, value in CONFIG_DEFAULTS.items():
        if isinstance(value, (dict, list)):
            data.setdefault(key, copy.deepcopy(value))
        else:
            data.setdefault(key, value)
    raw_ppe = data.get("track_ppe", [])
    data["track_ppe"] = _sanitize_track_ppe(raw_ppe)
    data.setdefault("stream_mode", "ffmpeg")
    backend_priority = data.get("backend_priority")
    if backend_priority is None:
        if data.get("stream_mode") == "gstreamer" and data.get("use_gstreamer", False):
            backend_priority = ["gstreamer", "ffmpeg", "opencv"]
        else:
            backend_priority = ["ffmpeg", "gstreamer", "opencv"]
    else:
        if isinstance(backend_priority, str):
            backend_priority = [backend_priority]
        backend_priority = ["ffmpeg", *[b for b in backend_priority if b != "ffmpeg"]]
    data["backend_priority"] = backend_priority
    return data


def _rewrite_pipelines(data: dict) -> None:
    """Upgrade legacy pipeline configuration in-place."""

    profiles = data["pipeline_profiles"]
    for _, cfg in profiles.items():
        if "pipelines" not in cfg:
            extra = cfg.pop("extra_pipeline", None)
            flags = cfg.pop("ffmpeg_flags", None)
            base_gst = (
                'rtspsrc location="{url}" protocols=tcp latency=100 ! '
                "rtph264depay ! h264parse ! avdec_h264 ! videoconvert"
            )
            if extra:
                base_gst += f" ! {extra}"
            base_gst += (
                " ! video/x-raw,format=BGR ! queue max-size-buffers=1 "
                "leaky=downstream ! appsink name=appsink drop=true "
                "sync=false max-buffers=1"
            )
            base_ffmpeg = "ffmpeg -rtsp_transport tcp -i {url} -an"
            if flags:
                base_ffmpeg += f" {flags}"
            base_ffmpeg += " -f rawvideo -pix_fmt bgr24 -"
            cfg["pipelines"] = {
                "gstreamer": base_gst,
                "ffmpeg": base_ffmpeg,
                "opencv": "{url}",
            }
        pipes = cfg.setdefault("pipelines", {})
        pipes.setdefault("gstreamer", "")
        pipes.setdefault("ffmpeg", "")
        pipes.setdefault("opencv", "{url}")


def _load_branding_file(path: str) -> dict:
    """Load branding information from ``path``."""

    return load_branding(path)


def _persist_to_redis(data: dict, redis_client: redis.Redis | None) -> None:
    """Store ``data`` in ``redis_client`` if provided."""

    if redis_client is not None:
        redis_client.set("config", json.dumps(data))


# Public helpers -----------------------------------------------------------


def sync_detection_classes(cfg: dict) -> None:
    groups = list(cfg.get("track_objects", []))
    if "person" not in groups:
        groups.insert(0, "person")
    cfg["track_objects"] = groups
    object_classes: list[str] = []
    count_classes: list[str] = []
    for group in groups:
        count_classes.extend(COUNT_GROUPS.get(group, [group]))
    object_classes.extend(count_classes)

    base_items = _sanitize_track_ppe(cfg.get("track_ppe", []))
    detection_items: list[str] = []
    for item in base_items:
        if item not in AVAILABLE_CLASSES:
            continue
        detection_items.append(item)
        pair = PPE_PAIRS.get(item)
        if pair and pair in AVAILABLE_CLASSES:
            detection_items.append(pair)

    cfg["track_ppe"] = base_items
    cfg["ppe_classes"] = detection_items
    cfg["object_classes"] = object_classes + detection_items
    cfg["count_classes"] = count_classes


def load_config(
    path: str,
    r: redis.Redis | None,
    *,
    data: dict | None = None,
    minimal: bool = False,
) -> dict:
    """Load configuration from ``path``."""

    if data is None:
        data = _read_config_file(path)

    if minimal:
        redis_url = data.get("redis_url")
        if not redis_url:
            raise KeyError("redis_url is required")
        return {"redis_url": redis_url, "data": data}
    if not data.get("redis_url"):
        raise KeyError("redis_url is required")
    data = _apply_defaults(data)
    _rewrite_pipelines(data)
    branding_path = str(Path(path).with_name("branding.json"))
    data.setdefault("branding", _load_branding_file(branding_path))
    sync_detection_classes(data)
    _persist_to_redis(data, r)
    return data


def save_config(cfg: dict, path: str, r: redis.Redis) -> None:
    """Persist configuration to disk and update Redis atomically."""

    raw_ppe = cfg.get("track_ppe", [])
    cfg["track_ppe"] = _sanitize_track_ppe(raw_ppe)
    sync_detection_classes(cfg)

    frame_skip = cfg.get("frame_skip", 3)
    if not isinstance(frame_skip, int) or frame_skip < 0:
        raise ValueError("frame_skip must be a non-negative integer")
    cfg["frame_skip"] = frame_skip
    detector_fps = cfg.get("detector_fps", 10)
    if not isinstance(detector_fps, (int, float)) or detector_fps < 0:
        raise ValueError("detector_fps must be non-negative")
    cfg["detector_fps"] = detector_fps
    cfg["adaptive_skip"] = bool(cfg.get("adaptive_skip", False))
    cfg.setdefault("ffmpeg_flags", "-flags low_delay -fflags nobuffer")

    device = cfg.get("device")
    if device is not None and not isinstance(device, str):
        cfg["device"] = str(device)

    def _ser(o: Any):
        import datetime as _dt
        import enum
        import uuid
        from pathlib import Path

        try:
            import torch  # type: ignore
        except ImportError:  # pragma: no cover - torch is optional
            torch = None

        if isinstance(o, Path):
            return str(o)
        if torch is not None and isinstance(o, torch.device):
            return str(o)
        if isinstance(o, (enum.Enum, uuid.UUID, _dt.datetime, _dt.date)):
            return str(o)
        raise TypeError(str(o))

    with SAVE_CONFIG_LOCK:
        with open(path, "a+") as f:
            if fcntl is not None:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                json.dump(cfg, f, indent=2, default=_ser)
                f.flush()
                os.fsync(f.fileno())
            finally:
                if fcntl is not None:
                    fcntl.flock(f, fcntl.LOCK_UN)
        r.set("config", json.dumps(cfg, default=_ser))


def load_branding(path: str) -> dict:
    """Load branding configuration from a JSON file."""
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {}
    for k, v in BRANDING_DEFAULTS.items():
        data.setdefault(k, v)
    return data


def save_branding(data: dict, path: str) -> None:
    """Save branding configuration."""
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name or ".")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass


__all__ = [
    "load_config",
    "save_config",
    "load_branding",
    "save_branding",
    "sync_detection_classes",
]
