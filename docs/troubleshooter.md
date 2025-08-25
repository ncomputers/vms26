# Troubleshooter

The troubleshooter aggregates connectivity diagnostics for cameras and exposes
results through a JSON array of step objects.

From the dashboard press **Troubleshooter** to open the page. Each camera lists a
**Run diagnostics** button which performs:

- ICMP ping to the camera host.
- RTSP or MJPEG probe depending on the active source; the inactive probe is skipped.
- Recent-frame freshness check using Redis to ensure frames are arriving.
- Report the camera's current source mode.

The API at `/api/troubleshooter/{id}` returns an array where each item contains
`step`, `ok`, `detail` and optional `hints` fields. Results are rendered inline
for quick inspection. Skipped probes are marked with a grey **skip** badge in the UI.

## Programmatic interface

- `GET /api/troubleshooter/tests` lists available diagnostic test identifiers and
  returns capability flags such as support for Server‑Sent Events.
- `POST /api/troubleshooter/run` executes a selection of tests sequentially. The
  request body accepts `{"camera_id": 1, "tests": ["ping", "rtsp_probe"]}` and
  responds with a `run_id` and an array of individual results. Each test is
  awaited with a timeout of five seconds and execution continues even after
  failures.
- `GET /api/troubleshooter/run_sse` streams the same diagnostics using
  Server‑Sent Events. Each `test_result` event includes the `run_id` and the
  accumulating results array, followed by a final `run_complete` event. Capture
  and detection processes continue unaffected during diagnostics runs.
