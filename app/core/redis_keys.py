"""Redis key constants for VMS module."""

VIS_ID_SEQ = "vms26:ids:visitor"
GP_ID_SEQ = "vms26:ids:gpass"

VIS_HASH = "vms26:vis:{id}"
VIS_ALL = "vms26:index:vis:all"

GP_HASH = "vms26:gpass:{id}"
GP_ALL = "vms26:index:gpass:all"
GP_BYDATE = "vms26:index:gpass:bydate:{date}"
GP_LOCK = "vms26:lock:gpass:{visitor_id}:{date}"

CFG_UI_VMS = "vms26:cfg:ui:vms"
CFG_VERSION = "vms26:cfg:version"

"""String constants for Redis keys used across the application."""

CFG_VERSION = "vms21:cfg:version"
CAM_STATE = "vms21:cam:{id}:state"
OVERLAY_LAST = "vms21:overlay:{id}"
EVENTS_STREAM = "vms21:events"

__all__ = [
    "CFG_VERSION",
    "CAM_STATE",
    "OVERLAY_LAST",
    "EVENTS_STREAM",
]
