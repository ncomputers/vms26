# Models

Detection models are loaded through the [vision registry](../app/vision/registry.py).

* Configure model paths with environment variables `YOLO_PERSON` and `YOLO_PPE` (default `yolov8s.pt` and `ppe.pt`).
* Models typically use the YOLOv8 architecture for person and PPE detection.
