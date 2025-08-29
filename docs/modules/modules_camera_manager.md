# modules_camera_manager
[Back to Architecture Overview](../README.md)

## Purpose
Service layer for starting, restarting and flagging camera tracking pipelines.
The implementation lives in ``core.camera_manager``.

## Key Classes
- **CameraManager** – coordinates tracker start/stop operations.

## Key Functions
- **start(camera_id)** – start trackers for the given camera.
- **restart(camera_id)** – restart trackers and update status in Redis.
-- **refresh_flags(camera_id)** – signal a tracker to reload debug flags.

## Configuration Notes
`CameraManager` receives callback functions for starting and stopping trackers.
Camera metadata is supplied via a `cams_getter` callable and Redis is optional.

Reconnect attempts use exponential backoff with jitter and a per-camera
"circuit breaker". After three consecutive failures the breaker opens for
15 seconds before allowing a half-open retry. Lightweight status updates are
published to `cam:<id>:status` for UI consumption.

## Inputs and Outputs
Refer to class methods for inputs and outputs.

## Redis Keys
- `camera:<id>` – stores camera status.
- `camera:<id>:health` – contains health status information.
- `cam:<id>:status` – current reconnect state and retry timing.

## Dependencies
- asyncio
- loguru
- typing
