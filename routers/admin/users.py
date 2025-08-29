from __future__ import annotations

"""User management routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from config import DEFAULT_MODULES
from config.storage import save_config
from modules.utils import hash_password, require_admin
from schemas.user import UserCreate, UserUpdate

# Default roles for user accounts
DEFAULT_ROLES = ["admin", "viewer"]

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

cfg: dict = {}
redis = None
templates: Jinja2Templates
cfg_path: str = ""
redisfx = None


def allowed_roles() -> list[str]:
    """Return permitted user roles from configuration."""
    return cfg.get("roles", DEFAULT_ROLES)


def available_modules() -> list[str]:
    """Return available modules from configuration."""
    modules = cfg.get("modules")
    if modules is None:
        modules = DEFAULT_MODULES.copy()
        cfg["modules"] = modules
        save_config(cfg, cfg_path, redis)
    return modules


# init_context routine
def init_context(
    config: dict,
    redis_client,
    templates_path: str,
    config_path: str,
    redis_facade=None,
):
    """Store shared objects for user management routes."""
    global cfg, redis, templates, cfg_path, redisfx
    cfg = config
    redis = redis_client
    redisfx = redis_facade
    templates = Jinja2Templates(directory=templates_path)
    templates.env.add_extension("jinja2.ext.do")
    cfg_path = config_path


@router.get("/users")
async def users_page(request: Request):
    """Render a simple user management page."""
    roles = allowed_roles()
    modules = available_modules()
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "users": cfg.get("users", []),
            "cfg": cfg,
            "roles": roles,
            "modules": modules,
        },
    )


@router.post("/users")
async def create_user(user: UserCreate, current=Depends(require_admin)):
    """Create a new user and persist to config."""
    users = cfg.setdefault("users", [])
    if any(u["username"] == user.username for u in users):
        raise HTTPException(status_code=400, detail="exists")
    roles = allowed_roles()
    modules = available_modules()
    if user.role not in roles:
        raise HTTPException(status_code=400, detail="invalid_role")
    if any(m not in modules for m in user.modules):
        raise HTTPException(status_code=400, detail="invalid_module")
    users.append(
        {
            "username": user.username,
            "password": user.password or "",
            "role": user.role,
            "modules": user.modules,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "require_2fa": user.require_2fa,
            "status": "pending",
            "mfa_enabled": user.mfa_enabled,
            "last_login": user.last_login,
            "created_on": datetime.utcnow(),
            "created_by": current.get("name"),
        }
    )
    save_config(cfg, cfg_path, redis)
    return {"created": True}


@router.put("/users/{username}")
async def update_user(username: str, data: UserUpdate):
    """Update an existing user."""
    users = cfg.get("users", [])
    roles = allowed_roles()
    modules = available_modules()
    for u in users:
        if u["username"] == username:
            if data.password is not None:
                u["password"] = hash_password(data.password)
            if data.role is not None:
                if data.role not in roles:
                    raise HTTPException(status_code=400, detail="invalid_role")
                u["role"] = data.role
            if data.modules is not None:
                if any(m not in modules for m in data.modules):
                    raise HTTPException(status_code=400, detail="invalid_module")
                u["modules"] = data.modules
            if data.email is not None:
                u["email"] = data.email
            if data.name is not None:
                u["name"] = data.name
            if data.phone is not None:
                u["phone"] = data.phone
            if data.require_2fa is not None:
                u["require_2fa"] = data.require_2fa
            if data.status is not None:
                u["status"] = data.status
            if data.mfa_enabled is not None:
                u["mfa_enabled"] = data.mfa_enabled
            if data.last_login is not None:
                u["last_login"] = data.last_login

            save_config(cfg, cfg_path, redis)
            return {"updated": True}
    raise HTTPException(status_code=404, detail="not_found")


@router.delete("/users/{username}")
async def delete_user(username: str):
    """Remove a user from the configuration."""
    users = cfg.get("users", [])
    for i, u in enumerate(users):
        if u["username"] == username:
            if (
                u.get("role") == "admin"
                and sum(1 for usr in users if usr.get("role") == "admin") == 1
            ):
                raise HTTPException(status_code=400, detail="cannot_delete_last_admin")

            users.pop(i)
            save_config(cfg, cfg_path, redis)
            return {"deleted": True}
    raise HTTPException(status_code=404, detail="not_found")


def _set_status(username: str, status: str) -> dict:
    users = cfg.get("users", [])
    for u in users:
        if u["username"] == username:
            u["status"] = status
            save_config(cfg, cfg_path, redis)
            return {"status": status}
    raise HTTPException(status_code=404, detail="not_found")


@router.post("/users/{username}/enable")
async def enable_user(username: str):
    """Enable a user account."""
    return _set_status(username, "active")


@router.post("/users/{username}/disable")
async def disable_user(username: str):
    """Disable a user account."""
    return _set_status(username, "disabled")


@router.post("/users/{username}/reset-password")
async def reset_password(username: str):
    """Reset a user's password."""
    users = cfg.get("users", [])
    for u in users:
        if u["username"] == username:
            u["password"] = ""

            save_config(cfg, cfg_path, redis)
            return {"reset": True}
    raise HTTPException(status_code=404, detail="not_found")


@router.post("/users/{username}/force-logout")
async def force_logout(username: str):
    """Force a user to log out by clearing last login."""
    users = cfg.get("users", [])
    for u in users:
        if u["username"] == username:
            u["last_login"] = None
            save_config(cfg, cfg_path, redis)
            return {"logout": True}
    raise HTTPException(status_code=404, detail="not_found")


@router.get("/users/export")
async def export_users():
    """Export user data without passwords."""
    users = cfg.get("users", [])
    data = [{k: v for k, v in u.items() if k != "password"} for u in users]
    save_config(cfg, cfg_path, redis)
    return {"users": data}
