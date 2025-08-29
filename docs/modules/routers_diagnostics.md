# routers.diagnostics
[Back to Architecture Overview](../README.md)

## Purpose
Expose administrative diagnostics helpers.

## Key Functions
- **diag_threads()** – return basic info about running threads.

## GET /api/v1/diag/threads
Return a list of currently running threads with their names, liveness and identifiers.

### Example Response
```json
[
  {"name": "MainThread", "alive": true, "ident": 1}
]
```

## Inputs and Outputs
No inputs. Returns a list of objects with ``name``, ``alive`` and ``ident`` fields.
