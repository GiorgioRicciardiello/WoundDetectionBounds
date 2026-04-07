"""
woundtrack.edges
================

Spatial geometry utilities for wound edge extraction.
No QC, no metrics, no ML dependencies.
"""

from typing import Tuple

import numpy as np

__all__ = [
    "extract_wound_edges_y",
    "is_wound_closing_by_edges",
]

def extract_wound_edges_y(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract upper and lower wound edges per x-column.

    Parameters
    ----------
    mask:
        2D mask (H, W). Nonzero treated as wound.

    Returns
    -------
    y_upper, y_lower:
        Arrays of shape (W,) containing upper/min y and lower/max y for each x.
        Columns with no wound are NaN.
    """
    H, W = mask.shape
    m = mask.astype(bool)

    y_upper = np.full(W, np.nan, dtype=float)
    y_lower = np.full(W, np.nan, dtype=float)

    for x in range(W):
        ys = np.where(m[:, x])[0]
        if ys.size:
            y_upper[x] = float(ys.min())
            y_lower[x] = float(ys.max())

    return y_upper, y_lower



def is_wound_closing_by_edges(
    y0_upper: np.ndarray,
    y0_lower: np.ndarray,
    yT_upper: np.ndarray,
    yT_lower: np.ndarray,
    min_frac_columns: float = 0.6,
) -> bool:
    """
    Determine whether the wound is closing based on edge motion.

    Closing definition (image coordinates, y increases downward):
    - upper edge should move DOWN: yT_upper > y0_upper
    - lower edge should move UP:   yT_lower < y0_lower

    This function checks the *fraction of valid columns* that satisfy both.

    Parameters
    ----------
    min_frac_columns:
        Minimum fraction of columns that must satisfy each condition.

    Returns
    -------
    bool
        True if closing, else False.
    """
    vu = ~np.isnan(y0_upper) & ~np.isnan(yT_upper)
    vl = ~np.isnan(y0_lower) & ~np.isnan(yT_lower)
    if vu.sum() == 0 or vl.sum() == 0:
        return False

    frac_upper = float(np.mean((yT_upper[vu] - y0_upper[vu]) > 0))
    frac_lower = float(np.mean((y0_lower[vl] - yT_lower[vl]) > 0))  # positive means lower moved up
    return (frac_upper >= min_frac_columns) and (frac_lower >= min_frac_columns)

