from __future__ import annotations

import asyncio
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from utils import logx


def percent_encode_auth(url: str) -> str:
    """Return *url* with username/password percent-encoded once."""

    parts = urlsplit(url)
    if parts.scheme.lower() != "rtsp":
        raise ValueError("URL must start with rtsp://")
    if not parts.username and not parts.password:
        return url
    username = quote(unquote(parts.username or ""), safe="")
    password = quote(unquote(parts.password or ""), safe="")
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    creds = username
    if username and parts.password is not None:
        creds += f":{password}"
    netloc = f"{creds}@{host}" if creds else host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


async def ffprobe_ok(url: str, timeout_ms: int) -> tuple[bool, str]:
    """Return ``(True, "")`` if ``ffprobe`` finds a video stream."""

    cmd = [
        "ffprobe",
        "-rtsp_transport",
        "tcp",
        "-rtsp_flags",
        "prefer_tcp",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "default=nw=1",
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout_ms / 1000)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return False, "timeout"
        if proc.returncode != 0:
            return False, err.decode().strip()
        if b"codec_type=video" not in out:
            return False, "no video stream"
        return True, ""
    except FileNotFoundError:
        return False, "ffprobe not found"
    except Exception as exc:  # pragma: no cover - unforeseen errors
        return False, str(exc)


async def choose_url(
    url: str,
    try_sub: bool,
    timeout_ms: int,
    retries: int,
    backoff_ms: int,
) -> str:
    """Return first healthy RTSP URL or raise ``RuntimeError`` after retries."""

    candidate = percent_encode_auth(url)
    last_err = "unreachable"
    for attempt in range(1, retries + 1):
        ok, err = await ffprobe_ok(candidate, timeout_ms)
        if ok:
            return candidate
        last_err = err or "ffprobe failed"
        if attempt == 1 and try_sub and "/Channels/101" in candidate:
            candidate = candidate.replace("/Channels/101", "/Channels/102")
            continue
        if attempt < retries:
            sleep = backoff_ms / 1000 * (2 ** (attempt - 1))
            logx.warn(
                "RTSP_RETRY",
                url=candidate,
                attempt=attempt,
                error=last_err,
                sleep_ms=int(sleep * 1000),
            )
            await asyncio.sleep(sleep)
    raise RuntimeError(last_err)


def ffmpeg_input_args(final_url: str) -> list[str]:
    """Return FFmpeg input arguments for ``final_url``."""

    return ["-rtsp_transport", "tcp", "-rtsp_flags", "prefer_tcp", "-i", final_url]
