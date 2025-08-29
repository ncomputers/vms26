from __future__ import annotations

"""Camera diagnostics helper for stream inspection."""

import asyncio
import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, List
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import StreamingResponse

from diagnostics.registry import list_tests
from modules import troubleshooter_runner as ts_runner
from modules.stream_probe import check_rtsp
from utils.deps import get_cameras, get_templates

router = APIRouter()
redisfx = None


def ok(step: str, detail: str) -> Dict[str, Any]:
    return {"step": step, "ok": True, "detail": detail}


def fail(step: str, detail: str, hints: Any = None) -> Dict[str, Any]:
    res: Dict[str, Any] = {"step": step, "ok": False, "detail": detail}
    if hints:
        res["hints"] = hints
    return res


def skipped(step: str, detail: str) -> Dict[str, Any]:
    return {"step": step, "ok": None, "detail": detail}


def _get_camera_mode(cam: Dict[str, Any]) -> str:
    mode = (cam.get("mode") or cam.get("type") or "").lower()
    if mode == "http":
        mode = "mjpeg"
    if mode not in {"rtsp", "mjpeg", "local", "screen"}:
        url = cam.get("url", "")
        if url.startswith("rtsp://"):
            mode = "rtsp"
        elif url.startswith("http://") or url.startswith("https://"):
            mode = "mjpeg"
        elif url:
            mode = "local"
        else:
            mode = "screen"
    return mode


async def get_last_frame_age_sec(cam_id: int) -> float | None:
    if redisfx is None:
        return None
    try:
        ts = await redisfx.get(f"camera:{cam_id}:last_frame_ts")
        if not ts:
            return None
        return time.time() - float(ts)
    except Exception:
        return None


@router.get("/troubleshooter", response_class=HTMLResponse)
async def troubleshooter_page(
    request: Request,
    templates: Jinja2Templates = Depends(get_templates),
    cameras: List[dict] = Depends(get_cameras),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "troubleshooter.html", {"request": request, "cameras": cameras}
    )


async def _ping(host: str) -> bool:
    if not host:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


@router.get("/api/troubleshooter/tests")
async def troubleshooter_tests() -> Dict[str, Any]:
    """Return available diagnostic tests and capability flags."""

    tests = list(list_tests().keys())
    return {"tests": tests, "capabilities": {"sse": True}}


async def _execute_test(name: str, fn, cam_id: int) -> Dict[str, Any]:
    task = asyncio.create_task(fn(cam_id)) if fn else None
    try:
        if task is None:
            raise RuntimeError("unknown_test")
        return await asyncio.wait_for(task, timeout=5)
    except asyncio.TimeoutError:
        return {
            "id": name,
            "status": "fail",
            "reason": "timeout",
            "detail": "",
            "suggestion": "",
            "duration_ms": 5000,
        }
    except Exception as exc:
        return {
            "id": name,
            "status": "fail",
            "reason": str(exc),
            "detail": "",
            "suggestion": "",
            "duration_ms": 0,
        }


async def _run_tests(cam_id: int, tests: List[str] | None) -> Dict[str, Any]:
    registry = list_tests()
    selected = tests or list(registry.keys())
    run_id = uuid.uuid4().hex
    results: List[Dict[str, Any]] = []
    for name in selected:
        fn = registry.get(name)
        res = await _execute_test(name, fn, cam_id)
        results.append(res)
    return {"run_id": run_id, "results": results}


@router.post("/api/troubleshooter/run")
async def troubleshooter_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    cam_id = int(payload.get("camera_id", 0))
    tests = payload.get("tests")
    return await _run_tests(cam_id, tests)


async def run_tests_event_source(cam_id: int, tests: List[str] | None) -> AsyncIterator[str]:
    registry = list_tests()
    selected = tests or list(registry.keys())
    run_id = uuid.uuid4().hex
    results: List[Dict[str, Any]] = []
    for name in selected:
        fn = registry.get(name)
        res = await _execute_test(name, fn, cam_id)
        results.append(res)
        payload = json.dumps({"run_id": run_id, "result": res, "results": list(results)})
        yield f"event: test_result\ndata: {payload}\n\n"
    final = json.dumps({"run_id": run_id, "results": results})
    yield f"event: run_complete\ndata: {final}\n\n"


@router.get("/api/troubleshooter/run_sse")
async def troubleshooter_run_sse(
    camera_id: int = Query(...),
    tests: str | None = Query(None),
) -> StreamingResponse:
    selected = tests.split(",") if tests else None
    return StreamingResponse(
        run_tests_event_source(camera_id, selected),
        media_type="text/event-stream",
    )


@router.get("/troubleshooter/start")
async def troubleshooter_start(
    camera_id: int = Query(...),
    cameras: List[dict] = Depends(get_cameras),
) -> Dict[str, Any]:
    cam = next((c for c in cameras if c.get("id") == camera_id), None)
    if cam is None:
        return {"error": "camera_not_found"}
    run_id = ts_runner.start_run(cam)
    return {"run_id": run_id}


async def _stream_run(run_id: str) -> AsyncIterator[str]:
    queue = ts_runner.get_queue(run_id)
    if queue is None:
        yield "data: {}\n\n"
        return
    loop = asyncio.get_running_loop()
    while True:
        msg = await loop.run_in_executor(None, queue.get)
        payload = json.dumps(msg)
        yield f"data: {payload}\n\n"
        if msg.get("stage") == "complete":
            ts_runner.cleanup(run_id)
            break


@router.get("/troubleshooter/stream")
async def troubleshooter_stream(run_id: str = Query(...)) -> StreamingResponse:
    return StreamingResponse(_stream_run(run_id), media_type="text/event-stream")


@router.get("/api/troubleshooter/{cam_id}")
async def troubleshooter_api(
    cam_id: int, cameras: List[dict] = Depends(get_cameras)
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    cam = next((c for c in cameras if c.get("id") == cam_id), None)
    if cam is None:
        results.append(fail("camera", "not found"))
        return results
    results.append(ok("camera", "found"))

    mode = _get_camera_mode(cam)
    results.append(ok("open", mode))

    uri = cam.get("url", "")
    host = urlparse(uri).hostname or ""

    try:
        ping_ok = await _ping(host)
    except Exception:
        ping_ok = False
    results.append(
        fail("ping", "timeout", ["check network cables"]) if not ping_ok else ok("ping", "reply")
    )

    if mode == "rtsp":
        try:
            info = await asyncio.to_thread(check_rtsp, uri)
            results.append(
                fail("rtsp", info.get("error") or "error", info.get("hints"))
                if not info.get("ok")
                else ok("rtsp", "ok")
            )
        except Exception as exc:
            results.append(fail("rtsp", str(exc)))
    else:
        results.append(skipped("rtsp", f"active source: {mode}"))

    if mode == "mjpeg":
        try:
            url = f"http://localhost/api/cameras/{cam_id}/mjpeg"
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
            ok_status = resp.status_code == 200
            results.append(
                ok("mjpeg", str(resp.status_code))
                if ok_status
                else fail("mjpeg", str(resp.status_code))
            )
        except Exception as exc:
            results.append(fail("mjpeg", str(exc)))
    else:
        results.append(skipped("mjpeg", f"active source: {mode}"))

    age = await get_last_frame_age_sec(cam_id)
    if age is None:
        results.append(fail("stream", "no frame"))
    elif age < 3:
        results.append(ok("stream", f"fresh frame ({age:.1f}s)"))
    else:
        results.append(fail("stream", f"stale frame ({age:.1f}s)"))

    return results


# init_context routine
def init_context(
    cfg: dict,
    trackers,
    cams,
    templates_path: str,
    redis_facade=None,
) -> None:  # pragma: no cover - simple
    global redisfx
    redisfx = redis_facade
    """Initialize module-level state.

    The troubleshooter router does not currently require any of the provided
    context objects, but the initialization hook is expected by the
    application startup sequence. Defining this no-op function allows the
    server to import and register the router without raising an AttributeError
    during startup.
    """
    return None
