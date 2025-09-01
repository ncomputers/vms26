from utils import ffmpeg as ffmpeg_utils


def test_build_preview_cmd_no_timeouts():
    cmd = ffmpeg_utils.build_preview_cmd("rtsp://x", "tcp")
    assert "-rw_timeout" not in cmd
    assert "-stimeout" not in cmd
    assert ["-rtsp_transport", "tcp"] == cmd[cmd.index("-rtsp_transport"): cmd.index("-rtsp_transport") + 2]


def test_build_snapshot_cmd_no_timeouts():
    cmd = ffmpeg_utils.build_snapshot_cmd("rtsp://x", "tcp")
    assert "-rw_timeout" not in cmd
    assert "-stimeout" not in cmd
    assert ["-rtsp_transport", "tcp"] == cmd[cmd.index("-rtsp_transport"): cmd.index("-rtsp_transport") + 2]
    assert ["-i", "rtsp://x"] == cmd[cmd.index("-i"): cmd.index("-i") + 2]


def test_build_preview_cmd_downscale():
    cmd = ffmpeg_utils.build_preview_cmd("rtsp://x", "udp", downscale=2)
    assert "-vf" in cmd
    idx = cmd.index("-vf") + 1
    assert cmd[idx] == "scale=trunc(iw/2/2)*2:trunc(ih/2/2)*2"
