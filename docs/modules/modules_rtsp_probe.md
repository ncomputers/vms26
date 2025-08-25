# modules_rtsp_probe
[Back to Architecture Overview](../README.md)

## Purpose
Auto-detect RTSP stream base paths by trying common camera URL patterns.

## Key Functions
- **probe_rtsp_base(host, user=None, password=None)** – return the first working RTSP URL built from ``host`` and predefined candidate paths.

## Configuration Notes
Uses ``ffprobe`` with TCP transport and a short timeout to test candidate paths.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
None

## Dependencies
- subprocess
- typing
