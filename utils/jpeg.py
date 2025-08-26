from __future__ import annotations

from os import getenv

from app.core.prof import profiled

DEFAULT_JPEG_QUALITY = int(getenv("VMS26_JPEG_QUALITY", "80"))

try:  # Prefer turbojpeg when available
    if getenv("VMS26_TURBOJPEG", "auto") in ("auto", "1"):
        from turbojpeg import TurboJPEG  # type: ignore

        _jpeg = TurboJPEG()

        def encode_jpeg(np_bgr, quality: int | None = None) -> bytes:
            q = int(quality if quality is not None else DEFAULT_JPEG_QUALITY)
            return _jpeg.encode(np_bgr, quality=q)

        encode_jpeg = profiled("enc")(encode_jpeg)

    else:  # pragma: no cover - explicit disable
        raise ImportError
except Exception:  # pragma: no cover - fallback to OpenCV
    import cv2  # type: ignore

    def encode_jpeg(np_bgr, quality: int | None = None) -> bytes:
        q = int(quality if quality is not None else DEFAULT_JPEG_QUALITY)
        ok, buf = cv2.imencode(".jpg", np_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        return buf.tobytes() if ok else b""

    encode_jpeg = profiled("enc")(encode_jpeg)


__all__ = ["encode_jpeg"]
