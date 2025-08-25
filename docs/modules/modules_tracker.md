# modules_tracker
[Back to Architecture Overview](../README.md)

## Purpose
Utilities for object tracking built around the `deep_sort_realtime` library.

## Key Classes
- **Tracker** - Thin wrapper around `DeepSort` allowing easy substitution in tests.

## Key Functions
None

## Configuration Notes
- `use_gpu_embedder` toggles GPU usage for the embedding model.
- `max_age` specifies how many frames a lost track is kept (default 10).

## Inputs and Outputs
Refer to class methods for inputs and outputs.

## Redis Keys
None

## Dependencies
- deep_sort_realtime *(optional)*
- typing

## Debug Statistics

`PersonTracker` exposes a set of runtime metrics via `get_debug_stats()` and
`get_queue_stats()`.  Useful fields include:

- `last_frame_ts` – timestamp of the most recent captured frame.
- `capture_fps` – rolling average frames-per-second.
- `jitter_ms` – difference between the slowest and fastest recent frame
  intervals in milliseconds.
- `dropped_frames` – number of frames discarded when the input queue is full.
- `last_overlay_ts` – timestamp of the last successfully rendered overlay.
- `overlay_match` – whether the overlay canvas matches the capture frame
  dimensions.
- `det_in` – current depth of the detection input queue.


## Coordinate Conversion

Detections and track boxes may be produced in the model's letterboxed space.
The tracker stores ``pad_x``, ``pad_y`` and ``scale`` so that tracked boxes
can be mapped back to the original frame:

```python
l_raw, t_raw, r_raw, b_raw = trk.to_ltrb()
l = (l_raw - pad_x) / scale
t = (t_raw - pad_y) / scale
r = (r_raw - pad_x) / scale
b = (b_raw - pad_y) / scale
```

The unscaled coordinates are used for center/side calculations and for
drawing overlays.

## Counting Line Geometry

Crossing detection relies on two helpers:

- ``side(point, a, b, eps)`` – returns ``-1`` when the point lies to the right
  of the line segment ``ab``, ``1`` when to the left and ``0`` when within
  ``eps`` units of the line.
- ``point_line_distance(point, a, b)`` – computes the perpendicular distance
  from a point to the counting line.

Each track stores its previous side and its previous distance from the line. A
crossing is counted only when the sign flips, the track has remained on the
previous side for ``cross_min_frames`` frames, has travelled at least
``cross_min_travel_px`` pixels and both the previous and current distances are
greater than ``cross_hysteresis`` to provide hysteresis around the counting
line.
