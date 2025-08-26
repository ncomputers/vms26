"""Redis key and stream name constants.

This module centralizes Redis key conventions so they can be reused across
components without risk of typos.
"""

EVENT_STREAM = "vms21:events"
"""Primary stream for application events."""

CAM_STATE_KEY = "cam:{camera_id}:state"
"""Format string for per-camera state hashes."""

__all__ = ["EVENT_STREAM", "CAM_STATE_KEY"]
