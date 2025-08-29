"""Diagnostics helpers."""

from __future__ import annotations

import threading


def dump_threads() -> list[dict]:
    """Return details for all currently running threads."""
    return [
        {"name": t.name, "alive": t.is_alive(), "ident": t.ident} for t in threading.enumerate()
    ]


__all__ = ["dump_threads"]
