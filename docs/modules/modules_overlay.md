# modules_overlay
[Back to Architecture Overview](../README.md)

## Purpose
Purpose: Overlay module. Debug overlays use solid LINE_8 drawing without
alpha blending or antialiasing, and labels are limited to a single line
of text with no shadows or rounded corners.

The renderer loads a bundled DejaVuSans font once at startup and falls back
to Pillow's default font if the file is missing.

## Key Classes
None

## Key Functions
- **draw_overlays(frame, tracks, show_ids, show_track_lines, show_lines, line_orientation, line_ratio, show_counts, counts, face_boxes=None)** - Draw tracking debug overlays and optional face bounding boxes on the frame. ``counts`` should map ``"entered"``, ``"exited"``, and ``"inside"``.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs. When any debug flag (lines, IDs, track lines, counts, or face boxes) is enabled the processed frame is streamed via `/stream/{cam_id}`; otherwise the dashboard requests `/stream/{cam_id}?raw=1`. Client-side scripts update the feed URL when these settings change.

## Overlay Types

The diagnostics overlay page (`/diagnostics/overlay/{id}`) provides a button group where only one overlay can be active at a time:

- **Vehicle** – bounding boxes and trails for detected vehicles.
- **Person** – bounding boxes and trails for detected people.
- **Center Line** – displays the configured counting line.
- **Vehicle Count** – shows vehicle entry/exit counts.
- **Person Count** – shows person entry/exit counts.
- **Face Count** – shows the number of detected faces.
- **ID** – labels tracks with their numeric IDs.
- **Face Recognition** – draws face detection boxes.
- **Face ID** – displays face boxes with associated IDs.

Display preference settings no longer expose these toggles; choose the desired overlay directly from the diagnostics overlay page.

## Configuration

The diagnostics overlay resolves its backend using the ``OVERLAY_BASE_URL`` environment variable. Set this to the base URL hosting the overlay service; it defaults to ``http://localhost:8000``.

## Redis Keys
None

## Dependencies
- cv2
- typing

## Coordinate Spaces and Counting

Track coordinates returned by the model may be in a letterboxed space. Before
drawing overlays or computing entry/exit counts, convert them back to the
original frame using the stored ``pad_x``, ``pad_y`` and ``scale`` values:

```python
l_raw, t_raw, r_raw, b_raw = trk.to_ltrb()
l = (l_raw - pad_x) / scale
t = (t_raw - pad_y) / scale
r = (r_raw - pad_x) / scale
b = (b_raw - pad_y) / scale
cx = (l + r) // 2
cy = (t + b) // 2
side_val = side((cx, cy), (0, line_pos), (w - 1, line_pos), eps)
```

The ``side`` helper uses an epsilon (default ``2.0``) to ignore jitter around
the counting line, returning ``-1``, ``0`` or ``1`` based on the cross-product
sign. ``point_line_distance`` complements this by reporting the perpendicular
distance to the counting line so that crossings require moving beyond a
``cross_hysteresis`` threshold.
