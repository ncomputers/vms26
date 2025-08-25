from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from loguru import logger

LICENSE_PATH = Path("data/config/license.json")


def get() -> Dict[str, Any] | None:
    """Return persisted license data if available."""
    try:
        with LICENSE_PATH.open() as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read license file: {}", exc)
        return None


def set(data: Dict[str, Any]) -> None:
    """Persist license ``data`` to disk."""
    try:
        LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LICENSE_PATH.open("w") as f:
            json.dump(data, f)
    except OSError as exc:
        logger.warning("Failed to write license file: {}", exc)
