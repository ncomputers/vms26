# modules_stream_probe
[Back to Architecture Overview](../README.md)

## Purpose
Probe streams to gather codec metadata and measure effective FPS.

## Key Classes
- **TrialResult** – dataclass summarizing FFmpeg trial results.

## Key Functions
- **probe_stream(url, sample_seconds=2, enable_hwaccel=True)** – try different transports and hardware acceleration options.
- **check_rtsp(url, timeout_sec=5.0, rtsp_transport='tcp')** – minimal RTSP probe returning metadata or error codes.

## Configuration Notes
`probe_stream` tests TCP/UDP combinations and optional hardware acceleration to select the best settings.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
None

## Dependencies
- dataclasses
- json
- subprocess
- typing
