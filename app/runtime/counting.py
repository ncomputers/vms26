"""Simplified counting helpers.

The real implementation lives elsewhere; this placeholder allows the runtime
pipeline to call :func:`count_update` during development and tests.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Tuple


def count_update(
    state: Any, tracks: Iterable[Any], line_cfg: Any
) -> Tuple[Any, List[Any]]:
    """Update counting ``state`` based on ``tracks``.

    Parameters are intentionally generic as the concrete structures depend on
    the production counting logic.  This placeholder simply returns the state
    unchanged and emits no events.
    """

    return state, []
