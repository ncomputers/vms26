# Redis

Redis acts as the central message bus and datastore.

* Configure the connection via the `redis_url` setting in [config.json](../config.json). The application requires a running Redis instance and aborts startup if it cannot connect.
* `storage_backend` controls persistence; currently only `redis` is supported.
* Crossing events are stored in sorted sets:
  * `person_logs` and `vehicle_logs` contain entry/exit events.
  * `face_logs` tracks counted faces.
  * All raw events may also be mirrored in the `events` set.
* Known face metadata is persisted under keys of the form `face:known:<id>` with
  all IDs stored in the `face:known_ids` set.
* Visitor lookups use the `visitor:face_ids` hash mapping gate-pass or visitor IDs
  to their corresponding face IDs.
* If migrating from earlier versions, remove the obsolete `events.db` SQLite file
  after verifying Redis contains the required history.
* Publishing `cam:<id>` to the `counter.config` channel reloads that camera's
  line configuration and `track_objects` list without restarting trackers.
* The `CFG_VERSION` key increments whenever configuration is updated. Use
  `watch_config` to refresh application settings when this version changes.
