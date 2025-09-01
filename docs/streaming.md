# Streaming Modes

The camera stack now supports two FFmpeg streaming modes:

- **Raw decoding (default)** – FFmpeg decodes the incoming H.264 stream into
  BGR frames that are pushed through the pipeline.
- **Pass-through** – set `use_raw=True` on `FFmpegCameraStream` to keep the
  compressed H.264 bitstream intact. Frames remain compressed in the internal
  buffer and are decoded only when `decode_latest()` is invoked.

All default FFmpeg commands use `-rtsp_transport tcp -an` to prefer TCP
transport and drop audio for lower latency.

Example:

```python
from modules.camera_factory import open_capture

# regular decoded frames
cap, _ = open_capture(url, cam_id)
```

## Reconnection

Capture sources now retry automatically using an exponential backoff starting
at 0.5s (configurable via `RECONNECT_BACKOFF_MS_MIN`) and capped by
`RECONNECT_BACKOFF_MS_MAX` (both in milliseconds). All RTSP commands default to
TCP transport; set `RTSP_TCP=1` to enforce TCP if a source requests UDP.
