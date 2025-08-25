# Models

Detection models are loaded through the [vision registry](../app/vision/registry.py).

* Configure model paths with environment variables `VMS21_YOLO_PERSON` and `VMS21_YOLO_PPE` (default `yolov8s.pt` and `ppe.pt`).
* Models typically use the YOLOv8 architecture for person and PPE detection.
