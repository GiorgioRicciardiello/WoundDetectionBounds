"""
woundtrack.time
===============

Time handling utilities for wound-healing trajectories.
"""

from typing import Sequence

import numpy as np

from .types import TimeT

__all__ = [
    "find_nearest_time",
]


def find_nearest_time(times: Sequence[TimeT], target: TimeT) -> float:
    """
    Find nearest time to target. If tie, choose the MAX (round up).

    Parameters
    ----------
    times : Sequence[TimeT]
        Available time values.
    target : TimeT
        Target time to find nearest match for.

    Returns
    -------
    float
        The nearest time value. If multiple times are equally close,
        returns the maximum (rounds up).

    Example
    -------
    >>> find_nearest_time([11.3, 12.3, 13.3], target=12)
    12.3
    >>> find_nearest_time([11.5, 12.5], target=12)  # tie -> round up
    12.5
    """
    arr = np.asarray(times, dtype=float)
    diffs = np.abs(arr - float(target))
    md = float(diffs.min())
    return float(arr[diffs == md].max())
