# modules.pipeline
[Back to Architecture Overview](../README.md)

## Purpose
Provides a lightweight demo pipeline comprising a capture loop and a process
loop. Frames are generated, encoded to JPEG and exposed via
`get_frame_bytes()` for MJPEG streaming. The capture loop writes frames to a
bounded ``collections.deque`` controlled by the ``QUEUE_MAX`` environment
variable (default ``2``). When the deque is full the oldest frame is dropped
before appending the new one. The process loop pulls frames from the deque,
sleeping briefly when empty and pacing work to the ``TARGET_FPS``
setting.

## Key Classes
- **Pipeline** – orchestrates background capture and processing threads.
- **CaptureLoop** – daemon thread placing frames into a deque without
  blocking.
- **ProcessLoop** – daemon thread encoding frames to JPEG bytes while
  pacing to a target frame rate.
- Threads are named ``cap-{id}`` and ``proc-{id}`` to aid diagnostics.

## Key Functions
- **Pipeline.start()** – launch capture and process threads.
- **Pipeline.get_frame_bytes()** – return latest encoded frame.

## Inputs and Outputs
Accepts a camera configuration dictionary on construction and outputs JPEG
encoded frames accessible through `get_frame_bytes`.
