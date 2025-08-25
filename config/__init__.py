"""Unified configuration package."""

from .constants import *  # noqa: F401,F403
from .storage import (
    _sanitize_track_ppe,
    load_branding,
    load_config,
    save_branding,
    save_config,
    sync_detection_classes,
)
from .versioning import bump_version, watch_config

config = DEFAULT_CONFIG.copy()
use_gstreamer: bool = config["use_gstreamer"]


def set_config(cfg: dict) -> None:
    """Replace the global configuration with ``cfg`` and sync thresholds."""

    config.clear()
    config.update(DEFAULT_CONFIG)
    config.update(cfg)

    FACE_THRESHOLDS.recognition_match = config.get(
        "face_match_thresh", FACE_THRESHOLDS.recognition_match
    )
    FACE_THRESHOLDS.db_duplicate = config.get(
        "face_db_dup_thresh", FACE_THRESHOLDS.db_duplicate
    )
    FACE_THRESHOLDS.duplicate_suppression = config.get(
        "face_duplicate_thresh", FACE_THRESHOLDS.duplicate_suppression
    )
    FACE_THRESHOLDS.blur_detection = config.get(
        "blur_detection_thresh", FACE_THRESHOLDS.blur_detection
    )
    FACE_THRESHOLDS.face_count_conf = config.get(
        "face_count_conf", FACE_THRESHOLDS.face_count_conf
    )
    FACE_THRESHOLDS.face_count_similarity = config.get(
        "face_count_similarity", FACE_THRESHOLDS.face_count_similarity
    )
    FACE_THRESHOLDS.face_count_min_size = config.get(
        "face_count_min_size", FACE_THRESHOLDS.face_count_min_size
    )
    global use_gstreamer
    use_gstreamer = config.get("use_gstreamer", False)


__all__ = [
    "load_config",
    "save_config",
    "load_branding",
    "save_branding",
    "sync_detection_classes",
    "_sanitize_track_ppe",
    "set_config",
    "config",
    "use_gstreamer",
    "watch_config",
    "bump_version",
] + [name for name in globals().keys() if name.isupper()]
