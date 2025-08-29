from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from urllib.parse import urlparse

from app.core.utils import now_ms
from utils.gpu import probe_cuda
from utils.redis import get_client

from .registry import app_config, get_source_mode, register


async def _wrap(test_id: str, fn, suggestion_default: str = "") -> Dict[str, Any]:
    start = now_ms()
    try:
        status, reason, detail, suggestion = await asyncio.wait_for(fn(), timeout=5)
        if not suggestion:
            suggestion = suggestion_default
    except asyncio.TimeoutError:
        status, reason, detail, suggestion = "fail", "timeout", "", suggestion_default
    except Exception as exc:  # pragma: no cover - best effort
        status, reason, detail, suggestion = "fail", str(exc), "", suggestion_default
    return {
        "id": test_id,
        "status": status,
        "reason": reason,
        "detail": detail,
        "suggestion": suggestion,
        "duration_ms": now_ms() - start,
    }


async def _redis_client():
    try:
        return await get_client()
    except Exception:  # pragma: no cover - allow diagnostics without Redis
        return None


@register("camera_found")
async def camera_found(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        mode = get_source_mode(cam_id)
        if not mode:
            return "fail", "not_found", "", "configure camera"  # no camera
        return "ok", "", f"mode:{mode}", ""

    return await _wrap("camera_found", inner, "ensure camera is configured")


@register("ping")
async def ping(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        cams = app_config.get("cameras") or []
        url = ""
        for cam in cams:
            if cam.get("id") == cam_id:
                url = cam.get("url", "")
                break
        host = urlparse(url).hostname or ""
        if not host:
            return "fail", "no_host", "", "verify camera URL"
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            return "fail", "unreachable", "", "check network connectivity"
        rtt = 0.0
        for line in out.decode().splitlines():
            if "time=" in line:
                try:
                    rtt = float(line.split("time=")[1].split()[0])
                except Exception:
                    rtt = 0.0
                break
        return "ok", "", f"rtt_ms:{rtt:.2f}", ""

    return await _wrap("ping", inner, "ensure host reachable")


@register("rtsp_probe")
async def rtsp_probe(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    mode = get_source_mode(cam_id)
    if not mode.startswith("rtsp"):
        return {
            "id": "rtsp_probe",
            "status": "skip",
            "reason": mode,
            "detail": "",
            "suggestion": "",
            "duration_ms": 0,
        }

    async def inner():
        cams = app_config.get("cameras") or []
        url = ""
        for cam in cams:
            if cam.get("id") == cam_id:
                url = cam.get("url", "")
                break
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 554
        if not host:
            return "fail", "no_host", "", "verify RTSP URL"
        t0 = time.perf_counter()
        reader = writer = None
        try:
            reader, writer = await asyncio.open_connection(host, port)
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
        ms = (time.perf_counter() - t0) * 1000
        return "ok", "", f"connect_ms:{ms:.1f}", ""

    return await _wrap("rtsp_probe", inner, "check RTSP service")


@register("mjpeg_probe")
async def mjpeg_probe(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    mode = get_source_mode(cam_id)
    if mode != "mjpeg":
        return {
            "id": "mjpeg_probe",
            "status": "skip",
            "reason": mode,
            "detail": "",
            "suggestion": "",
            "duration_ms": 0,
        }

    async def inner():
        cams = app_config.get("cameras") or []
        url = ""
        for cam in cams:
            if cam.get("id") == cam_id:
                url = cam.get("url", "")
                break
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if not host:
            return "fail", "no_host", "", "verify MJPEG URL"
        reader = writer = None
        t0 = time.perf_counter()
        try:
            reader, writer = await asyncio.open_connection(host, port)
            request = f"HEAD {path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            await reader.read(64)
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
        ms = (time.perf_counter() - t0) * 1000
        return "ok", "", f"connect_ms:{ms:.1f}", ""

    return await _wrap("mjpeg_probe", inner, "check HTTP service")


@register("snapshot_fresh")
async def snapshot_fresh(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    mode = get_source_mode(cam_id)
    if mode == "screen":
        return {
            "id": "snapshot_fresh",
            "status": "skip",
            "reason": mode,
            "detail": "",
            "suggestion": "",
            "duration_ms": 0,
        }

    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        key = f"cam:{cam_id}:last_frame_ts"
        ts = await redis.get(key)
        if not ts:
            return "fail", "missing", "", "ensure stream running"
        age = int(time.time()) - int(ts)
        return (
            ("ok" if age < 10 else "fail"),
            "",
            f"age_s:{age}",
            "restart camera" if age >= 10 else "",
        )

    return await _wrap("snapshot_fresh", inner, "verify frame ingestion")


@register("stream_metrics")
async def stream_metrics(cam_id: int, *_: Any, **__: Any) -> Dict[str, Any]:
    mode = get_source_mode(cam_id)
    if mode == "screen":
        return {
            "id": "stream_metrics",
            "status": "skip",
            "reason": mode,
            "detail": "",
            "suggestion": "",
            "duration_ms": 0,
        }

    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        metrics = await redis.hgetall(f"cam:{cam_id}:stream")
        if not metrics:
            return "fail", "missing", "", "check streaming pipeline"
        fps = metrics.get("fps", "0")
        jitter = metrics.get("jitter", "0")
        return "ok", "", f"fps:{fps} jitter:{jitter}", ""

    return await _wrap("stream_metrics", inner, "inspect stream quality")


@register("detector_warm")
async def detector_warm(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        val = await redis.get("detector:warm")
        if val in {"1", "true", "warm"}:
            return "ok", "", "warm", ""
        return "fail", "cold", "", "preload detector"

    return await _wrap("detector_warm", inner, "warm up detector")


@register("inference_latency")
async def inference_latency(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        latencies = await redis.lrange("inference:latency", -5, -1)
        if not latencies:
            return "fail", "missing", "", "collect latency metrics"
        vals = [float(x) for x in latencies]
        avg = sum(vals) / len(vals)
        return "ok", "", f"avg_ms:{avg:.1f}", ""

    return await _wrap("inference_latency", inner, "monitor inference")


@register("queues_depth")
async def queues_depth(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        visitor_depth = await redis.llen("visitor_queue")
        capture_depth = await redis.llen("capture_queue")
        detail = f"visitor:{visitor_depth} capture:{capture_depth}"
        return "ok", "", detail, ""

    return await _wrap("queues_depth", inner, "drain queues if necessary")


@register("redis_rtt")
async def redis_rtt(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        t0 = time.perf_counter()
        await redis.ping()
        ms = (time.perf_counter() - t0) * 1000
        return "ok", "", f"rtt_ms:{ms:.1f}", ""

    return await _wrap("redis_rtt", inner, "check Redis connectivity")


@register("gpu_stats")
async def gpu_stats(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        has_cuda, count, err = probe_cuda()
        if has_cuda:
            return "ok", "", f"devices:{count}", ""
        reason = err or "unavailable"
        return "fail", reason, "", "verify GPU drivers"

    return await _wrap("gpu_stats", inner, "ensure CUDA installed")


@register("report_consistency")
async def report_consistency(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        redis = await _redis_client()
        if redis is None:
            return "fail", "no_redis", "", "start Redis"
        generated = await redis.get("reports:generated")
        stored = await redis.get("reports:stored")
        if generated is None or stored is None:
            return "fail", "missing", "", "track report counters"
        if generated == stored:
            return "ok", "", f"count:{generated}", ""
        return "fail", "mismatch", f"generated:{generated} stored:{stored}", "reconcile reports"

    return await _wrap("report_consistency", inner, "verify reporting pipeline")


@register("license_limits")
async def license_limits(*_: Any, **__: Any) -> Dict[str, Any]:
    async def inner():
        lic = app_config.get("license") or {}
        max_cams = int(lic.get("max_cameras", 0))
        cams = app_config.get("cameras") or []
        count = len(cams)
        if max_cams and count > max_cams:
            detail = f"cameras:{count}/{max_cams}"
            return "fail", "limit_exceeded", detail, "upgrade license"
        return "ok", "", f"cameras:{count}/{max_cams or 'unlimited'}", ""

    return await _wrap("license_limits", inner, "check license configuration")
