import os
import datetime as _dt
from typing import Any, Dict, List, Optional

from redis import Redis


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """Return a cached Redis client using ``REDIS_URL``."""
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        _redis_client = Redis.from_url(url, decode_responses=True)
    return _redis_client


def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat()


def _today() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%d")


def _ts_ms() -> int:
    return int(_dt.datetime.utcnow().timestamp() * 1000)


# ---------------------------------------------------------------------------
# Visitor storage
# ---------------------------------------------------------------------------

VIS_ID_SEQ = "vms26:ids:visitor"
VIS_HASH = "vms26:vis:{id}"
VIS_ALL = "vms26:index:vis:all"


def create_visitor(data: Dict[str, Any]) -> int:
    r = get_redis()
    vid = r.incr(VIS_ID_SEQ)
    now = _now_iso()
    key = VIS_HASH.format(id=vid)
    fields = {
        "full_name": data.get("full_name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "org": data.get("org", ""),
        "gov_id": data.get("gov_id", ""),
        "created_at": now,
        "updated_at": now,
        "deleted_at": "",
    }
    r.hset(key, mapping=fields)
    r.sadd(VIS_ALL, vid)
    # optional event
    try:
        r.xadd(
            "vms26:events",
            {
                "ts_ms": _ts_ms(),
                "kind": "visitor_created",
                "visitor_id": vid,
            },
        )
    except Exception:
        pass
    return vid


def list_visitors(query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    r = get_redis()
    ids = r.smembers(VIS_ALL)
    results: List[Dict[str, Any]] = []
    query = query or {}
    name_filter = (query.get("full_name") or "").lower()
    phone_filter = query.get("phone") or ""
    for vid in ids:
        data = r.hgetall(VIS_HASH.format(id=vid))
        if not data or data.get("deleted_at"):
            continue
        if name_filter and name_filter not in data.get("full_name", "").lower():
            continue
        if phone_filter and phone_filter != data.get("phone", ""):
            continue
        data["id"] = int(vid)
        results.append(data)
    return results


def soft_delete_visitor(vid: int) -> None:
    r = get_redis()
    now = _now_iso()
    key = VIS_HASH.format(id=vid)
    r.hset(key, "deleted_at", now)
    r.srem(VIS_ALL, vid)
    try:
        r.xadd(
            "vms26:events",
            {"ts_ms": _ts_ms(), "kind": "visitor_deleted", "visitor_id": vid},
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Gate pass storage
# ---------------------------------------------------------------------------

GP_ID_SEQ = "vms26:ids:gpass"
GP_HASH = "vms26:gpass:{id}"
GP_ALL = "vms26:index:gpass:all"
GP_BYDATE = "vms26:index:gpass:bydate:{date}"
GP_LOCK = "vms26:lock:gpass:{visitor_id}:{date}"


def create_gate_pass(
    visitor_id: int, host_name: str, purpose: str, visit_date: str
) -> int:
    r = get_redis()
    gpid = r.incr(GP_ID_SEQ)
    now = _now_iso()
    key = GP_HASH.format(id=gpid)
    fields = {
        "visitor_id": str(visitor_id),
        "host_name": host_name,
        "purpose": purpose,
        "visit_date": visit_date,
        "status": "draft",
        "qr_data": "",
        "photo_path": "",
        "printed_at": "",
        "created_at": now,
        "updated_at": now,
        "deleted_at": "",
    }
    r.hset(key, mapping=fields)
    r.sadd(GP_ALL, gpid)
    r.sadd(GP_BYDATE.format(date=visit_date), gpid)
    try:
        r.xadd(
            "vms26:events",
            {
                "ts_ms": _ts_ms(),
                "kind": "gpass_created",
                "gate_pass_id": gpid,
                "visitor_id": visitor_id,
            },
        )
    except Exception:
        pass
    return gpid


def get_gate_pass(gpid: int) -> Dict[str, Any]:
    r = get_redis()
    data = r.hgetall(GP_HASH.format(id=gpid))
    if data:
        data["id"] = int(gpid)
    return data


def approve_gate_pass(gpid: int) -> Dict[str, Any]:
    r = get_redis()
    key = GP_HASH.format(id=gpid)
    data = r.hgetall(key)
    if not data:
        raise ValueError("not_found")
    if data.get("status") in {"approved", "printed"}:
        raise RuntimeError("already_active")
    visitor_id = data.get("visitor_id")
    visit_date = data.get("visit_date")
    lock_key = GP_LOCK.format(visitor_id=visitor_id, date=visit_date)
    ok = r.set(lock_key, gpid, nx=True)
    if not ok:
        existing = r.get(lock_key)
        if existing and str(existing) != str(gpid):
            raise RuntimeError("active_exists")
    qr_data = f"GP:{gpid}:{visitor_id}:{visit_date}"
    now = _now_iso()
    r.hset(key, mapping={"status": "approved", "qr_data": qr_data, "updated_at": now})
    try:
        r.xadd(
            "vms26:events",
            {
                "ts_ms": _ts_ms(),
                "kind": "gpass_approved",
                "gate_pass_id": gpid,
                "visitor_id": visitor_id,
            },
        )
    except Exception:
        pass
    return {"qr_data": qr_data, "status": "approved"}


def mark_printed(gpid: int) -> Dict[str, Any]:
    r = get_redis()
    key = GP_HASH.format(id=gpid)
    now = _now_iso()
    r.hset(key, mapping={"status": "printed", "printed_at": now, "updated_at": now})
    try:
        r.xadd(
            "vms26:events",
            {
                "ts_ms": _ts_ms(),
                "kind": "gpass_printed",
                "gate_pass_id": gpid,
            },
        )
    except Exception:
        pass
    return {"status": "printed", "printed_at": now}


def soft_delete_gate_pass(gpid: int) -> None:
    r = get_redis()
    key = GP_HASH.format(id=gpid)
    data = r.hgetall(key)
    if not data:
        return
    now = _now_iso()
    r.hset(key, "deleted_at", now)
    r.srem(GP_ALL, gpid)
    r.srem(GP_BYDATE.format(date=data.get("visit_date")), gpid)
    status = data.get("status")
    if status in {"approved", "printed"}:
        lock_key = GP_LOCK.format(
            visitor_id=data.get("visitor_id"), date=data.get("visit_date")
        )
        if r.get(lock_key) == str(gpid):
            r.delete(lock_key)
    try:
        r.xadd(
            "vms26:events",
            {
                "ts_ms": _ts_ms(),
                "kind": "gpass_deleted",
                "gate_pass_id": gpid,
                "visitor_id": data.get("visitor_id"),
            },
        )
    except Exception:
        pass


def list_gate_passes(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    r = get_redis()
    filters = filters or {}
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    ids: set = set()
    if date_from or date_to:
        start = _dt.datetime.strptime(date_from or date_to, "%Y-%m-%d")
        end = _dt.datetime.strptime(date_to or date_from, "%Y-%m-%d")
        step = _dt.timedelta(days=1)
        cur = start
        while cur <= end:
            ids.update(
                r.smembers(GP_BYDATE.format(date=cur.strftime("%Y-%m-%d")))
            )
            cur += step
    else:
        ids = set(r.smembers(GP_ALL))
    results: List[Dict[str, Any]] = []
    status_f = filters.get("status")
    visitor_f = filters.get("visitor_id")
    for gid in ids:
        data = r.hgetall(GP_HASH.format(id=gid))
        if not data or data.get("deleted_at"):
            continue
        if status_f and data.get("status") != status_f:
            continue
        if visitor_f and data.get("visitor_id") != str(visitor_f):
            continue
        vdate = data.get("visit_date")
        if date_from and vdate < date_from:
            continue
        if date_to and vdate > date_to:
            continue
        data["id"] = int(gid)
        results.append(data)
    return results


__all__ = [
    "get_redis",
    "create_visitor",
    "list_visitors",
    "soft_delete_visitor",
    "create_gate_pass",
    "approve_gate_pass",
    "mark_printed",
    "soft_delete_gate_pass",
    "list_gate_passes",
    "get_gate_pass",
]
