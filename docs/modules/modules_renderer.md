# modules_renderer
[Back to Architecture Overview](../README.md)

## Purpose
Draw tracking overlays in a separate process using shared memory.

## Key Classes
- **RendererProcess** – manages a subprocess that renders overlays into shared memory.

## Key Functions
- **_render_loop(shm_in_name, shm_out_name, queue, shape)** – process target that applies overlays to frames.

## Configuration Notes
Frames are exchanged via `multiprocessing.shared_memory` and overlay flags are passed through a queue.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
None

## Dependencies
- multiprocessing
- numpy
- modules.overlay
