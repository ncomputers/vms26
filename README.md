# Crowd Management System v81

Version 81 separates the person counting and PPE detection logic into two
independent modules. The basic **PersonTracker** detects and tracks people and
vehicles, logging entry/exit events to `person_logs` and `vehicle_logs` while
pushing items needing PPE checks to
`ppe_queue`. A new **PPEDetector** reads from this queue and stores the results
in `ppe_logs`. Older
entries are pruned automatically based on the configurable
`ppe_log_retention_secs` window. Camera configuration now uses grouped tasks for
counting and PPE detection.

The tracker keeps a complete history of entry and exit events in the
`person_logs` sorted set so the reports API can reconstruct occupancy over
time. When PPE detection is enabled, each relevant `person_logs` entry is copied
to a dedicated PPE queue. The `PPEWorker` consumes that queue and writes results
to `ppe_logs`, ensuring that PPE processing never removes data needed for
standard person-count reports.

Duplicate frame removal and all other features from the previous release are
still available.

## Upgrade Notes

Existing deployments may have camera records without the `show` flag used to
toggle visibility on the dashboard. On startup, the application now adds
`"show": true` to any camera missing this field and saves the update back to
Redis. After upgrading, review the Cameras page to confirm that each camera is
visible as expected.

Camera metadata now resides entirely in Redis, so no database migrations are
required for upgrades or fresh installs.

Event history previously stored in `events.db` is now written to Redis.
After upgrading, you may safely delete the old SQLite file. Configure the
`storage_backend` field in `config.json` (currently only `redis` is supported).

## Features

- **Multiple camera sources**: Add HTTP or RTSP cameras via the settings page.
- **Person and vehicle counting and PPE checks**: YOLOv8 is used for person and vehicle detection and, when enabled, for verifying required PPE.

## Camera Input Simplified

Camera capture is configured through a single `camera` block in `config.json`:

```json
{
  "camera": {"mode": "rtsp", "uri": "rtsp://user:pass@host/stream"}
}
```

Examples:

- **RTSP via FFmpeg** (default)

  ```json
  {"camera": {"mode": "rtsp", "uri": "rtsp://..."}, "use_gstreamer": false}
  ```

- **RTSP via GStreamer**

  ```json
  {"camera": {"mode": "rtsp", "uri": "rtsp://..."}, "use_gstreamer": true}
  ```

- **Local webcam**

  ```json
  {"camera": {"mode": "local", "uri": 0}}
  ```

- **HTTP MJPEG**

  ```json
  {"camera": {"mode": "http", "uri": "http://cam/mjpg"}}
  ```

Toggle `use_gstreamer` to switch RTSP backends. Only one pipeline is active at a
time; set it to `true` for GStreamer or `false` to use FFmpeg. Hardware decode
options are available via the GStreamer backend. Set `overlay_mode` to `"none"`
to stream raw frames without server-side overlays.

- **Counting and alerts**: Tracks entries/exits and can send email alerts based on customizable rules.
- **Duplicate frame filter**: Skips nearly identical frames to reduce GPU/CPU load.
- **Dashboard and reports**: Live counts, recent anomalies, and historical reports are available in the web interface.
- **Dashboard polling**: The dashboard refreshes counts by polling `/api/stats` every 2 seconds.
- **Dashboard history API**: Aggregated metrics are available via `/api/dashboard/stats?range=7d` where `range` may be `today`, `7d`, or `this_month`.
- **Debug stats**: Visit `/debug` to monitor raw SSE data, connection status, and camera backend info. For YOLO detection logs, open `/debug/yolo`.
- **Live feed optimization**: Dashboard streams the raw camera feed via `/stream/{cam_id}?raw=1` while analysis runs separately.
- **Per-camera resolution**: Choose 480p, 720p, 1080p, or original when adding a camera.
- **Camera status**: Online/offline indicators appear in the Cameras page for quick troubleshooting.
- **Secure logins**: User passwords are stored as PBKDF2 hashes and verified using passlib.
- **Rotating log file**: `app.log` captures runtime logs with automatic rotation.
- **Historical reports**: A background task records per-minute counts to Redis so
  the reports page can graph occupancy over time. Log entries are stored in Redis
  sorted sets for efficient range queries.
- **Redis stream debug**: Stats are also written to `stats_stream` for reliable debugging.- **GStreamer streaming**: RTSP cameras use `avdec_h264` for software decoding and a leaky queue to drop stale frames for low latency.

## Quick Start

Minimal configuration examples for RTSP cameras:

```json
{"camera": {"mode": "rtsp", "uri": "rtsp://user:pass@host/stream"}, "use_gstreamer": false}
```

Set `use_gstreamer` to `true` to run the GStreamer pipeline instead of FFmpeg.
Only one pipeline runs at a time; restart after changing this flag.

## Camera Configuration Recommendations

- Use an H.264 substream.
- Limit the frame rate to 10–15 fps.
- Prefer constant bit rate (CBR).

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| 401/403 errors | Authentication failure | Verify credentials in the URL. |
| Unsupported codec or blank feed | Codec mismatch | Configure the camera for H.264. |
| Connection refused or 404 | Invalid URL | Check host, port, and stream path. |
| Frozen video or frequent reconnects | Transport issues or timeouts | Confirm `transport` setting and adjust RTSP timeouts. |

## Camera API


Each camera starts a connect-only RTSP connector that feeds decoded frames into
an internal **FrameBus**. The MJPG preview endpoint subscribes to this bus so
connectors continue running even when no preview clients are connected.

Environment knobs influencing the preview stream:

- `FRAME_JPEG_QUALITY` – JPEG quality for streamed frames (default `80`).
- `TARGET_FPS` – throttle outgoing MJPEG rate (default `15`).
- `NO_FRAME_TIMEOUT_MS` – trigger a capture restart if no frame is received
  within this window (default `2000`).
- `HEARTBEAT_INTERVAL_MS` – interval for keep-alive JPEGs during stalls
  (default `1500`).
- `RTSP_TCP=1` forces TCP transport for RTSP sources.

The FFmpeg `-rw_timeout` option and Python-based reconnect backoff have been
removed; the connector now relies on FFmpeg's internal retry logic.

Fields accepted by the camera creation endpoint:

- `name`
- `url`
- `orientation`
- `transport`
- `resolution`
- `ppe`
- `inout_count`
- `reverse`
- `show`
- `enabled`
- `line`
  (shared virtual line for In/Out counting). Update via
  `PATCH /api/cameras/{id}/line`; running trackers apply changes immediately,
  otherwise changes load on restart.
- `profile`
- `site_id`

Counting can be toggled via:

```bash
curl -X PATCH http://localhost:8000/api/cameras/{id} \
  -H "Content-Type: application/json" \
  -d '{"counting": true}'
```

The previous `PATCH /api/cameras/{id}/settings` endpoint and its
`counting_enabled` field are deprecated.

Example:

```bash
curl -X POST http://localhost:8000/cameras \
  -H "Content-Type: application/json" \
-d '{"name":"Gate","url":"rtsp://cam/stream","orientation":"normal","transport":"tcp","resolution":"original","enabled":true}'
```

## Installation

1. Install Python 3.10+, Redis, and the `ffmpeg` command-line tools. Redis must be running and reachable; the application exits on startup if it cannot connect.
2. Install dependencies (including `ultralytics`):
   ```bash
   pip install -r requirements.txt
   ```
   For systems with a display, install `opencv-python` to enable OpenCV's GUI
   features. Headless deployments should install `opencv-python-headless` and
   either set `"headless": true` in `config.json` or run without a `DISPLAY`
   environment variable. If OpenCV is not installed, the application still
   starts but features that rely on local camera capture remain unavailable.
   If you see an `ImportError: libGL.so.1` during startup, remove any existing
   `opencv-python` package and reinstall the headless variant:

   ```bash
   pip uninstall -y opencv-python
   pip install opencv-python-headless
   ```
3. Install [WeasyPrint](https://weasyprint.org/) and its native dependencies for
   PDF generation. On Debian/Ubuntu:
   ```bash
   sudo apt install libpangocairo-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0
   pip install weasyprint
   ```
   The project relies on WeasyPrint—tools like `wkhtmltopdf` are not supported.
   4. (Optional) Install GStreamer and its Python bindings if you plan to enable
   GStreamer streaming:
   ```bash
   sudo apt install python3-gi gstreamer1.0-plugins-base \
       gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
       gstreamer1.0-plugins-ugly gstreamer1.0-tools
   ```
5. (Optional) Install PHP if you want to use the sample PHP pages in `public/`.

## Configuration

Edit `config.json` to set camera URLs, model paths, thresholds, and email settings. Most options can also be adjusted in the web UI under **Settings**. Configuration changes are propagated to running pipelines within a few seconds. Key fields include:

- `stream_url` – Optional default stream used when launching via the command line.
- `person_model`, `ppe_model` – Paths to YOLO models.
- `device` – `auto`, `cpu`, or `cuda:0`. `auto` uses GPU if available,
  otherwise falls back to CPU with a warning.
- `headless` – Set to `true` to force offscreen mode when no display is
  available.
- `max_capacity` and `warn_threshold` – Occupancy limits.
- `redis_url` – Location of the Redis instance (required). The server must be reachable at startup or the application will terminate.
- `email` – SMTP configuration. Set `smtp_host`, `smtp_port`, `smtp_user`, `smtp_pass`, `use_tls`/`use_ssl`, and `from_addr` to enable email alerts.
- `default_host` – Optional host name used when no host is provided. When set,
- `stream_mode` – Maintained for backward compatibility; FFmpeg is tried first
  and GStreamer is used only if initialization fails.
- `stream_probe_timeout` – Seconds to wait for `ffprobe` when resolving stream
  dimensions. Defaults to **10** and can be overridden per camera.
- `stream_probe_fallback_ttl` – Seconds to cache the fallback resolution after
  a probe failure. Defaults to **120**.
  RTSP probes use TCP transport by default, matching the MJPEG preview
  pipeline.
- `use_gstreamer` – When `true`, attempt to use GStreamer bindings for camera
  pipelines. Defaults to `false` and automatically disables itself if
  `gst-launch-1.0` is missing or fails to run. When `false` the application
  skips `gi` imports and relies on FFmpeg/OpenCV.
- `backend_priority` – Ordered list of capture backends to try (default
  `["ffmpeg", "gstreamer", "opencv"]`). Disabled backends are skipped
  automatically. `opencv` is only attempted when a live dashboard view is
  requested (`for_display=True`); otherwise it is removed.
- `pipeline_profiles` – Named capture settings. See
  [camera factory examples](docs/modules/modules_camera_factory.md#full-pipeline-profiles)
  for GStreamer, FFmpeg and OpenCV profiles with equivalent command-line
  pipelines.
- `capture_buffer_seconds` – Length of encoded video to buffer before dropping (5–60).
- `frame_skip` – Number of frames to skip between processed frames (default 3).
- `detector_fps` – Maximum detector invocations per second (default 10).
- `adaptive_skip` – Enable motion-based frame skipping when `true`.
- `ffmpeg_flags` – Extra FFmpeg options appended to the capture command (default `"-flags low_delay -fflags nobuffer"`).
- `cpu_limit_percent` – Percent of CPU cores allocated to processing. The
  resolved core count sets process CPU affinity and caps threads in BLAS-backed
  libraries (default 50).
- `show_counts` – Display "Entered"/"Exited"/"Inside" labels on the live feed when enabled.
- `license_key` – JWT license token controlling maximum cameras and feature access.
- `ppe_log_retention_secs` – Seconds to retain PPE log entries before they are pruned (default 604800).
- `duplicate_bypass_seconds` – Cooldown window in seconds to skip repeated PPE statuses for the same track (default 2).
- `track_objects` – YOLO labels or alias names to track. Aliases such as `"vehicle"`
  expand to multiple classes (`car`, `truck`, `bus`, `motorcycle`, etc.).
  The `"person"` class is mandatory for in/out counting; removing it disables counts.
- `cross_min_travel_px` – Minimum distance in pixels a track must move on one side
  before a subsequent crossing is counted (default 10).
- `cross_min_frames` – Minimum consecutive frames a track must remain on a side
  before a subsequent crossing is counted (default 2).

### Environment Variables

- `FFPROBE_TIMEOUT_SEC` – Seconds to wait for RTSP metadata probes. Defaults to **30**.
- `RTSP_STIMEOUT_USEC` – Microseconds for RTSP connect timeout passed as ``-stimeout``. Defaults to **5000000**.

### Entry/exit logging with PPE detection

Enabling counting and PPE checks together requires both features in
`config.json` and camera tasks that include the desired PPE classes. The
`person_logs` history remains intact because the PPE worker consumes entries from
its own queue.

```json
{
  "features": {
    "in_out_counting": true,
    "ppe_detection": true
  },
  "track_ppe": ["helmet"],
  "cameras": [
    {
      "id": "gate1",
      "url": "rtsp://user:pass@cam/stream",
      "tasks": ["in_count", "out_count", "helmet", "no_helmet"]
    }
  ]
}
```

Entry/exit counters only increment when the detected group is `"person"`. PPE
detections configured via `track_ppe` are associated with their corresponding
person track and do not produce counts on their own.

### FFmpeg pipeline

The default camera backend invokes:

```bash
ffmpeg -rtsp_transport tcp -fflags nobuffer -flags low_delay \
       -analyzeduration 0 -probesize 32 \
       -stimeout ${RTSP_STIMEOUT_USEC:-5000000} \
       -i {url} -f rawvideo -pix_fmt bgr24 -
```

Key options:

- `frame_skip` – Drop frames between analyses to reduce load.
- `detector_fps` – Limit how often the detector runs.
- `adaptive_skip` – Increase/decrease `frame_skip` based on motion.
- `rtsp_transport` – `tcp` (default) or `udp` for the RTSP transport.
- `FFMPEG_EXTRA_FLAGS` – Prepended FFmpeg arguments from the environment.
- `ffmpeg_flags` – Extra arguments appended to the command.

Example `config.json`:

```json
{
  "frame_skip": 0,
  "pipeline_profiles": {
    "default": {
      "backend": "ffmpeg",
      "ffmpeg_flags": "-an -rtsp_transport tcp"
    }
  },
  "cameras": [
    { "id": "lobby", "url": "rtsp://user:pass@cam/stream" },
    {
      "id": "dock",
      "url": "rtsp://user:pass@cam2/stream",
      "ffmpeg_flags": "-rtsp_transport udp"
    }
  ]
}
```

The first camera uses the default pipeline, while the second overrides the transport.

#### Troubleshooting FFmpeg

- **Authentication errors (401/403)** – verify the username and password.
- **Network issues** – `No route to host` or timeouts suggest connectivity problems; check firewalls and cabling.
- **Short read** – messages like `Connection reset` or `short read` indicate the camera closed the connection; switch transports or lower `frame_skip`.

#### Troubleshooting Tracking

- **Incorrect counts** – when using models that operate on letterboxed frames,
  ensure bounding boxes are converted back to the original frame using the
  stored `pad_x`, `pad_y` and `scale` values. Skipped conversion leads to
  misaligned counting lines and wrong entry/exit totals.

### Logging

Logging is configured via [`logging_config.py`](logging_config.py) using Loguru with JSON output and rotation. Adjust verbosity by setting the `LOG_LEVEL` environment variable (e.g., `LOG_LEVEL=DEBUG`) or by adding a `log_level` entry in `config.json`.

Set `COUNTING_PURE=1` to enable the new counting-only pipeline which emits entry/exit events to an in-memory list. The variable is unset by default, preserving the legacy counting behaviour.

## Licensing

The application verifies the `license_key` on startup but will still run if the token is missing or invalid. Feature limits remain disabled until a valid key is activated. Use the **Settings** page (or `/license` endpoint) to update the key at runtime. The page shows license details such as client name, enabled features and expiration. Administrators can generate keys with `key_gen.py` or `license_generator.py`, enabling optional modules like PPE Detection and Visitor Management.

## Running

Launch the FastAPI application:

```bash
python3 main.py
```

Then open `http://localhost:5002` in your browser. Use the **Cameras** page to add streams (HTTP, RTSP or local webcams) and **Settings** to adjust options. Install development dependencies and run tests with `pytest`:

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q tests
```
When PyTorch with CUDA is installed, a GPU smoke test performs a basic CUDA tensor
operation to verify functionality.

> **Note:** Features that access the webcam via `getUserMedia` require HTTPS. Run the
> server with TLS by setting `SSL_CERTFILE` and `SSL_KEYFILE` or deploy behind an
> HTTPS‑enabled reverse proxy.

### Display modes

The server supports both GUI and headless deployments:

- **GUI mode** – Requires a display and the `opencv-python` package. Ensure
  `"headless": false` in `config.json`.
- **Headless mode** – Set `"headless": true` or run without a `DISPLAY`
  variable. The application sets `QT_QPA_PLATFORM=offscreen` and requires
  `opencv-python-headless`.
  In headless mode, the application skips the OpenCV backend unless a client
  opens the dashboard's live view and `for_display` is explicitly enabled.

### Choosing capture_buffer_seconds

The capture buffer holds encoded video data so that temporary inference delays
don't interrupt streaming. Set a higher value (up to 60&nbsp;s) for unstable
networks, or lower for minimal latency. Worst-case latency is roughly
`capture_buffer_seconds / FPS`.

## Directory Structure

- `main.py` – FastAPI entry point.
- `core/` – Helper modules such as configuration and tracker manager.
- `modules/` – Tracking, alerts, and utilities.
- `routers/` – API routes for dashboard, settings, reports, and cameras.
- `templates/` – HTML templates rendered by FastAPI.
- `public/` – Optional PHP pages.
- `tests/` – Simple unit tests.

## Development Tips

This repository uses a `.gitattributes` file that keeps incoming changes during merges.
If merge conflicts occur, Git will prefer the incoming version.

## Redis Key Naming

Redis keys follow a colon-separated scheme of `<module>:<entity>:<id>` to avoid collisions.

Examples:

- `person_tracker:cam:1:in` – entry count for camera `1`.

Use this pattern for any new Redis keys to keep the namespace consistent.

## File Reference

The repository contains the following files:

### Root files

- `main.py` – main FastAPI application.
- `config.py` – shared configuration dictionary.
- `config.json` – example configuration used at startup.
- `key_gen.py` – interactive license token generator.
- `license_generator.py` – command line generator for licenses.
- `license_plate_detector.pt` – pretrained model for license plates.
- `requirements.txt` – Python dependency list.
- `__init__.py` – marks the project package.
- `README.md` – this documentation file.

### Admin

- `Admin/license_generator.py` – interactive generator built with Authlib.

### core

- `core/__init__.py` – package marker for core modules.
- `config/storage.py` – load, save and normalize configuration.
- `core/stats.py` – aggregate statistics and publish to Redis.
- `core/tracker_manager.py` – start and manage `PersonTracker` instances.

### modules

- `modules/__init__.py` – package initialization.
- `modules/alerts.py` – background email alert worker.
- `modules/camera_factory.py` – helpers for opening camera streams.
- `modules/duplicate_filter.py` – drop nearly identical frames.
- `modules/gstreamer_stream.py` – GStreamer camera wrapper.
- `modules/license.py` – license token utilities.
- `modules/tracker/manager.py` – main tracking and counting logic.
- `modules/ppe_worker.py` – process person logs for PPE detection.
- `modules/profiler.py` – lightweight profiling utilities.
- `modules/utils.py` – misc helpers (password hashing, email, etc.).
- `modules/export.py` – helper functions for CSV, Excel and PDF exports.

### routers

- `routers/__init__.py` – package marker.
- `routers/alerts.py` – routes for alert rules and email tests.
- `routers/auth.py` – login and logout endpoints.
- `routers/cameras.py` – camera CRUD and preview routes.
- `routers/dashboard.py` – dashboard pages and streaming APIs.
- `routers/ppe_reports.py` – PPE report generation endpoints.
- `routers/reports.py` – person/vehicle report APIs.
 - `routers/settings.py` – update and export configuration.

### templates

- `templates/*.html` – Jinja2 templates for the web UI.
- `templates/partials/header.html` and `footer.html` – shared layout pieces.

### static

- `static/css/flatpickr.min.css` – bundled CSS for date pickers.
- `static/js/chart.min.js` – chart rendering library.
- `static/js/flatpickr.min.js` – date picker library.
- `static/logo1.png` and `static/logo2.png` – sample logos.

### public

- `public/dashboard.php` – PHP example dashboard.
- `public/report.php` – PHP report page.

### tests

- `tests/test_license.py` – verify license helpers.
- `tests/test_ppe_worker.py` – test PPE worker logic.
- `tests/test_reports.py` – test reporting endpoints.
- `tests/test_alerts.py` – test email alerts and metrics.
- `tests/TEST.PY` – simple FFmpeg stream example.

### Low-latency capture

The camera wrappers keep only the latest **N** frames in memory. A larger buffer
adds roughly `N / FPS` of latency but smooths out short processing spikes. Set
`capture_buffer` in `config.json` (default `3`). For 60&nbsp;fps sports feeds try
`5`, while low frame rate CCTV works well with `2`. Local USB cameras default to
`local_buffer_size=1` for minimal delay; increase it if you experience dropped
frames during processing spikes.

The factory verifies that a stream is delivering frames and will automatically
fall back from GStreamer to FFmpeg (or OpenCV) if needed.

Benchmark with:

```bash
gst-launch-1.0 rtspsrc location=... ! videorate drop-only=true ! fpsdisplaysink text-overlay=false
ffplay -flags low_delay -fflags nobuffer -i rtsp://...
python -m modules.latency_probe --url rtsp://... --buffer 3
```

## Package Documentation

Detailed documentation for internal modules and routers is available below.

### Modules

- [**init**](docs/modules/modules___init__.md)
- [alerts](docs/modules/modules_alerts.md)
- [base_camera](docs/modules/modules_base_camera.md)
- [camera_factory](docs/modules/modules_camera_factory.md)
- [camera_manager](docs/modules/modules_camera_manager.md)
- [capture_utils](docs/modules/modules_capture_utils.md)
- [duplicate_filter](docs/modules/modules_duplicate_filter.md)
- [email_utils](docs/modules/modules_email_utils.md)
- [export](docs/modules/modules_export.md)
- [feedback_db](docs/modules/modules_feedback_db.md)
- [getinfo](docs/modules/modules_getinfo.md)
- [gstreamer_stream](docs/modules/modules_gstreamer_stream.md)
- [license](docs/modules/modules_license.md)
- [model_registry](docs/modules/modules_model_registry.md)
- [ppe_worker](docs/modules/modules_ppe_worker.md)
- [profiler](docs/modules/modules_profiler.md)
- [renderer](docs/modules/modules_renderer.md)
- [report_export](docs/modules/modules_report_export.md)
- [stream_probe](docs/modules/modules_stream_probe.md)
- [tracker](docs/modules/modules_tracker.md)
- [utils](docs/modules/modules_utils.md)

### Routers

- [**init**](docs/modules/routers___init__.md)
- [alerts](docs/modules/routers_alerts.md)
- [auth](docs/modules/routers_auth.md)
- [blueprints](docs/modules/routers_blueprints.md)
- [cameras](docs/modules/routers_cameras.md)
- [dashboard](docs/modules/routers_dashboard.md)
- [ppe_reports](docs/modules/routers_ppe_reports.md)
- [reports](docs/modules/routers_reports.md)
- [settings](docs/modules/routers_settings.md)

## Progressive Web App

This project ships as a PWA and supports offline use, installation and push notifications.

### Build and Install

1. Run `npm run build-sw` after production builds to generate the service worker precache.
2. Serve the app over **HTTPS** so the service worker can register.

### Debugging

- Open DevTools → Application to inspect service workers, manifests and caches.
- To clear caches run `caches.keys().then(k=>k.forEach(caches.delete));` in the console.
- Notification permissions can be revoked via your browser's site settings.

### Offline and Updates

- The app precaches core assets and uses runtime caching for API calls and images.
- When a new service worker is available you'll be prompted to refresh; confirming reloads with the latest assets.
- `/offline.html` is shown when navigation requests fail while offline.

### Lighthouse

Run `npm run lhci` to audit PWA compliance. The configuration targets a PWA score of 95 or higher.

## Mobile App Configuration

The mobile build reads metadata from `config/mobile_app.json`. To create a white-label app for a new client, duplicate this file and adjust the following fields:

1. `appName` and `appId` identify the app in stores.
2. `serverUrl` and `manifestUrl` point to the deployment server and web manifest.
3. `icons.android` and `icons.ios` provide platform-specific icon URLs.
4. `version` tracks the release number.
5. `permissions` lists required runtime permissions.

After updating the JSON, run the usual Capacitor or Cordova build steps; the configuration is picked up automatically.
