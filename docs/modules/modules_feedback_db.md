# modules_feedback_db
[Back to Architecture Overview](../README.md)

## Purpose
Store user feedback records in Redis.

## Key Functions
- **create_feedback(redis_client, data)** – persist a feedback record and return its ID.
- **list_feedback(redis_client)** – list all stored feedback entries.
- **update_status(redis_client, feedback_id, status)** – update the status field for a record.

## Configuration Notes
Records are stored as hashes named `feedback:entry:<id>` and IDs are tracked in the `feedback:ids` set.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
- `feedback:ids`
- `feedback:entry:<id>`

## Dependencies
- redis
- loguru
- typing
- utils.ids
