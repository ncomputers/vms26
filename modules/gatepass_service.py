"""Utilities for gate pass management backed by Redis."""

from __future__ import annotations

import json
from pathlib import Path

import redis
from fastapi import Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from config import config as cfg
from utils.image import decode_base64_image
from utils.redis import trim_sorted_set_sync


class GatepassService:
    """Helper methods for gate pass CRUD operations in Redis."""

    def __init__(self, client: redis.Redis):
        self.client = client

    # ------------------------------------------------------------------
    # rendering helpers
    # ------------------------------------------------------------------
    @staticmethod
    def build_qr_link(gate_id: str, request: Request) -> str:
        base = str(request.base_url).rstrip("/")
        return (
            f"{base}/gatepass/view/{gate_id}" if gate_id else f"{base}/gatepass/view/"
        )

    _template_dir = Path(__file__).resolve().parent.parent / "templates"
    _env = Environment(
        loader=FileSystemLoader(_template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    _env.globals["url_for"] = lambda name, path: (
        f"/static/{path}" if name == "static" else path
    )

    def render_gatepass_card(self, rec: dict, qr_image: str | None = None) -> str:
        rec_local = dict(rec)
        if rec_local.get("signature") and rec_local["signature"].startswith("static/"):
            rec_local["signature"] = f"/{rec_local['signature']}"
        branding = cfg.get("branding", {})
        cfg_local = dict(cfg)
        cfg_local["branding"] = dict(branding)
        logo = cfg_local["branding"].get("company_logo_url") or cfg_local.get(
            "logo_url"
        )
        if logo and logo.startswith("static/"):
            cfg_local["branding"]["company_logo_url"] = f"/{logo}"
            logo = cfg_local["branding"]["company_logo_url"]
        if logo and not (logo.startswith("http") or logo.startswith("/static/")):
            cfg_local["branding"]["company_logo_url"] = ""
            cfg_local["logo_url"] = ""
        footer = cfg_local["branding"].get("footer_logo_url") or cfg_local.get(
            "logo2_url"
        )
        if footer and footer.startswith("static/"):
            cfg_local["branding"]["footer_logo_url"] = f"/{footer}"
        color_map = {
            "pending": "warning text-dark",
            "approved": "success",
            "rejected": "danger",
            "created": "secondary",
        }
        status_color = color_map.get(rec.get("status", "created"), "secondary")
        template = self._env.get_template("partials/gatepass_card.html")
        html = template.render(
            rec=rec_local,
            branding=cfg_local.get("branding", {}),
            cfg=cfg_local,
            status_color=status_color,
            qr_img=qr_image,
            signature_url=rec_local.get("signature"),
        )
        return html.replace('"', "'")

    # ------------------------------------------------------------------
    # redis helpers
    # ------------------------------------------------------------------
    def _find_gatepass(self, gate_id: str) -> tuple[dict, str | bytes] | None:
        try:
            data = self.client.hget("gatepass:active", gate_id)
        except Exception as exc:
            logger.exception("failed to fetch gate pass {}: {}", gate_id, exc)
            raise RuntimeError("failed to fetch gate passes") from exc
        if data:
            obj = json.loads(data if isinstance(data, str) else data.decode())
            return obj, data
        return None

    def update_status(self, gate_id: str, status: str) -> bool:
        res = self._find_gatepass(gate_id)
        if not res:
            return False
        obj, entry = res
        obj["status"] = status
        self.client.zrem("vms_logs", entry)
        self.client.zadd("vms_logs", {json.dumps(obj): obj["ts"]})
        trim_sorted_set_sync(self.client, "vms_logs", obj["ts"])
        try:
            if status == "rejected" or obj.get("valid_to", 0) < int(time.time()):
                self.client.hdel("gatepass:active", gate_id)
                if obj.get("phone"):
                    self.client.hdel("gatepass:active_phone", obj["phone"])
            else:
                self.client.hset("gatepass:active", gate_id, json.dumps(obj))
                if obj.get("phone"):
                    self.client.hset("gatepass:active_phone", obj["phone"], gate_id)
        except Exception:
            logger.exception("Failed to update gate pass index for {}", gate_id)
        return True

    def save_signature(self, gate_id: str, data: str) -> str:
        if not data:
            return ""
        sig_dir = Path("static/signatures")
        sig_dir.mkdir(parents=True, exist_ok=True)
        path = sig_dir / f"{gate_id}.png"
        try:
            img_bytes = decode_base64_image(data)
            path.write_bytes(img_bytes)
        except ValueError:
            return ""
        res = self._find_gatepass(gate_id)
        stored_path = f"/static/signatures/{gate_id}.png"
        if res:
            obj, entry = res
            obj["signature"] = stored_path
            self.client.zrem("vms_logs", entry)
            self.client.zadd("vms_logs", {json.dumps(obj): obj["ts"]})
            trim_sorted_set_sync(self.client, "vms_logs", obj["ts"])
        return stored_path


# ------------------------------------------------------------------
# compatibility wrappers
# ------------------------------------------------------------------
_svc: GatepassService | None = None


def init(redis_client: redis.Redis) -> None:
    """Initialise the shared :class:`GatepassService` instance."""

    global _svc
    _svc = GatepassService(redis_client)


def _require_svc() -> GatepassService:
    if _svc is None:
        raise ValueError("Redis not initialized")
    return _svc


def build_qr_link(gate_id: str, request: Request) -> str:
    return GatepassService.build_qr_link(gate_id, request)


def render_gatepass_card(rec: dict, qr_image: str | None = None) -> str:
    return _require_svc().render_gatepass_card(rec, qr_image)


def update_status(gate_id: str, status: str) -> bool:
    return _require_svc().update_status(gate_id, status)


def save_signature(gate_id: str, data: str) -> str:
    return _require_svc().save_signature(gate_id, data)


__all__ = [
    "GatepassService",
    "init",
    "build_qr_link",
    "render_gatepass_card",
    "update_status",
    "save_signature",
]
