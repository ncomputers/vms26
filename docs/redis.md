# Redis

Redis acts as the central message bus and datastore.

* Configure the connection via the `redis_url` setting in [config.json](../config.json). The application requires a running Redis instance and aborts startup if it cannot connect.
* `storage_backend` controls persistence; currently only `redis` is supported.
* Crossing events are stored in sorted sets:
  * `person_logs` and `vehicle_logs` contain entry/exit events.
  * All raw events may also be mirrored in the `events` set.
* Real-time line-cross events are pushed to the `events_stream` Redis stream with
  fields `camera_id`, `ts_ms`, `kind`, `group`, `track_id` and `line_id`.
* Per-camera state is tracked in hashes `cam:<id>:state` storing `fps_in`,
  `fps_out` and the most recent `last_error`.
* If migrating from earlier versions, remove the obsolete `events.db` SQLite file
  after verifying Redis contains the required history.
* Publishing `cam:<id>` to the `counter.config` channel reloads that camera's
  line configuration and `track_objects` list without restarting trackers.
* The `CFG_VERSION` key increments whenever configuration is updated. Use
  `watch_config` to refresh application settings when this version changes.
* The ``app.core.redis_bus`` module provides helpers for publishing events to
  the ``events`` stream via ``xadd_event`` and for updating
  ``cam:<id>:state`` hashes through ``set_cam_state`` with an expiry.
