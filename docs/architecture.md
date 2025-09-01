# Architecture Overview

## System Goals and Components
The Crowd Management System provides real-time person counting, PPE detection, and visitor management. It is built around several major components:

- **Web Server** – FastAPI application that serves the dashboard and REST APIs.
- **Workers** – Background tasks such as `PersonTracker`, `PPEWorker`, and `VisitorWorker` that process camera streams and handle business logic.
- **Redis** – Central datastore and message broker used for events, metrics, and queues.
- **Models** – YOLO models for person and PPE detection loaded through the model registry.

## Data Flow
```
Camera Streams --> PersonTracker --> Redis --> Dashboard
```
1. Cameras stream frames via GStreamer or FFmpeg.
2. `PersonTracker` analyzes frames and writes events to Redis streams.
3. Background workers consume those streams for PPE checks and visitor handling.
4. The web dashboard subscribes to Redis to display live counts and alerts.

### Storage Backend

Event data is persisted in Redis. The `storage_backend` setting in
`config.json` selects the backend and currently supports only `redis`.
Historical crossing events are stored in the sorted sets
`person_logs` and `vehicle_logs` using the event timestamp as the
score. Older deployments that used `events.db` can delete the SQLite file after
migrating.

For deployments requiring relational persistence, an initial migration
(`migrations/0001_create_events_summaries.sql`) is provided to create `events`
and `summaries` tables along with their indexes.

### Capture Pipeline
FFmpeg is the default backend and executes:

```bash
ffmpeg -loglevel error -rtsp_transport tcp -fflags nobuffer -flags low_delay \
       -analyzeduration 0 -probesize 32 \
       -stimeout ${RTSP_STIMEOUT_USEC:-5000000} \
       -i {url} -f rawvideo -pix_fmt bgr24 -
```

`rtsp_transport` may be set to `udp`, `FFMPEG_EXTRA_FLAGS` prepends custom
options, and `ffmpeg_flags` appends them. The global `frame_skip` parameter
drops frames before analysis to reduce load. Capture runs on a background
thread reading into a preallocated buffer and placing complete frames into a
small deque whose length is controlled by ``QUEUE_MAX`` (default ``2``),
discarding the oldest frame when full. The processing stage paces work to
``TARGET_FPS`` to avoid backlog growth. Consecutive short reads
trigger FFmpeg restarts with exponential backoff. Unexpected EOFs or broken
pipes cause the reader to restart FFmpeg with an exponential backoff capped at
10 s, and the total restart count is exposed via the `/debug` endpoint.

## Deployment Diagram
```
+-----------+       HTTP       +------------+
| Dashboard | <--------------> | Web Server |
+-----------+                  +------------+
                                   |
                        Redis streams & queues
                                   |
                         +------------------+
                         |    Workers       |
                         | (PersonTracker,  |
                         |  PPE, Visitors)  |
                         +------------------+
```

### Environment Requirements
- Python 3.10+
- Redis server (a running instance is required; fakeredis is not bundled)
- `ffmpeg` command-line tools
- Installed Python dependencies from `requirements.txt` (including `ultralytics`)
- Optional PostgreSQL driver (`psycopg2` or `asyncpg`) and accessible database for integration tests
- Optional GPU with CUDA for accelerated inference

## Module Documentation
- [Web Server](web-server.md)
- [Workers](workers.md)
- [Redis](redis.md)
- [Models](models.md)

## Background Housekeeping

A watchdog thread performs periodic housekeeping every 60 s. It prunes
registered caches beyond 10 000 entries (keeping the newest items) and, when
``CUDA_EMPTY_EVERY=60`` and a CUDA device is present, calls
``torch.cuda.empty_cache()``. Each run logs a throttled ``[perf] housekeeping``
message including prune counts.

## Getting Started
1. Clone the repository and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Ensure a Redis instance is running and configured in `config.json`.
3. Start the application:
   ```bash
   uvicorn main:app
   ```
   For HTTPS, pass `--ssl-certfile` and `--ssl-keyfile` or run behind a reverse proxy.
4. Run the test suite to verify your environment:
    ```bash
    python3 -m pytest -q
    ```
   The PostgreSQL integration test in `tests/test_postgres.py` requires a working
   `postgres_dsn` fixture and either `psycopg2` or `asyncpg`; if unavailable, the test is skipped.
5. See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.
