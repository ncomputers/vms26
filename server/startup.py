from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from loguru import logger
from redis import Redis
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import load_branding, load_config, save_config
from config.license_storage import get as load_license
from config.license_storage import set as save_license
from core.tracker_manager import count_log_loop
from logging_config import LOG_LEVEL, set_log_level, setup_json_logger
from modules.license import verify_license
from modules.profiler import profiler_manager
from modules.rtsp_client import choose_url, ffmpeg_input_args
from modules.tracker import PersonTracker
from routers import blueprints
from routers.health import monitor_readiness
from startup import start_background_workers
from utils import logx
from utils.cpu import apply_thread_limits
from utils.gpu import configure_onnxruntime
from utils.gstreamer import probe_gstreamer
from utils.preflight import DependencyError, check_dependencies
from utils.redis_facade import make_facade_from_url

from .config import _apply_license, _connect_redis, _load_camera_profiles, _read_initial_config
from .hardware import _early_cpu_setup

setup_json_logger()
logger = logger.bind(module="startup")

# perform CPU setup before heavy imports
_early_cpu_setup()

try:  # pragma: no cover - OpenCV is optional
    import cv2  # type: ignore  # noqa: F401,E402
except Exception:  # pragma: no cover - dependency may be missing
    cv2 = None  # type: ignore[assignment]
from fastapi.templating import Jinja2Templates  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"


def _stop_worker(name: str, worker: object, stop_fn: Callable[[object], None]) -> None:
    """Stop a worker with standard logging and join support."""
    logger.info("Stopping {}", name)
    try:
        stop_fn(worker)
        if hasattr(worker, "join"):
            worker.join(timeout=2)
    finally:
        logger.info("{} stopped", name)


async def handle_unexpected_error(request: Request, exc: Exception):
    """Catch-all handler that logs the error and resets session state."""
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)

    logger.exception("Unhandled application error: {}", exc)

    session = request.scope.get("session")
    if isinstance(session, dict):
        session.clear()

    for attr in ("db", "db_session"):
        session = getattr(request.state, attr, None)
        if session and hasattr(session, "rollback"):
            with suppress(Exception):
                session.rollback()

    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


def silent_exception_handler(loop: asyncio.AbstractEventLoop, context: dict):
    exception = context.get("exception")
    if isinstance(exception, ConnectionResetError):
        logger.warning("\U0001f507 Suppressed harmless ConnectionResetError (WinError 10054)")
        return
    loop.default_exception_handler(context)


async def stop_all(app: FastAPI) -> None:
    """Signal all background threads to stop and wait for termination."""
    trackers = getattr(app.state, "trackers", {})
    ppe_worker = getattr(app.state, "ppe_worker", None)
    visitor_worker = getattr(app.state, "visitor_worker", None)
    alert_worker = getattr(app.state, "alert_worker", None)
    worker_tasks = getattr(app.state, "worker_tasks", [])

    logger.info("Stopping trackers")
    for tr in trackers.values():
        tr.running = False
    from core.tracker_manager import tracker_threads

    for cam_id, info in list(tracker_threads.items()):
        for name in ("capture", "process"):
            thread = info.get(name)
            if thread:
                logger.info(f"Waiting for tracker {cam_id} {name} thread")
                thread.join(timeout=2)
                logger.info(f"Tracker {cam_id} {name} thread stopped")

    if ppe_worker:
        _stop_worker("PPE worker", ppe_worker, lambda w: setattr(w, "running", False))

    if visitor_worker:
        _stop_worker("Visitor worker", visitor_worker, lambda w: w.stop())

    if alert_worker:
        _stop_worker("Alert worker", alert_worker, lambda w: w.stop())

    logger.info("Cancelling background tasks")
    worker_tasks = [t for t in worker_tasks if t]
    for task in worker_tasks:
        task.cancel()
    for task in worker_tasks:
        try:
            await task
            logger.info(f"Task {task.get_name() or id(task)} finished")
        except asyncio.CancelledError:
            logger.info(f"Task {task.get_name() or id(task)} cancelled")
        except (RuntimeError, OSError) as e:
            logger.exception(f"Task {task.get_name() or id(task)} error: {e}")

    from modules.profiler import profiler_manager

    profiler_manager.stop()
    logger.info("All workers stopped")


def init_app(
    app: FastAPI,
    config_path: str = "config.json",
    stream_url: str | None = None,
    workers: int | None = None,
) -> dict[str, Any]:
    """Configure application state and services."""
    config_path_local = config_path if os.path.isabs(config_path) else str(BASE_DIR / config_path)
    info = _read_initial_config(config_path_local)

    redis_url = info.get("redis_url")
    if not redis_url:
        logger.error("redis_url missing in configuration")
        raise SystemExit(1)
    temp_cfg = info["data"]
    redis_client_local: Redis = _connect_redis(redis_url)
    redis_fx = make_facade_from_url(redis_url)

    logger.info("Loading full configuration")
    try:
        cfg: dict[str, Any] = load_config(config_path_local, redis_client_local, data=temp_cfg)
    except (OSError, json.JSONDecodeError, RuntimeError) as e:
        logger.exception("Configuration load failed: {}", e)
        raise SystemExit(1) from e
    cfg["secret_key"] = os.getenv("CSRF_SECRET_KEY", cfg.get("secret_key", ""))

    set_log_level(cfg.get("log_level", LOG_LEVEL))
    probe_gstreamer(cfg)

    branding_path = str(Path(config_path_local).with_name("branding.json"))
    cfg["branding"] = load_branding(branding_path)
    persisted = load_license() or {}
    key = persisted.get("key") or cfg.get("license_key", "")
    license_info = verify_license(key)
    if license_info.get("valid"):
        cfg["license_key"] = key
        cfg = _apply_license(cfg, license_info)
        save_license({"key": key, "info": license_info})
    else:
        cfg = _apply_license(cfg, license_info)
        logger.warning("license not persisted / demo defaults applied")
        save_config(cfg, config_path_local, redis_client_local)
    redis_client_local.set("license_info", json.dumps(license_info))

    try:
        check_dependencies(cfg, BASE_DIR)
    except DependencyError as e:
        logger.error(str(e))
        raise SystemExit(1) from e

    configure_onnxruntime(cfg)

    from config import set_config

    set_config(cfg)

    backend = cfg.get("storage_backend", "redis")
    logger.info("using storage backend {}", backend)
    if backend != "redis":
        logger.error("unsupported storage backend: {}", backend)
        raise SystemExit(1)

    cams = _load_camera_profiles(redis_client_local, cfg, stream_url)

    trackers: dict[int, PersonTracker] = {}

    app.state.config = cfg
    app.state.config_path = config_path_local
    app.state.redis_client = redis_client_local
    app.state.redis_facade = redis_fx
    app.state.cameras = cams
    app.state.trackers = trackers
    app.state.ppe_worker = None
    app.state.visitor_worker = None
    app.state.alert_worker = None
    app.state.branding_path = branding_path
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.add_extension("jinja2.ext.do")
    app.state.templates = templates

    monitor_readiness(app)

    blueprints.init_all(
        cfg,
        trackers,
        cams,
        redis_client_local,
        str(TEMPLATE_DIR),
        config_path_local,
        branding_path,
        redis_fx,
    )
    blueprints.register_blueprints(app)
    apply_thread_limits(cfg, workers)

    return cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(silent_exception_handler)

    config_path = os.getenv("CONFIG_PATH", "config.json")
    stream_url = os.getenv("STREAM_URL")
    workers_env = os.getenv("WORKERS")
    workers = int(workers_env) if workers_env else None

    start_time = time.time()
    cfg = init_app(app, config_path=config_path, stream_url=stream_url, workers=workers)

    redis_client = app.state.redis_client
    cams = app.state.cameras
    trackers: dict[int, PersonTracker] = app.state.trackers

    base_url = os.getenv("CAM_RTSP_URL")
    if base_url:
        try:
            final_url = await choose_url(
                base_url,
                os.getenv("CAM_TRY_SUBSTREAM", "true").lower() == "true",
                int(os.getenv("CAM_HEALTHCHECK_TIMEOUT_MS", "4000")),
                int(os.getenv("CAM_MAX_RETRIES", "8")),
                int(os.getenv("CAM_BACKOFF_BASE_MS", "500")),
            )
        except RuntimeError as exc:
            logx.error("RTSP_FAILED", url=base_url, error=str(exc))
            raise SystemExit(1) from exc
        os.environ["FINAL_URL"] = final_url
        ff_args = ffmpeg_input_args(final_url)
        os.environ["FFMPEG_ARGS"] = " ".join(ff_args)
        logx.event("RTSP_READY", url=final_url)
    else:
        logx.warn("RTSP_DISABLED", reason="CAM_RTSP_URL not set")

    tasks = await start_background_workers(app, cfg, cams, trackers, redis_client)
    app.state.worker_tasks = tasks

    log_task = None
    if redis_client:
        log_task = asyncio.create_task(count_log_loop(redis_client, trackers))
    app.state.log_task = log_task

    logger.info("Starting profiler")
    try:
        profiler_manager.start(cfg)
        logger.info("Profiler started")
    except (RuntimeError, OSError) as e:
        logger.exception("Profiler start failed: {}", e)
        raise

    elapsed = time.time() - start_time
    features = ", ".join([k for k, v in cfg.get("features", {}).items() if v]) or "none"
    logger.info("Startup complete in {:.2f}s. Enabled features: {}", elapsed, features)

    try:
        yield
    finally:
        log_task = getattr(app.state, "log_task", None)
        if log_task:
            log_task.cancel()
            with suppress(asyncio.CancelledError):
                await log_task
        await stop_all(app)
