from __future__ import annotations

"""Gatepass approval and notification routes."""

import hmac
import json
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger

from config import config as cfg
from modules.email_utils import send_email, sign_token

from . import (
    _cache_gatepass,
    _format_gatepass_times,
    _load_gatepass,
    _qr_data_uri,
    config_obj,
    gatepass_service,
    redis,
    templates,
)

router = APIRouter()


@router.get("/gatepass/approve", name="gatepass_approve")
async def gatepass_approve(token: str, request: Request) -> HTMLResponse:
    """Validate token and display gate pass for approval."""
    try:
        gp_id, sig = token.split(":", 1)
    except ValueError:
        return HTMLResponse("invalid token", status_code=400)
    stored_sig = redis.get(f"gatepass:signature:{gp_id}")
    if isinstance(stored_sig, bytes):
        stored_sig = stored_sig.decode()
    if not stored_sig or not hmac.compare_digest(stored_sig, sig):
        return HTMLResponse("invalid token", status_code=400)
    url = request.url_for("gatepass_view", gate_id=gp_id)
    return RedirectResponse(f"{url}?token={token}")


@router.post("/gatepass/approve")
async def gatepass_approve_submit(
    request: Request,
    token: str | None = Form(None),
    gate_id: str | None = Form(None),
    host_pass: str = Form(""),
):
    """Approve a pending gate pass after verifying host password."""
    gp_id = gate_id
    if token:
        try:
            gp_id, sig = token.split(":", 1)
        except ValueError:
            return JSONResponse({"error": "invalid_token"}, status_code=400)
        stored_sig = redis.get(f"gatepass:signature:{gp_id}")
        if isinstance(stored_sig, bytes):
            stored_sig = stored_sig.decode()
        if not stored_sig or not hmac.compare_digest(stored_sig, sig):
            return JSONResponse({"error": "invalid_token"}, status_code=400)
    if not gp_id:
        return JSONResponse({"error": "invalid_token"}, status_code=400)
    obj = _load_gatepass(gp_id)
    if not obj:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if obj.get("host", "").strip().lower() != host_pass.strip().lower():
        return JSONResponse({"error": "verification_failed"}, status_code=403)
    obj["status"] = "approved"
    redis.zadd("vms_logs", {json.dumps(obj): int(obj["ts"])})
    _cache_gatepass(obj)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"approved": True})
    url = request.url_for("gatepass_view", gate_id=gp_id)
    return RedirectResponse(f"{url}?approved=1", status_code=302)


@router.get("/gatepass/reject", name="gatepass_reject")
async def gatepass_reject(token: str, request: Request) -> HTMLResponse:
    try:
        gp_id, sig = token.split(":", 1)
    except ValueError:
        return HTMLResponse("invalid token", status_code=400)
    stored_sig = redis.get(f"gatepass:signature:{gp_id}")
    if isinstance(stored_sig, bytes):
        stored_sig = stored_sig.decode()
    if not stored_sig or not hmac.compare_digest(stored_sig, sig):
        return HTMLResponse("invalid token", status_code=400)
    obj = _load_gatepass(gp_id)
    if obj:
        obj["status"] = "rejected"
        redis.zadd("vms_logs", {json.dumps(obj): int(obj["ts"])})
        _cache_gatepass(obj)
        return templates.TemplateResponse(
            "gatepass_confirm.html", {"request": request, "status": "rejected"}
        )
    return HTMLResponse("not found", status_code=404)


@router.get("/pending-requests")
async def pending_requests(request: Request):
    entries = redis.zrevrange("vms_logs", 0, -1)
    rows = []
    for e in entries:
        obj = json.loads(e)
        if obj.get("status") == "pending":
            obj["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(obj["ts"]))
            rows.append(obj)
    return templates.TemplateResponse(
        "pending_requests.html",
        {
            "request": request,
            "rows": rows,
            "cfg": cfg,
            "build_qr_link": gatepass_service.build_qr_link,
        },
    )


@router.post("/gatepass/resend/{gp_id}")
async def gatepass_resend(gp_id: str, request: Request) -> JSONResponse:
    try:
        obj = _load_gatepass(gp_id)
    except RuntimeError:
        return JSONResponse({"error": "redis_unavailable"}, status_code=503)
    if obj and obj.get("status") == "pending":
        email = obj.get("approver_email")
        if email:
            tok = f"{gp_id}:{sign_token(gp_id, config_obj.get('secret_key', 'secret'))}"
            approve_url = request.url_for("gatepass_approve", token=tok)
            reject_url = request.url_for("gatepass_reject", token=tok)
            _format_gatepass_times(obj)
            qr_img = _qr_data_uri(gatepass_service.build_qr_link(gp_id, request))
            card_html = gatepass_service.render_gatepass_card(obj, qr_img)
            msg = (
                f"{card_html}"
                f"<p><a href='{approve_url}'>Approve</a> | <a href='{reject_url}'>Reject</a></p>"
            )
            send_email(
                "Gate Pass Approval",
                msg,
                [email],
                config_obj.get("email", {}),
                html=True,
            )
        return JSONResponse({"resent": True})
    return JSONResponse({"error": "not_found"}, status_code=404)


@router.post("/gatepass/cancel/{gp_id}")
async def gatepass_cancel(gp_id: str) -> JSONResponse:
    try:
        obj = _load_gatepass(gp_id)
    except RuntimeError:
        return JSONResponse({"error": "redis_unavailable"}, status_code=503)
    if obj:
        obj["status"] = "rejected"
        try:
            redis.zadd("vms_logs", {json.dumps(obj): int(obj["ts"])})
            _cache_gatepass(obj)
        except Exception:
            logger.exception("Redis unavailable while cancelling gate pass {}", gp_id)
            return JSONResponse({"error": "redis_unavailable"}, status_code=503)
        return JSONResponse({"cancelled": True})
    return JSONResponse({"error": "not_found"}, status_code=404)
