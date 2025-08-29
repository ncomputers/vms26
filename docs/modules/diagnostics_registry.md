# diagnostics.registry

Utility module providing a registry of diagnostic tests.  Tests are
registered with the `register` decorator and retrieved via `list_tests`
which returns them in execution order.  Each test is asynchronous and
returns a mapping containing the fields `id`, `status`, `reason`,
`detail`, `suggestion` and `duration_ms`.

Additional helpers:

* `get_source_mode(cam_id)` – determine the configured source mode for a
  camera.
* `now_ms()` – convenience wrapper returning the current time in
  milliseconds.

The default suite covers connectivity and runtime health checks such as
`camera_found`, `ping`, `rtsp_probe`, `mjpeg_probe`, `snapshot_fresh`,
`stream_metrics`, `detector_warm`, `inference_latency`,
`queues_depth`, `redis_rtt`, `gpu_stats`, `report_consistency` and
`license_limits`.

`detector_warm` now stores the loaded model and backend information in the
Redis key `detector:warm`.  `inference_latency` consumes a rolling histogram
populated by the profiler which pushes recent inference durations (in
milliseconds) to the `inference:latency` list.
