from fastapi import APIRouter, HTTPException
from loguru import logger

from app.storage import redis_vms

router = APIRouter(prefix="/api/v1")


@router.post("/visitors")
def create_visitor(payload: dict) -> dict:
    vid = redis_vms.create_visitor(payload)
    logger.info({"stage": "vms", "action": "create_visitor", "id": vid})
    return {"id": vid}


@router.get("/visitors")
def list_visitors(full_name: str = "", phone: str = "") -> list[dict]:
    return redis_vms.list_visitors({"full_name": full_name, "phone": phone})


@router.post("/gate_pass")
def create_gate_pass(payload: dict) -> dict:
    gpid = redis_vms.create_gate_pass(
        int(payload["visitor_id"]),
        payload.get("host_name", ""),
        payload.get("purpose", ""),
        payload.get("visit_date", ""),
    )
    logger.info(
        {
            "stage": "vms",
            "action": "create_gate_pass",
            "id": gpid,
            "visitor_id": payload.get("visitor_id"),
            "status": "draft",
        }
    )
    return {"id": gpid, "status": "draft"}


@router.get("/gate_pass")
def list_gate_passes(
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    visitor_id: int | None = None,
) -> list[dict]:
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "visitor_id": visitor_id,
    }
    return redis_vms.list_gate_passes(filters)


@router.get("/gate_pass/{gpid}")
def get_gate_pass(gpid: int) -> dict:
    data = redis_vms.get_gate_pass(gpid)
    if not data:
        raise HTTPException(status_code=404, detail="not_found")
    return data


@router.post("/gate_pass/{gpid}/approve")
def approve_gate_pass(gpid: int) -> dict:
    try:
        res = redis_vms.approve_gate_pass(gpid)
    except RuntimeError as exc:
        if "active_exists" in str(exc):
            raise HTTPException(status_code=409, detail="active_exists")
        raise
    logger.info(
        {"stage": "vms", "action": "approve_gate_pass", "id": gpid, **res}
    )
    return {"ok": True, **res}


@router.post("/gate_pass/{gpid}/printed")
def mark_printed(gpid: int) -> dict:
    res = redis_vms.mark_printed(gpid)
    logger.info(
        {"stage": "vms", "action": "printed_gate_pass", "id": gpid, **res}
    )
    return {"ok": True, **res}


@router.delete("/gate_pass/{gpid}")
def delete_gate_pass(gpid: int) -> dict:
    redis_vms.soft_delete_gate_pass(gpid)
    logger.info({"stage": "vms", "action": "delete_gate_pass", "id": gpid})
    return {"ok": True}
