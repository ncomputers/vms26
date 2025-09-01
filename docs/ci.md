# CI and Testing Quick Start

This guide shows how to set up the development environment and run the quality
checks used in continuous integration.

## Install developer dependencies

```bash
pip install -r requirements.txt
pip install pre-commit ruff pytest uvicorn
pre-commit install
```

## Run pre-commit hooks

Run all formatting and lint checks:

```bash
pre-commit run --all-files
```

## Code formatting

`pre-commit` runs Black, isort and Ruff automatically. To format the repository
manually you can run:

```bash
ruff check .
black .
isort .
```

## Unit tests

Execute the Python unit tests:

```bash
pytest
```

## Integration tests

The full test suite, including a basic server startup check, can be executed
with:

```bash
bash scripts/run_all_tests.sh
```

## Pytest markers

- `slow` – marks long-running tests. Skip them with `-m "not slow"` or run only
  them with `-m slow`.
- `anyio` – used for asynchronous tests that run under the AnyIO framework.
- `xfail` – tests that are expected to fail until the related feature is
  implemented.

## Environment variables

These environment variables affect tests and local development:

| Variable | Description |
|----------|-------------|
| `CONFIG_PATH` | Path to the configuration file. Defaults to `config.json`. |
| `WORKERS` | Override the number of worker threads used by the server. |
| `QUEUE_MAX` | Maximum size of the internal processing queue. |
| `TARGET_FPS` | Target frame processing rate for the pipeline. |
| `TZ` | Time zone used in tests for date/time handling. |
| `ALLOW_UNAUTHENTICATED_STREAM` | If set, disables stream authentication in development. |
