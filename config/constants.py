"""Configuration constants for the application."""

import os
from dataclasses import dataclass

from app.core.utils import parse_bool


@dataclass
class FaceThresholds:
    """Centralized face processing thresholds."""

    recognition_match: float = 0.6
    db_duplicate: float = 0.95
    duplicate_suppression: float = 0.5
    blur_detection: float = 100.0


FACE_THRESHOLDS = FaceThresholds()

DEFAULT_MODULES = ["dashboard", "visitors", "reports", "settings"]

# Optional development flag to disable stream authentication
ALLOW_UNAUTHENTICATED_STREAM = parse_bool(os.getenv("ALLOW_UNAUTHENTICATED_STREAM"))

DEFAULT_CONFIG = {
    "enable_person_tracking": True,
    "default_host": "",
    "camera_id": "",
    "license_info": {"features": {"visitor_mgmt": True}},
    "features": {"visitor_mgmt": True},
    "blur_detection_thresh": FACE_THRESHOLDS.blur_detection,
    "local_buffer_size": 1,
    "model_version": 1,
    "preview_scale": 1.0,
    "detector_fps": 10,
    "adaptive_skip": False,
    "modules": DEFAULT_MODULES.copy(),
    # media backend selection
    "use_gstreamer": False,
    "storage_backend": "redis",
    "allow_unauthenticated_stream": ALLOW_UNAUTHENTICATED_STREAM,
    "stream_probe_timeout": 10,
    "stream_probe_fallback_ttl": 120,
    "camera": {"mode": "rtsp", "uri": "", "latency_ms": 100, "tcp": True},
}

MODEL_CLASSES = [
    "no_dust_mask",
    "no_face_shield",
    "no_helmet",
    "no_protective_gloves",
    "no_safety_glasses",
    "no_safety_shoes",
    "no_vest_jacket",
    "helmet",
    "person",
    "person_smoking",
    "person_using_phone",
    "protective_gloves",
    "safety_glasses",
    "safety_shoes",
    "smoke",
    "sparks",
    "vest_jacket",
    "worker",
]

PPE_ITEMS = [
    "helmet",
    "vest_jacket",
    "safety_shoes",
    "protective_gloves",
    "face_shield",
    "dust_mask",
    "safety_glasses",
]

PPE_PAIRS = {
    "helmet": "no_helmet",
    "vest_jacket": "no_vest_jacket",
    "safety_shoes": "no_safety_shoes",
    "protective_gloves": "no_protective_gloves",
    "face_shield": "no_face_shield",
    "dust_mask": "no_dust_mask",
    "safety_glasses": "no_safety_glasses",
}
PPE_TASKS = list(PPE_PAIRS.keys()) + list(PPE_PAIRS.values())

ANOMALY_ITEMS = [
    "no_helmet",
    "no_safety_shoes",
    "no_safety_glasses",
    "no_protective_gloves",
    "no_dust_mask",
    "no_face_shield",
    "no_vest_jacket",
    "smoke",
    "sparks",
    "yellow_alert",
    "red_alert",
]

OTHER_CLASSES = [
    "person",
    "person_smoking",
    "person_using_phone",
    "smoke",
    "sparks",
    "worker",
    "fire",
]

COUNT_GROUPS = {
    "person": ["person"],
    "vehicle": ["car", "truck", "bus", "motorcycle", "bicycle", "auto", "van"],
    "other": OTHER_CLASSES,
}
VEHICLE_LABELS = {
    "car",
    "truck",
    "bus",
    "motorbike",
    "motorcycle",
    "bicycle",
    "auto",
    "van",
}
AVAILABLE_CLASSES = MODEL_CLASSES + ANOMALY_ITEMS + [c for cl in COUNT_GROUPS.values() for c in cl]
CAMERA_TASKS = [
    "in_count",
    "out_count",
    "inout_count",
    "full_monitor",
    "visitor_mgmt",
] + MODEL_CLASSES
UI_CAMERA_TASKS = ["in_out_counting", "visitor_mgmt"] + PPE_TASKS

CONFIG_DEFAULTS = {
    "track_ppe": [],
    "alert_anomalies": [],
    "track_objects": ["person", "vehicle"],
    "ppe_conf_thresh": 0.5,
    "detect_helmet_color": False,
    "show_lines": True,
    "show_ids": True,
    "show_counts": False,
    "preview_anomalies": [],
    "email_enabled": True,
    "show_track_lines": False,
    "preview_scale": 1.0,
    "enable_live_charts": True,
    "chart_update_freq": 5,
    "capture_buffer_seconds": 15,
    "frame_skip": 3,
    "detector_fps": 10,
    "adaptive_skip": False,
    "stream_probe_timeout": 10,
    "stream_probe_fallback_ttl": 120,
    "ffmpeg_flags": "-an -flags low_delay -fflags nobuffer",
    "enable_profiling": False,
    "enable_person_tracking": True,
    "profiling_interval": 5,
    "ppe_log_limit": 1000,
    "alert_key_retention_secs": 7 * 24 * 60 * 60,
    "ppe_log_retention_secs": 7 * 24 * 60 * 60,
    "pipeline_profiles": {},
    "cpu_limit_percent": 50,
    "max_retry": 5,
    "capture_buffer": 3,
    "local_buffer_size": 1,
    "camera": {"mode": "rtsp", "uri": "", "latency_ms": 100, "tcp": True},
    "person_model": "yolov8s.pt",
    "ppe_model": "mymodalv7.pt",
    "license_key": "TRIAL-123456",
    "max_cameras": 3,
    "modules": DEFAULT_MODULES.copy(),
    "features": {
        "in_out_counting": True,
        "ppe_detection": True,
        "visitor_mgmt": False,
    },
    "debug_logs": False,
    "count_cooldown": 2.0,
    "cross_hysteresis": 15,
    "cross_min_travel_px": 10,
    "cross_min_frames": 2,
    "track_max_age": 10,
    "device": "auto",
    "cpu_sample_every": 3,
    "logo_url": "https://www.coromandel.biz/wp-content/uploads/2025/04/cropped-CIL-Logo_WB-02-1-300x100.png",
    "logo2_url": "https://www.coromandel.biz/wp-content/uploads/2025/02/murugappa-logo.png",
    "users": [
        {"username": "admin", "password": "rapidadmin", "role": "admin"},
        {"username": "viewer", "password": "viewer", "role": "viewer"},
    ],
    "settings_password": "000",
    # media backend selection
    "use_gstreamer": False,
}

BRANDING_DEFAULTS = {
    "company_name": "My Company",
    "site_name": "Main Site",
    "website": "",
    "address": "",
    "phone": "",
    "tagline": "",
    "print_layout": "A5",
    "company_logo": "",
    "company_logo_url": "",
    "footer_logo": "",
    "footer_logo_url": "",
}

__all__ = [
    "FACE_THRESHOLDS",
    "DEFAULT_CONFIG",
    "DEFAULT_MODULES",
    "MODEL_CLASSES",
    "PPE_ITEMS",
    "PPE_PAIRS",
    "PPE_TASKS",
    "ANOMALY_ITEMS",
    "OTHER_CLASSES",
    "COUNT_GROUPS",
    "AVAILABLE_CLASSES",
    "CAMERA_TASKS",
    "UI_CAMERA_TASKS",
    "VEHICLE_LABELS",
    "CONFIG_DEFAULTS",
    "BRANDING_DEFAULTS",
]
