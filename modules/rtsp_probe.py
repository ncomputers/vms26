from __future__ import annotations

import subprocess
from typing import Optional

CANDIDATES = [
    "/Streaming/Channels/101",
    "/cam/realmonitor?channel=1&subtype=0",
    "/live",
    "/stream1",
]


def _check(url: str) -> bool:
    cmd = [
        "ffprobe",
        "-rtsp_transport",
        "tcp",
        "-stimeout",
        "2000000",
        "-v",
        "error",
        "-show_streams",
        url,
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def probe_rtsp_base(host: str, user: Optional[str] = None, password: Optional[str] = None) -> str:
    """Return first working RTSP URL built from ``host`` and ``CANDIDATES``.

    ``host`` may include a port. Credentials are optional.
    """
    auth = ""
    if user:
        auth = f"{user}:{password or ''}@"
    base = f"rtsp://{auth}{host}"
    for path in CANDIDATES:
        url = base + path
        if _check(url):
            return url
    raise RuntimeError("No RTSP stream found")
