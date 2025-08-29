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

The unscaled coordinates are used for center/side calculations.

## Counting Line Geometry

Crossing detection relies on ``side(point, a, b, eps)`` which returns ``-1`` when
the point lies to the right of the line segment ``ab``, ``1`` when to the left
and ``0`` when within ``eps`` units of the line.

For each line, the tracker keeps per-track state with the last side and whether
an entry or exit has already been counted. When the side changes from non-zero
to the opposite sign, a single event is emitted:

* ``+1`` → ``entered``
* ``-1`` → ``exited``

Tracks with low confidence or fewer than two frames of age are ignored to avoid
jitter, and state is evicted if a track is not seen for over 120 seconds.
