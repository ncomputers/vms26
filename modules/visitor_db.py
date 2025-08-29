"""Redis-backed helpers for visitor and host records."""

from __future__ import annotations

import json
import time
from itertools import islice
from typing import Dict, Iterator, Optional

import redis
from loguru import logger

from utils.ids import generate_id


class VisitorDB:
    """Lightweight wrapper around Redis for visitor lookups."""

    def __init__(self, client: redis.Redis):
        self.client = client

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_map(data: Dict) -> Dict:
        return {
            k.decode() if isinstance(k, bytes) else k: (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }

    def _fetch_visitor_record(self, phone: str) -> Dict[str, str]:
        if not phone:
            return {}
        try:
            data = self.client.hgetall(f"visitor:record:{phone}")
        except Exception as exc:
            logger.exception("failed to fetch visitor {}: {}", phone, exc)
            return {}
        return self._decode_map(data) if data else {}

    def _update_name_index(self, name: str, phone: str) -> None:
        if not name:
            return
        member = f"{name.lower()}|{phone}"
        ts = time.time()
        self.client.zadd("visitor_name_idx", {member: ts})

    def _iter_name_index(self, prefix_l: str, seen: set[tuple[str, str]]) -> Iterator[dict]:
        pattern = f"{prefix_l}*"
        for member, _score in self.client.zscan_iter("visitor_name_idx", match=pattern, count=50):
            mstr = member.decode() if isinstance(member, bytes) else member
            try:
                name, phone = mstr.split("|", 1)
            except ValueError:
                name, phone = mstr, ""
            key = (name, phone)
            if key in seen:
                continue
            seen.add(key)
            info = self.get_visitor_by_phone(phone) or {}
            yield {
                "name": info.get("name", name),
                "phone": phone,
                "visitor_type": info.get("visitor_type", ""),
                "company": info.get("org", ""),
                "photo_url": info.get("photo", ""),
            }

    def _scan_logs(self, prefix_l: str, remaining: int, seen: set[tuple[str, str]]) -> list[dict]:
        try:
            entries = self.client.zrevrange("vms_logs", 0, -1)
        except Exception as exc:
            logger.exception("failed to scan visitor logs: {}", exc)
            return []
        results: list[dict] = []
        for e in entries:
            try:
                obj = json.loads(e if isinstance(e, str) else e.decode())
            except Exception:
                continue
            name = obj.get("name", "")
            if not name.lower().startswith(prefix_l):
                continue
            phone = obj.get("phone", "")
            key = (name, phone)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "name": name,
                    "phone": phone,
                    "visitor_type": obj.get("visitor_type", ""),
                    "company": obj.get("company_name", ""),
                    "photo_url": obj.get("photo_url", ""),
                }
            )
            if len(results) >= remaining:
                break
        return results

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def save_visitor(
        self,
        name: str,
        phone: str,
        email: str = "",
        org: str = "",
        photo: str = "",
        visitor_id: str | None = None,
    ) -> str:
        if not phone:
            raise ValueError("phone missing")
        try:
            existing = self._fetch_visitor_record(phone)
            vid = visitor_id or existing.get("id") or generate_id()
            mapping = {
                "id": vid,
                "name": name,
                "email": email,
                "org": org,
                "photo": photo,
            }
            self.client.hset(f"visitor:record:{phone}", mapping=mapping)
            try:
                self._update_name_index(name, phone)
            except Exception:
                pass
            return vid
        except Exception as exc:
            logger.exception("failed to save visitor {}: {}", phone, exc)
            raise RuntimeError("failed to save visitor") from exc

    def save_host(self, name: str, email: str = "", dept: str = "", location: str = "") -> None:
        if not name:
            raise ValueError("name missing")
        try:
            mapping = {"email": email, "dept": dept, "location": location}
            self.client.hset(f"visitor:host:{name}", mapping=mapping)
        except Exception as exc:
            logger.exception("failed to save host {}: {}", name, exc)
            raise RuntimeError("failed to save host") from exc

    def get_or_create_visitor(
        self, name: str, phone: str, email: str = "", org: str = "", photo: str = ""
    ) -> str:
        if not phone:
            return ""
        info = self._fetch_visitor_record(phone)
        vid = info.get("id")
        if vid:
            if name or email or org or photo:
                mapping = {
                    "name": name or info.get("name", ""),
                    "email": email or info.get("email", ""),
                    "org": org or info.get("org", ""),
                    "photo": photo or info.get("photo", ""),
                    "id": vid,
                }
                self.client.hset(f"visitor:record:{phone}", mapping=mapping)
            return vid
        vid = generate_id()
        mapping = {
            "id": vid,
            "name": name,
            "email": email,
            "org": org,
            "photo": photo,
        }
        self.client.hset(f"visitor:record:{phone}", mapping=mapping)
        try:
            self._update_name_index(name, phone)
        except Exception:
            pass
        return vid

    def get_visitor_by_phone(self, phone: str) -> Optional[Dict[str, str]]:
        if not phone:
            return None
        info = self._fetch_visitor_record(phone)
        if not info:
            return None
        return {
            "id": info.get("id", ""),
            "name": info.get("name", ""),
            "email": info.get("email", ""),
            "org": info.get("org", ""),
            "photo": info.get("photo", ""),
        }

    def get_host(self, name: str) -> Optional[Dict[str, str]]:
        if not name:
            return None
        try:
            data = self.client.hgetall(f"visitor:host:{name}")
        except Exception as exc:
            logger.exception("failed to fetch host {}: {}", name, exc)
            return None
        if not data:
            return None
        info = self._decode_map(data)
        return {
            "email": info.get("email", ""),
            "dept": info.get("dept", ""),
            "location": info.get("location", ""),
        }

    def search_visitors_by_name(self, prefix: str, limit: int = 5) -> list[dict]:
        if not prefix:
            return []
        prefix_l = prefix.lower()
        seen: set[tuple[str, str]] = set()
        results = list(islice(self._iter_name_index(prefix_l, seen), limit))
        if len(results) == limit:
            return results
        results.extend(self._scan_logs(prefix_l, limit - len(results), seen))
        return results


# ------------------------------------------------------------------
# compatibility wrappers
# ------------------------------------------------------------------
_db: VisitorDB | None = None


def init_db(redis_client: redis.Redis) -> None:
    """Initialise the shared :class:`VisitorDB` instance."""

    global _db
    _db = VisitorDB(redis_client)


def _require_db() -> VisitorDB:
    if _db is None:
        raise ValueError("Redis not initialized")
    return _db


def save_visitor(*args, **kwargs):
    return _require_db().save_visitor(*args, **kwargs)


def save_host(*args, **kwargs):
    return _require_db().save_host(*args, **kwargs)


def get_or_create_visitor(*args, **kwargs):
    return _require_db().get_or_create_visitor(*args, **kwargs)


def get_visitor_by_phone(*args, **kwargs):
    return _require_db().get_visitor_by_phone(*args, **kwargs)


def get_host(*args, **kwargs):
    return _require_db().get_host(*args, **kwargs)


def search_visitors_by_name(*args, **kwargs):
    return _require_db().search_visitors_by_name(*args, **kwargs)


__all__ = [
    "VisitorDB",
    "init_db",
    "save_visitor",
    "save_host",
    "get_or_create_visitor",
    "get_visitor_by_phone",
    "get_host",
    "search_visitors_by_name",
]
