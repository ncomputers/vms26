#!/usr/bin/env python3
"""Quick environment health check for common dependencies."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from redis import Redis
from redis.exceptions import RedisError

GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def _fmt(ok: bool) -> str:
    color = GREEN if ok else YELLOW
    label = "OK" if ok else "WARN"
    return f"{color}{label}{RESET}"


def _print(name: str, ok: bool, msg: str) -> None:
    print(f"{_fmt(ok)} {name}: {msg}")


def _parse_env() -> Tuple[bool, str, dict[str, Any]]:
    path = os.getenv("CONFIG_PATH", "config.json")
    try:
        from config.storage import load_config

        cfg = load_config(path, None, minimal=True)
        return True, path, cfg
    except Exception as exc:  # pragma: no cover - info only
        return False, str(exc), {}


def _check_redis(url: str) -> Tuple[bool, str, int | None]:
    try:
        client = Redis.from_url(url, decode_responses=True)
        client.ping()
        raw = client.get("cameras") or client.hget("cameras", "data")
        count = len(json.loads(raw)) if raw else 0
        return True, url, count
    except (RedisError, OSError, ValueError) as exc:  # pragma: no cover - info only
        return False, str(exc), None


def _check_cuda() -> Tuple[bool, str]:
    try:
        import torch

        ok = torch.cuda.is_available()
        return ok, "available" if ok else "not available"
    except Exception as exc:  # pragma: no cover - info only
        return False, f"torch not usable: {exc}"


def _check_turbojpeg() -> Tuple[bool, str]:
    try:
        from turbojpeg import TurboJPEG  # noqa: F401

        return True, "present"
    except Exception as exc:  # pragma: no cover - info only
        return False, str(exc)


def main() -> int:
    env_ok, env_msg, cfg = _parse_env()
    _print("env", env_ok, env_msg)

    redis_url = cfg.get("redis_url") or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_ok, redis_msg, cam_count = _check_redis(redis_url)
    _print("redis", redis_ok, redis_msg)

    cuda_ok, cuda_msg = _check_cuda()
    _print("cuda", cuda_ok, cuda_msg)

    jpeg_ok, jpeg_msg = _check_turbojpeg()
    _print("turbojpeg", jpeg_ok, jpeg_msg)

    if cam_count is not None:
        _print("cameras", True, str(cam_count))
    else:
        _print("cameras", False, "unknown")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
