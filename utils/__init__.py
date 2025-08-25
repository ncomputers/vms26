"""Utility package initialization and public exports."""

from .license_guard import require_feature
from .redis_facade import RedisFacade, make_facade_from_url

__all__ = ["require_feature", "RedisFacade", "make_facade_from_url"]
