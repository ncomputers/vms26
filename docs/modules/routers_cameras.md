# routers_cameras
[Back to Architecture Overview](../README.md)

## Purpose
Camera management routes. Utilizes the shared
`visitor_disabled_response` helper to standardize messaging when visitor
management features are disabled or unlicensed.
When an RTSP URL without a path is supplied, camera creation attempts
to auto-probe common stream paths and logs the selected URL.

### Environment Variables

- `PIPELINE` - When set to `1`, MJPEG frames are streamed from a
  lightweight in-process pipeline instead of spawning FFmpeg.

## Key Classes
None

## Key Functions
- **init_context(config, cameras, trackers, redis_client, templates_path)** -
- **_expand_ppe_tasks(tasks)** - Ensure each selected PPE class includes its paired absence/presence.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
- `rtsp://`

## Dependencies
- __future__
- config
- core.config
- core.tracker_manager
- cv2
- fastapi
- fastapi.responses
- fastapi.templating
- json
- modules.ffmpeg_stream
- modules.gstreamer_stream
- modules.utils
- typing
- utils
- routers.visitor_utils
