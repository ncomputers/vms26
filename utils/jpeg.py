from __future__ import annotations

from os import getenv

try:  # Prefer turbojpeg when available
    if getenv("VMS26_TURBOJPEG", "auto") in ("auto", "1"):
        from turbojpeg import TurboJPEG  # type: ignore

        _jpeg = TurboJPEG()

        def encode_jpeg(np_bgr, q: int) -> bytes:
            return _jpeg.encode(np_bgr, quality=q)

    else:  # pragma: no cover - explicit disable
        raise ImportError
except Exception:  # pragma: no cover - fallback to OpenCV
    import cv2  # type: ignore

    def encode_jpeg(np_bgr, q: int) -> bytes:
        ok, buf = cv2.imencode(".jpg", np_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(q)])
        return buf.tobytes() if ok else b""


__all__ = ["encode_jpeg"]
