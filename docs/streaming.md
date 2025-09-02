# Streaming Modes

The camera stack supports two FFmpeg streaming modes:

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

## Connect-only RTSP connector

A lightweight `RtspConnector` process establishes the RTSP session and emits
decoded frames. The connector focuses solely on keeping the FFmpeg process
running; it does not handle previews or additional processing.

Frames from each connector are published to a dedicated :class:`FrameBus`, a
small thread-safe ring buffer that exposes ``put`` and ``get_latest`` helpers.
Multiple consumers can subscribe to a bus without interfering with one another.

## MJPG preview publisher

The preview service subscribes to ``FrameBus`` instances through an
``PreviewPublisher``. Clients request previews via
``/api/cameras/{id}/mjpeg``. The publisher encodes frames to JPEG and yields
them as ``multipart/x-mixed-replace`` chunks.

Because preview consumption is decoupled from the connector, a camera can
stream and be analysed even when no preview clients are connected.

### Configuration example

```json
{
  "cameras": [
    {"id": 1, "url": "rtsp://cam/stream", "resolution": "1280x720"}
  ]
}
```

Connectors start automatically for all configured cameras. Preview is optional
and can be toggled independently:

```bash
curl -X POST /api/cameras/1/show   # start preview
curl -X POST /api/cameras/1/hide   # stop preview
```

## Reconnection

The legacy `-rw_timeout` flag and Python retry/backoff logic have been
removed. The connector relies on FFmpeg's internal reconnect handling and a
watchdog to detect stalled streams. All RTSP commands default to TCP transport;
set `RTSP_TCP=1` to enforce TCP if a source requests UDP.
