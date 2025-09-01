"""String constants for Redis keys used across the application."""

CFG_VERSION = "vms21:cfg:version"
CAM_STATE = "vms21:cam:{id}:state"
EVENTS_STREAM = "vms21:events"

__all__ = [
    "CFG_VERSION",
    "CAM_STATE",
    "EVENTS_STREAM",
]
