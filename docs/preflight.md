# Preflight Checks

`scripts/preflight.py` prints a quick summary of common dependencies.
It checks:

- Redis connectivity and configured camera count
- CUDA availability
- TurboJPEG library presence
- Configuration file parsing from `CONFIG_PATH`

Run:

```bash
python scripts/preflight.py
```

Each line is tagged `OK` or `WARN` with ANSI colors and the script always exits
with code 0 so it can be safely used in logs or startup scripts.
