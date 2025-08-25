# modules_face_engine_utils
[Back to Architecture Overview](../README.md)

## Purpose
Helper functions for the face engine.

## Key Classes
None

## Key Functions
- **load_image(data)** - Load an image from raw bytes or base64 string.
- **crop_face(image, bbox)** -
- **resize(image, max_size)** -
- **is_blurry(image, threshold)** -
- **face_count(image, detector)** -

## Thresholds, defaults, and usage
The face engine centralizes common thresholds in `config.FaceThresholds`.
These settings can be overridden through configuration and are consumed by
helpers such as `is_blurry` and the face database utilities.

| Name | Default | Override Key | Usage |
| ---- | ------- | ------------ | ----- |
| `recognition_match` | `0.6` | `face_match_thresh` | Minimum similarity score required to consider two faces a match during recognition. |
| `db_duplicate` | `0.95` | `face_db_dup_thresh` | Treat two face embeddings as the same person when adding to the database. |
| `duplicate_suppression` | `0.5` | `face_duplicate_thresh` | Suppress repeated detections of the same face to reduce duplicates. |
| `blur_detection` | `100.0` | `blur_detection_thresh` | Variance of Laplacian below this value marks an image as blurry and skips processing. |
| `face_count_conf` | `0.85` | `face_count_conf` | Detection confidence for face counting. |
| `face_count_similarity` | `0.6` | `face_count_similarity` | Match threshold to avoid double-counting faces. |
| `face_count_min_size` | `80.0` | `face_count_min_size` | Smallest face size considered for counting. |

### Interaction examples
- **Counting:** a face contributes to the count only when detection confidence
  exceeds `face_count_conf` **and** its similarity to an existing track is
  below `face_count_similarity`.

## Inputs and Outputs
Refer to function signatures above for inputs and outputs.

## Redis Keys
None

## Dependencies
- __future__
- base64
- cv2
- numpy
- typing
