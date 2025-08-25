"""Centralized event name constants.

This module defines all Redis event identifiers used across the
application. Using constants avoids typos when publishing or
subscribing to events.
"""

# PPE related events
PPE_VIOLATION = "ppe_violation"

# Authentication events
FAILED_LOGIN = "failed_login"

# Face recognition events
FACE_UNRECOGNIZED = "face_unrecognized"
FACE_BLURRY = "face_blurry"

# Gate pass events
GATEPASS_CREATED = "gatepass_created"
GATEPASS_APPROVED = "gatepass_approved"
GATEPASS_REJECTED = "gatepass_rejected"
GATEPASS_OVERDUE = "gatepass_overdue"

# Visitor management events
VISITOR_REGISTERED = "visitor_registered"

# Camera/streaming events
CAMERA_OFFLINE = "camera_offline"
CAPTURE_START = "capture_start"
CAPTURE_STOP = "capture_stop"
CAPTURE_ERROR = "capture_error"
CAPTURE_READ_FAIL = "capture_read_fail"

# System monitoring events
NETWORK_USAGE_HIGH = "network_usage_high"
NETWORK_USAGE_LOW = "network_usage_low"
DISK_SPACE_LOW = "disk_space_low"
SYSTEM_CPU_HIGH = "system_cpu_high"

# Configuration events
CONFIG_UPDATED = "config_updated"

# Counting events
PERSON_ENTRY = "person_entry"
PERSON_EXIT = "person_exit"
VEHICLE_ENTRY = "vehicle_entry"
VEHICLE_EXIT = "vehicle_exit"
VEHICLE_DETECTED = "vehicle_detected"
FACE_IN = "face_in"
FACE_OUT = "face_out"

# All events set for easy validation
ALL_EVENTS = {
    PPE_VIOLATION,
    FAILED_LOGIN,
    FACE_UNRECOGNIZED,
    FACE_BLURRY,
    PERSON_ENTRY,
    PERSON_EXIT,
    VEHICLE_ENTRY,
    VEHICLE_EXIT,
    VEHICLE_DETECTED,
    FACE_IN,
    FACE_OUT,
    GATEPASS_CREATED,
    GATEPASS_APPROVED,
    GATEPASS_REJECTED,
    GATEPASS_OVERDUE,
    VISITOR_REGISTERED,
    CAMERA_OFFLINE,
    CAPTURE_START,
    CAPTURE_STOP,
    CAPTURE_ERROR,
    CAPTURE_READ_FAIL,
    NETWORK_USAGE_HIGH,
    NETWORK_USAGE_LOW,
    DISK_SPACE_LOW,
    SYSTEM_CPU_HIGH,
    CONFIG_UPDATED,
}

__all__ = [
    "PPE_VIOLATION",
    "FAILED_LOGIN",
    "FACE_UNRECOGNIZED",
    "FACE_BLURRY",
    "PERSON_ENTRY",
    "PERSON_EXIT",
    "VEHICLE_ENTRY",
    "VEHICLE_EXIT",
    "VEHICLE_DETECTED",
    "FACE_IN",
    "FACE_OUT",
    "GATEPASS_CREATED",
    "GATEPASS_APPROVED",
    "GATEPASS_REJECTED",
    "GATEPASS_OVERDUE",
    "VISITOR_REGISTERED",
    "CAMERA_OFFLINE",
    "CAPTURE_START",
    "CAPTURE_STOP",
    "CAPTURE_ERROR",
    "CAPTURE_READ_FAIL",
    "NETWORK_USAGE_HIGH",
    "NETWORK_USAGE_LOW",
    "DISK_SPACE_LOW",
    "SYSTEM_CPU_HIGH",
    "CONFIG_UPDATED",
    "ALL_EVENTS",
]
