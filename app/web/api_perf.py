"""Expose live performance metrics."""

from fastapi import APIRouter

from app.core.perf import PERF as CAM_PERF
from app.core.prof import PERF as PROF

from . import handle_errors

router = APIRouter()


@router.get("/api/v1/perf")
@handle_errors
def get_perf() -> dict:
    """Return per-camera performance statistics."""
    cams: dict[str, dict] = {}
    for cid, p in CAM_PERF.items():
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
    prof: dict[str, dict[str, float]] = {}
    for name, samples in PROF.items():
        data = sorted(samples)
        if data:
            prof[name] = {
                "p50": data[int(0.5 * (len(data) - 1))],
                "p95": data[int(0.95 * (len(data) - 1))],
            }
        else:
            prof[name] = {"p50": 0.0, "p95": 0.0}
    return {"cameras": cams, "profile": prof}
