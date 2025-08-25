# Alerts

This document describes the event-driven alerting system. Modules publish
Redis events using constants from `core.events` and PPE status strings. The
`AlertWorker` monitors these events and applies rules to send notifications.

## Event Sources

| Identifier | Emitted by | Sample rule |
|------------|------------|-------------|
| `ppe_violation` | `modules.ppe_worker` | `{ "metric": "ppe_violation", "type": "event", "value": 1, "recipients": "safety@example.com" }` |
| `failed_login` | `routers.auth` | `{ "metric": "failed_login", "type": "event", "value": 1, "recipients": "admin@example.com" }` |
| `face_unrecognized` | `modules.visitor_worker` | `{ "metric": "face_unrecognized", "type": "event", "value": 1, "recipients": "security@example.com" }` |
| `face_blurry` | `modules.visitor_worker` | `{ "metric": "face_blurry", "type": "event", "value": 1, "recipients": "security@example.com" }` |
| `gatepass_created` | `routers.gatepass.create` | `{ "metric": "gatepass_created", "type": "event", "value": 1, "recipients": "security@example.com" }` |
| `gatepass_approved` | `routers.gatepass.approval` | `{ "metric": "gatepass_approved", "type": "event", "value": 1, "recipients": "host@example.com" }` |
| `gatepass_rejected` | `routers.gatepass.approval` | `{ "metric": "gatepass_rejected", "type": "event", "value": 1, "recipients": "host@example.com" }` |
| `gatepass_overdue` | `modules.alerts` | `{ "metric": "gatepass_overdue", "type": "event", "value": 1, "recipients": "security@example.com" }` |
| `visitor_registered` | `routers.visitor.registration` | `{ "metric": "visitor_registered", "type": "event", "value": 1, "recipients": "reception@example.com" }` |
| `camera_offline` | `core.camera_manager` | `{ "metric": "camera_offline", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `network_usage_high` | `workers.system_monitor` | `{ "metric": "network_usage_high", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `network_usage_low` | `workers.system_monitor` | `{ "metric": "network_usage_low", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `disk_space_low` | `workers.system_monitor` | `{ "metric": "disk_space_low", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `system_cpu_high` | `workers.system_monitor` | `{ "metric": "system_cpu_high", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `person_entry` | `routers.entry` | `{ "metric": "person_entry", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `person_exit` | `routers.entry` | `{ "metric": "person_exit", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `vehicle_entry` | `routers.entry` | `{ "metric": "vehicle_entry", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `vehicle_exit` | `routers.entry` | `{ "metric": "vehicle_exit", "type": "event", "value": 1, "recipients": "ops@example.com" }` |
| `vehicle_detected` | `routers.entry_stats` | `{ "metric": "vehicle_detected", "type": "event", "value": 1, "recipients": "ops@example.com" }` |

PPE anomaly statuses such as `no_helmet`, `no_vest_jacket` and others are
emitted by `modules.ppe_worker`. A rule example:

```json
{ "metric": "no_helmet", "type": "threshold", "value": 2, "window": 5, "recipients": "safety@example.com" }
```

## Redis Keys

* `events` – sorted set of published events. Each item is a JSON object with
  a `ts` timestamp and `event` field.
* `vms_logs` – visitor management system logs used for rules involving
  visitor activity.
* `ppe_logs` – PPE detection logs for anomaly-based rules.

## Report Attachments

`AlertWorker` uses two helpers to generate email reports:

* `_send_report` – builds a PPE spreadsheet and optionally attaches images.
* `_send_vms_report` – builds a visitor log spreadsheet.

Both helpers attach the generated report when `attach` is true in the rule.
