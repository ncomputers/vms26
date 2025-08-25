# modules.pipeline
[Back to Architecture Overview](../README.md)

## Purpose
Provides a lightweight demo pipeline comprising a capture loop and a process
loop. Frames are generated, encoded to JPEG and exposed via
`get_overlay_bytes()` for MJPEG streaming.

## Key Classes
- **Pipeline** – orchestrates background capture and processing threads.
- **CaptureLoop** – daemon thread placing frames into a queue.
- **ProcessLoop** – daemon thread encoding frames to overlay bytes.

## Key Functions
- **Pipeline.start()** – launch capture and process threads.
- **Pipeline.get_overlay_bytes()** – return latest encoded overlay frame.

## Inputs and Outputs
Accepts a camera configuration dictionary on construction and outputs JPEG
encoded overlay frames accessible through `get_overlay_bytes`.
