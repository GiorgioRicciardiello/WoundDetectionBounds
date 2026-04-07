"""
woundtrack.metrics
==================

Quantitative biology metrics for wound healing analysis.
Returns DataFrame tables with computed metrics.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from .types import TrajectoriesDict
from .time import find_nearest_time
from .edges import extract_wound_edges_y, is_wound_closing_by_edges
from .plots import debug_plot_wound_edges_overlay

__all__ = [
    "distance_calculator",
]

def distance_calculator(
    trajectories: TrajectoriesDict,
    t_target: float = 12.0,
    debug: bool = False,
    debug_max_plots: int = 10,
    img_alpha: float = 0.25,
    min_closing_frac_columns: float = 0.6,
):
    """
    Compute wound closure speed from masks at t=0 and nearest time to `t_target`.

    What it does per trajectory
    ---------------------------
    1) Locate t=0 entry.
    2) Choose `t_used` = nearest available time to `t_target` (tie -> round up).
    3) Extract upper/lower edges at t=0 and t=t_used.
    4) Compute per-edge displacement magnitudes and convert to speed:
       speed_edge = mean(|Δy|) / Δt
       Always non-negative.
    5) Compute `is_closing` using edge motion directionality:
       upper should move down; lower should move up (in most columns).
    6) Return a table with:
       trajectory, t_used, area_t0, area_tT, speed_upper, speed_lower, speed_mean, is_closing

    Parameters
    ----------
    trajectories:
        Raw trajectories dict.
    t_target:
        Desired comparison time.
    debug:
        If True, show overlay plot(s) using t=0 image as background.
    debug_max_plots:
        Maximum number of trajectories to plot (avoid opening 300 figures).
    img_alpha:
        Transparency for the background t=0 image in debug plots.
    min_closing_frac_columns:
        Fraction of columns that must satisfy closing direction for is_closing=True.

    Returns
    -------
    pandas.DataFrame
        Table of metrics.
    """

    rows: List[Dict[str, Any]] = []
    n_plotted = 0

    for traj_key, traj_data in trajectories.items():
        results = traj_data.get("results", [])
        if not results:
            continue

        times = [r.get("t") for r in results if r.get("t") is not None]
        if 0 not in times:
            continue

        t_used = find_nearest_time(times, t_target)

        r0 = next((r for r in results if r.get("t") == 0), None)
        rT = next((r for r in results if r.get("t") == t_used), None)
        if r0 is None or rT is None:
            continue

        mask0 = r0.get("mask")
        maskT = rT.get("mask")
        if mask0 is None or maskT is None:
            continue

        img0 = r0.get("img_raw", None)

        # areas (pixels)
        area_t0 = int(np.asarray(mask0).astype(bool).sum())
        area_tT = int(np.asarray(maskT).astype(bool).sum())

        # edges
        y0_upper, y0_lower = extract_wound_edges_y(np.asarray(mask0))
        yT_upper, yT_lower = extract_wound_edges_y(np.asarray(maskT))

        vu = ~np.isnan(y0_upper) & ~np.isnan(yT_upper)
        vl = ~np.isnan(y0_lower) & ~np.isnan(yT_lower)
        if vu.sum() == 0 or vl.sum() == 0:
            continue

        # speeds (always positive magnitude)
        dy_upper = yT_upper[vu] - y0_upper[vu]
        dy_lower = y0_lower[vl] - yT_lower[vl]  # positive if lower moved up

        dt = float(t_used) if float(t_used) != 0.0 else np.nan
        if not np.isfinite(dt) or dt <= 0:
            continue

        speed_upper = float(np.mean(np.abs(dy_upper)) / dt)
        speed_lower = float(np.mean(np.abs(dy_lower)) / dt)
        speed_mean = float(np.mean([speed_upper, speed_lower]))

        # closing boolean (directionality + robustness)
        is_closing = is_wound_closing_by_edges(
            y0_upper=y0_upper,
            y0_lower=y0_lower,
            yT_upper=yT_upper,
            yT_lower=yT_lower,
            min_frac_columns=min_closing_frac_columns,
        )

        # optional debug plot
        if debug and (img0 is not None) and (n_plotted < debug_max_plots):
            debug_plot_wound_edges_overlay(
                img0=np.asarray(img0),
                y0_upper=y0_upper,
                y0_lower=y0_lower,
                yT_upper=yT_upper,
                yT_lower=yT_lower,
                traj_key=traj_key,
                t_used=t_used,
                img_alpha=img_alpha,
            )
            n_plotted += 1

        rows.append(
            dict(
                trajectory=traj_key,
                t_used=float(t_used),
                area_t0=area_t0,
                area_tT=area_tT,
                speed_upper=speed_upper,
                speed_lower=speed_lower,
                speed_mean=speed_mean,
                is_closing=bool(is_closing),
            )
        )

    return pd.DataFrame(rows)
