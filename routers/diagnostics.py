from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.diag import dump_threads
from modules.utils import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/api/v1/diag/threads")
async def diag_threads() -> list[dict]:
    """Return basic information about running threads."""
    return dump_threads()


def init_context(
    cfg: dict,
    trackers,
    cams,
    templates_path: str,
    redis_facade=None,
) -> None:
    """Initialize router-level state. Provided for API compatibility."""
    return None
