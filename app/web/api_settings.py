from fastapi import APIRouter

from app.core.config import get_vms_ui, set_vms_ui

router = APIRouter(prefix="/api/v1/settings")


@router.patch("/vms")
def patch_vms_settings(payload: dict) -> dict:
    config = set_vms_ui(payload)
    return config
