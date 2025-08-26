# Changelog
- bundle DejaVuSans font and cache overlay font to avoid per-frame load
- name capture/process/watchdog threads and add diagnostic thread dump endpoint
- add StoppableThread with signal-based shutdown and stalled camera watchdog

- throttle per-frame logs and standardize log prefixes; ensure single exception traces
- remove unused health endpoints and standardize response shapes

- use Redis pipeline for per-frame state updates and apply TTL
- replace blocking KEYS with SCAN when cleaning camera keys
- add redis_guard helpers to enforce TTL and wrap pipelines
- avoid double counting by tracking per-line entry/exit state and expiring stale tracks
- remove unused RTSP and MJPEG helper scripts

- add TurboJPEG-backed `encode_jpeg` helper with env-configurable quality
- drop legacy `vision.overlay` renderer in favour of `app.vision.overlay`

- handle missing Loguru handlers gracefully to prevent startup crash
- replace local gate pass placeholder image with hosted URL
- centralize Redis key names in `app/core/redis_keys.py`
- add optional Pydantic-based configuration loader with singleton accessor
- provide compatibility wrapper for `vision.counting`

- support experimental counting-only pipeline toggled via `VMS21_COUNTING_PURE`
- optionally stream MJPEG overlays via in-process Pipeline when `VMS21_PIPELINE=1`
- add DeepSort-based Tracker wrapper in app/vision with env-configurable params
- add initial SQL migration for events and summaries tables
- add runtime aggregator for Redis stream summaries
- add async diagnostics tests for connectivity and performance metrics
- cache basic and PPE detectors in shared registry for diagnostics
- add overlay diagnostics checks endpoint and front-end runner
- add model adapters for basic and PPE YOLO models to allow diagnostics model switching
- ensure diagnostic overlays draw boxes with source-frame coordinates
- add helpers `abs_line_from_ratio` and `draw_boxes_pil` with bounds clamping
- make dashboard latest_images robust to sync/async Redis clients using EAFP
- track FFmpeg restarts and expose `restarts` count via `/debug`
- validate and normalize camera resolution strings via regex parsing
- add `-fflags nobuffer` placeholder to FFmpeg flag inputs in camera settings and debug pages
- add ffmpeg rawvideo reader test
- send empty PPE list when no detections and update overlay client

- restructure FFmpeg RTSP command to add banner/loglevel flags and ensure input
  options precede ``-i``

- probe RTSP resolution via ffprobe and read fixed-size frames in FFmpeg capture
- switch counting toggle to `PATCH /api/cameras/{id}` and drop legacy
  `counting_enabled` setting
- handle BGRA frames in FFmpeg capture and log conversions
- update counting settings to refresh camera tasks and deprecate
  ``counting_enabled`` flag
- ensure troubleshooter API reports final read step and update tests
- add FrameBus ring buffer for camera frames
- fallback to FFmpeg when GStreamer support is unavailable
- add missing `init_context` stub to troubleshooter router to allow server startup
- disable audio in FFmpeg pipelines and add low-latency flags for faster RTSP handling
- cache ffprobe fallback resolutions briefly and allow configurable probe timeout
- handle count_events failures gracefully and return HTTP 503 when stats are unavailable
- reuse In/Out virtual line for face recognition; add migration for legacy `inout_line`
- Fix overlays: WebSocket DI + PPE threshold; add robust WS & canvas sizing
- remove automatic local camera discovery
- fix /vms 500 error; add regression tests
- wait for camera metadata before enabling capture buttons
- improve captured image quality and error handling in face search (70% JPEG)
- auto-detect stream type from URLs in tracker and camera factory
- enable FFmpeg HTTP reconnection flags with configurable delay
- document camera API fields and provide curl example
- remove legacy `/manage_faces/*` endpoints; use `GET /api/faces` for listings
- expose Redis facade via app state and router contexts

- prevent duplicate timers and listeners in live view scripts; add scheduler and debounce search inputs
