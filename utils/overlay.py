"""Minimal overlay utilities for tests."""

from typing import Iterable, Tuple

import numpy as np


def draw_boxes_np(
    frame: np.ndarray,
    boxes: Iterable[Tuple[int, int, int, int]],
    color=(0, 255, 0),
    thickness: int = 1,
):
    """Return frame unchanged; placeholder for box drawing."""
    return frame
