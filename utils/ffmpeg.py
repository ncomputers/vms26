from __future__ import annotations



def build_preview_cmd(url: str, transport: str, downscale: int | None = None) -> list[str]:
    """Return ffmpeg command for generating an MJPEG preview."""
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-rtsp_transport",
        transport,
        "-i",
        url,
        "-an",
    ]
    cmd += ["-flags", "low_delay", "-fflags", "nobuffer"]
    if downscale and downscale > 1:
        vf = f"scale=trunc(iw/{downscale}/2)*2:trunc(ih/{downscale}/2)*2"
        cmd += ["-vf", vf]
    cmd += [
        "-threads",
        "1",
        "-f",
        "mpjpeg",
        "-q:v",
        "5",
        "pipe:1",
    ]
    return cmd


def build_snapshot_cmd(url: str, transport: str, downscale: int | None = None) -> list[str]:
    """Return ffmpeg command for capturing a single JPEG frame."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-nostats"]
    if url.startswith("rtsp://"):
        cmd += [
            "-rtsp_transport",
            transport,
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-probesize",
            "1000000",
            "-analyzeduration",
            "0",
            "-max_delay",
            "500000",
            "-reorder_queue_size",
            "0",
            "-avioflags",
            "direct",
            "-an",
            "-i",
            url,
        ]
    else:
        cmd += ["-i", url, "-an", "-flags", "low_delay", "-fflags", "nobuffer"]
    if downscale and downscale > 1:
        vf = f"scale=trunc(iw/{downscale}/2)*2:trunc(ih/{downscale}/2)*2"
        cmd += ["-vf", vf]
    cmd += [
        "-threads",
        "1",
        "-frames:v",
        "1",
        "-f",
        "image2",
        "-q:v",
        "5",
        "pipe:1",
    ]
    return cmd
