# modules_frame_bus
[Back to Architecture Overview](../README.md)

## Purpose
Small ring buffer holding recent frames for a camera.

## Key Classes
- **FrameBus** - Thread-safe buffer exposing ``put``, ``get_latest`` and ``info``.

## Inputs and Outputs
- ``put(frame)`` stores a numpy array and updates metadata.
- ``get_latest(timeout_ms)`` retrieves the newest frame or ``None`` on timeout.
- ``info()`` returns width, height and FPS of the latest frame.

## Dependencies
- collections
- dataclasses
- numpy
- threading
- time
