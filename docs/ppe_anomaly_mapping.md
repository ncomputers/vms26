# PPE and Anomaly Mapping

The available PPE tracking items and anomaly alerts are defined in `config` via `PPE_ITEMS` and `ANOMALY_ITEMS`.
Both the settings routes and dashboard templates read from these constants so new entries only need to be added in one place.
Updating the lists keeps server-side validation and client UI in sync.
