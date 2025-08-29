"""High level tracking package."""

from .detector import Detector
from .manager import InferWorker, PersonTracker, PostProcessWorker, ProcessingWorker
from .stream import CaptureWorker
from .tracker import Tracker


class _TrackerCache:
    """Provide read access to latest tracker detections."""

    def get_latest(self, camera_id: int):
        """Return latest detections for ``camera_id``.

        Each detection is a ``dict`` with ``bbox``, ``cls`` and ``conf`` keys.
        Falls back to an empty list when no data is available.
        """

        try:
            from routers import cameras  # lazy import to avoid circular deps

            tr = cameras.trackers_map.get(camera_id)
        except Exception:  # pragma: no cover - missing trackers or import error
            return []
        if not tr:
            return []
        dets = []
        for info in getattr(tr, "tracks", {}).values():
            bbox = info.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            dets.append(
                {
                    "bbox": list(bbox),
                    "cls": info.get("group") or info.get("label"),
                    "conf": info.get("conf"),
                }
            )
        return dets


tracker = _TrackerCache()


__all__ = [
    "PersonTracker",
    "InferWorker",
    "PostProcessWorker",
    "ProcessingWorker",
    "CaptureWorker",
    "Detector",
    "Tracker",
    "tracker",
]
