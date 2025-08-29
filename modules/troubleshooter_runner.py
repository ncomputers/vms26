from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Dict
from urllib.parse import urlparse

from loguru import logger

logger = logger.bind(module="troubleshooter")

# Map of active runs: run_id -> {"queue": mp.Queue, "process": mp.Process}
_RUNS: Dict[str, Dict[str, Any]] = {}


def _run_stage(name: str, func, queue: mp.Queue, timeout: float = 10.0) -> bool:
    start = time.time()
    status = "PASS"
    detail = ""

    def target() -> None:
        nonlocal status, detail
        try:
            func()
        except Exception as exc:  # pragma: no cover - defensive
            status = "FAIL"
            detail = str(exc)

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        status = "TIMEOUT"
        detail = f">{int(timeout * 1000)}ms"

    duration_ms = int((time.time() - start) * 1000)
    event = {
        "stage": name,
        "status": status,
        "duration_ms": duration_ms,
        "detail": detail,
    }
    logger.info(json.dumps(event))
    queue.put(event)
    return status == "PASS"


def _worker(url: str, queue: mp.Queue) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""

    def ping() -> None:
        if not host:
            raise RuntimeError("no_host")
        subprocess.run(
            [
                "ping",
                "-c",
                "1",
                "-W",
                "1",
                host,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=2,
        )

    def ffprobe() -> None:
        if shutil.which("ffprobe") is None:
            raise RuntimeError("ffprobe_missing")
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,r_frame_rate",
                "-of",
                "json",
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=5,
        )

    def decode() -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg_missing")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                url,
                "-frames:v",
                "30",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )

    def detector() -> None:
        time.sleep(0.1)

    def pipeline() -> None:
        secs = float(os.environ.get("TROUBLESHOOTER_DRY_RUN_SECS", "5"))
        time.sleep(secs)

    stages = [
        ("ping", ping),
        ("ffprobe", ffprobe),
        ("decode", decode),
        ("detector", detector),
        ("pipeline", pipeline),
    ]

    for name, fn in stages:
        ok = _run_stage(name, fn, queue)
        if not ok:
            break

    queue.put({"stage": "complete"})


def start_run(camera: Dict[str, Any]) -> str:
    """Start troubleshooter diagnostics in a subprocess and return run_id."""
    run_id = uuid.uuid4().hex
    q: mp.Queue = mp.Queue()
    p = mp.Process(target=_worker, args=(camera.get("url", ""), q))
    p.start()
    _RUNS[run_id] = {"queue": q, "process": p}
    return run_id


def get_queue(run_id: str) -> mp.Queue | None:
    info = _RUNS.get(run_id)
    return info.get("queue") if info else None


def cleanup(run_id: str) -> None:
    info = _RUNS.pop(run_id, None)
    if not info:
        return
    proc: mp.Process = info.get("process")
    if proc and proc.is_alive():
        proc.join(timeout=0.1)
