# routers_api_summary
[Back to Architecture Overview](../README.md)

## Purpose
Provide aggregated counts over a date range.

## Key Classes
None

## Key Functions
- **get_summary(...)** - Return aggregated sums of in/out counts for specified groups.

## GET /api/v1/summary

Retrieve aggregated counts.

### Parameters

- `from`: start date in `YYYY-MM-DD` format.
- `to`: end date in `YYYY-MM-DD` format.
- `group`: comma-separated groups (`person`, `vehicle`).
- `metric`: comma-separated metrics (`in`, `out`).

### Example Response

```json
{
  "person": {"in": 5, "out": 3},
  "vehicle": {"in": 1, "out": 0}
}
```

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
- `summaries:YYYY-MM-DD` - daily summary hashes.
- `person_logs`, `vehicle_logs` - event fallbacks.

## Dependencies
- fastapi
- modules.events_store
- config
- utils.deps
