# Streaming Modes

The camera stack now supports two FFmpeg streaming modes:

- **Raw decoding (default)** – FFmpeg decodes the incoming H.264 stream into
  BGR frames that are pushed through the pipeline.
- **Pass-through** – set `use_raw=True` on `FFmpegCameraStream` or pass
  `stream_mode="lite"` to `camera_factory.open_capture` to keep the
  compressed H.264 bitstream intact. Frames remain compressed in the internal
  buffer and are decoded only when `decode_latest()` is invoked.

All default FFmpeg commands use `-rtsp_transport tcp -an` to prefer TCP
transport and drop audio for lower latency.

Example:

```python
from modules.camera_factory import open_capture

# regular decoded frames
cap, _ = open_capture(url, cam_id)

# pass-through for a lightweight live view
cap, _ = open_capture(url, cam_id, stream_mode="lite")
```

## Reconnection

Capture sources now retry automatically using an exponential backoff starting
at 0.5s and capped by the `VMS26_RECONNECT_MAXSLEEP` environment variable
(default 8s). To force TCP transport for all RTSP streams, set
`VMS26_RTSP_TCP=1`.
