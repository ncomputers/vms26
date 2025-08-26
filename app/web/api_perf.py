"""Expose live performance metrics."""

from fastapi import APIRouter

from app.core.perf import PERF

from . import handle_errors

router = APIRouter()


@router.get("/api/v1/perf")
@handle_errors
def get_perf() -> dict:
    """Return per-camera performance statistics."""
    cams: dict[str, dict] = {}
    for cid, p in PERF.items():
        cams[cid] = {
            "fps_in": p.fps_in.value,
            "fps_out": p.fps_out.value,
            "qdepth": p.qdepth,
            "drops": p.drops,
            "det_p50": p.det_ms.p50(),
            "det_p95": p.det_ms.p95(),
            "trk_p50": p.trk_ms.p50(),
            "trk_p95": p.trk_ms.p95(),
            "last_ts": p.last_ts,
        }
    return {"cameras": cams}
