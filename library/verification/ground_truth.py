"""
Ground-Truth Mask Generation
=============================

Two modes for building ground-truth masks:

1. **Full polygon mode** — user draws the entire wound boundary from
   scratch.  Multiple polygons are unioned into a single mask.

2. **Edge correction mode** — the model's upper/lower edge arrays are
   taken as the base, and the user draws corrected boundary segments
   within a limited x-range.  Only the corrected columns are replaced;
   the rest of the mask is inherited from the model.

Both modes produce a binary ``(H, W)`` uint8 mask suitable for
pixel-level metric comparison via :mod:`library.verification.metrics`.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from skimage.draw import polygon as sk_polygon


def polygons_to_mask(
    polygons: List[List[Tuple[float, float]]],
    img_shape: Tuple[int, int],
) -> np.ndarray:
    """Rasterise one or more polygons into a binary mask.

    Parameters
    ----------
    polygons : list of list of (x, y)
        Each inner list is a closed polygon defined by vertex coordinates
        in *image space* (origin top-left, x = column, y = row).
        Coordinates may be float (sub-pixel); they are rounded internally.
    img_shape : (int, int)
        ``(H, W)`` — height and width of the target mask.

    Returns
    -------
    np.ndarray
        Binary mask of shape ``img_shape``, dtype uint8, values {0, 1}.
        Foreground (wound) = 1, background = 0.

    Raises
    ------
    ValueError
        If any polygon has fewer than 3 vertices (cannot form an area).

    Notes
    -----
    Vertex ordering (CW vs CCW) does not matter — ``skimage.draw.polygon``
    fills the interior regardless.
    """
    mask = np.zeros(img_shape, dtype=np.uint8)
    H, W = img_shape

    for poly in polygons:
        if len(poly) < 3:
            raise ValueError(
                f"Polygon must have >= 3 vertices, got {len(poly)}"
            )

        # Separate x (col) and y (row) coordinates
        cols = np.array([p[0] for p in poly], dtype=np.float64)
        rows = np.array([p[1] for p in poly], dtype=np.float64)

        # Rasterise — sk_polygon expects (row_coords, col_coords)
        rr, cc = sk_polygon(rows, cols, shape=(H, W))

        mask[rr, cc] = 1

    return mask


# ===================================================================
# Edge correction mode
# ===================================================================

def correct_edges(
    model_upper: np.ndarray,
    model_lower: np.ndarray,
    corrections: List[dict],
    img_shape: Tuple[int, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a corrected mask by replacing model edges in user-specified x-ranges.

    The model mask is defined by ``upper_edge[x]`` and ``lower_edge[x]``
    — one y-value per column.  Instead of redrawing the whole wound, the
    user provides correction segments: a list of ``(x, y)`` points that
    redefine either the upper or lower boundary within the x-range
    spanned by those points.  Columns outside any correction keep the
    original model edge.

    Parameters
    ----------
    model_upper : np.ndarray
        Model's upper edge, shape ``(W,)``, float.
    model_lower : np.ndarray
        Model's lower edge, shape ``(W,)``, float.
    corrections : list of dict
        Each dict has:
        - ``"edge"``: ``"upper"`` or ``"lower"``
        - ``"points"``: list of ``[x, y]`` pairs (at least 2)
        The points define a polyline; y-values are linearly interpolated
        for every integer column between ``min(x)`` and ``max(x)``.
    img_shape : (int, int)
        ``(H, W)`` of the image.

    Returns
    -------
    corrected_upper : np.ndarray
        Shape ``(W,)`` — upper edge with corrections applied.
    corrected_lower : np.ndarray
        Shape ``(W,)`` — lower edge with corrections applied.
    mask : np.ndarray
        Binary mask ``(H, W)`` uint8 rebuilt from corrected edges.

    Raises
    ------
    ValueError
        If a correction has fewer than 2 points or an invalid edge name.

    Notes
    -----
    Interpolation uses ``numpy.interp`` (piecewise-linear) which is
    exact at the user-clicked points and linear between them.  Columns
    outside the correction's x-range are untouched.
    """
    W = img_shape[1]
    H = img_shape[0]

    corrected_upper = model_upper.copy()
    corrected_lower = model_lower.copy()

    for corr in corrections:
        edge = corr.get("edge", "").lower()
        points = corr.get("points", [])

        if edge not in ("upper", "lower"):
            raise ValueError(f"Edge must be 'upper' or 'lower', got '{edge}'")
        if len(points) < 2:
            raise ValueError(
                f"Edge correction needs >= 2 points, got {len(points)}"
            )

        # Extract x and y from the user's polyline
        xs = np.array([p[0] for p in points], dtype=np.float64)
        ys = np.array([p[1] for p in points], dtype=np.float64)

        # Sort by x for interpolation
        order = np.argsort(xs)
        xs = xs[order]
        ys = ys[order]

        # Integer columns in the correction range
        x_min = max(0, int(np.floor(xs[0])))
        x_max = min(W - 1, int(np.ceil(xs[-1])))
        col_range = np.arange(x_min, x_max + 1)

        # Interpolate y for each column
        y_interp = np.interp(col_range.astype(np.float64), xs, ys)

        if edge == "upper":
            corrected_upper[col_range] = y_interp
        else:
            corrected_lower[col_range] = y_interp

    # Rebuild mask from corrected edges (vectorised)
    y_up = np.clip(corrected_upper, 0, H - 1).astype(int)
    y_lo = np.clip(corrected_lower, 0, H - 1).astype(int)
    rows = np.arange(H)[:, None]  # (H, 1)

    open_cols = y_up < y_lo
    mask = (
        (rows >= y_up[None, :])
        & (rows <= y_lo[None, :])
        & open_cols[None, :]
    ).astype(np.uint8)

    return corrected_upper, corrected_lower, mask
