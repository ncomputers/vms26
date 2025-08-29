import subprocess
import sys
import textwrap
import types

import numpy as np

sys.modules.setdefault("cv2", types.SimpleNamespace())
from modules.renderer import RendererProcess


def test_renderer_writes_overlay():
    shape = (10, 10, 3)
    renderer = RendererProcess(shape)
    renderer.frame[:] = 0
    tracks = {1: {"bbox": (1, 1, 5, 5)}}
    renderer.queue.put(
        {
            "tracks": tracks,
            "flags": {
                "show_ids": False,
                "show_track_lines": True,
                "show_lines": False,
                "show_counts": False,
            },
            "line_orientation": "vertical",
            "line_ratio": 0.5,
            "counts": {"entered": 0, "exited": 0, "inside": 0},
        }
    )
    renderer.queue.put(None)
    renderer.process.join()
    assert renderer.output.any()
    renderer.close()


def test_renderer_no_resource_tracker_warning():
    code = textwrap.dedent(
        """
        from modules.renderer import RendererProcess
        with RendererProcess((5, 5, 3)):
            pass
        """
    )
    proc = subprocess.run([sys.executable, "-Wdefault", "-c", code], capture_output=True, text=True)
    assert "resource_tracker" not in proc.stderr
