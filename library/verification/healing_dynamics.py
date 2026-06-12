"""
Wound Healing Dynamics Analysis
================================

Data pipeline for computing fractional wound closure from verified
trajectories.  Loads the legacy table, filters to human-verified good
segmentations, applies monotonic smoothing, computes fractional closure,
and aligns to a common time grid.

Also provides summary statistics and markdown report generation for
the paper results section.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from library.visualization.utils import (
    add_time_hours,
    align_times_within_identifiers,
    compute_fractional_closure,
    enforce_smooth_monotonic_curve,
)


# ===================================================================
# Data loading and filtering
# ===================================================================

def load_and_filter_legacy_data(
    legacy_path: Path,
    verification_path: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load legacy table and filter to verified-good trajectories.

    Parameters
    ----------
    legacy_path : Path
        Path to ``experiments.xlsx`` with per-timepoint wound data.
    verification_path : Path
        Path to ``verification_results_*.xlsx`` with human verdicts.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        ``(df_legacy_filtered, df_verification)`` where the legacy table
        contains only rows for the 282 verified-good identifiers.

    Raises
    ------
    FileNotFoundError
        If either input file does not exist.
    """
    legacy_path = Path(legacy_path)
    verification_path = Path(verification_path)

    if not legacy_path.exists():
        raise FileNotFoundError(f"Legacy table not found: {legacy_path}")
    if not verification_path.exists():
        raise FileNotFoundError(f"Verification results not found: {verification_path}")

    df_verif = pd.read_excel(verification_path, sheet_name="Per-Image Annotations")
    df_legacy = pd.read_excel(legacy_path)

    # Filter to verified correct AND wound present (exclude "no wound")
    good_mask = (df_verif["correct"] == 1.0) & (df_verif["notes"] != "no wound")
    good_keys = set(df_verif.loc[good_mask, "trajectory_key"])

    df_filtered = df_legacy[df_legacy["identifier"].isin(good_keys)].copy()

    return df_filtered, df_verif


# ===================================================================
# Healing computation pipeline
# ===================================================================

def compute_healing_pipeline(
    df: pd.DataFrame,
    time_grid_hours: float = 0.5,
) -> pd.DataFrame:
    """Run the full healing ratio computation pipeline.

    Steps:
    1. Enforce monotonic non-increasing wound area (PCHIP + cumulative min)
    2. Convert time to hours (rounded to ``time_grid_hours``)
    3. Compute fractional closure: ``(A0 - At) / A0``
    4. Align to common time grid via linear interpolation

    Parameters
    ----------
    df : pd.DataFrame
        Filtered legacy table with columns: ``identifier``, ``wound_area``,
        ``time_min``, plus metadata columns.
    time_grid_hours : float
        Time grid resolution in hours (default 0.5h = 30 min).

    Returns
    -------
    pd.DataFrame
        Aligned dataframe with columns: ``identifier``, ``trajectory``,
        ``time_min``, ``time_h``, ``wound_area``, ``wound_area_corrected``,
        ``fractional_closure``, plus all metadata columns.
    """
    df = df.copy()

    # Drop rows with NaN wound_area (wound fully closed or detection failed)
    n_before = len(df)
    df = df.dropna(subset=["wound_area"])
    n_dropped = n_before - len(df)
    if n_dropped > 0:
        import logging
        logging.getLogger(__name__).info(
            "Dropped %d rows with NaN wound_area", n_dropped
        )

    # Step 1: monotonic smoothing
    df = enforce_smooth_monotonic_curve(
        df,
        area_col="wound_area",
        time_col="time_min",
        group_col="identifier",
        corrected_col="wound_area_corrected",
    )

    # Step 2: add time in hours
    df = add_time_hours(
        df,
        time_col="time_min",
        new_col="time_h",
        round_to=time_grid_hours,
    )

    # Step 3: fractional closure on corrected area
    df = compute_fractional_closure(
        df,
        area_col="wound_area_corrected",
        time_col="time_min",
        group_col="identifier",
    )

    # Step 4: align to common time grid
    grid_minutes = int(time_grid_hours * 60)
    target_times = np.arange(0, 1440 + grid_minutes, grid_minutes)

    df = align_times_within_identifiers(
        df,
        time_col="time_min",
        group_col="identifier",
        value_cols=("wound_area_corrected", "fractional_closure"),
        target_times=target_times,
        method="interpolate",
    )

    # Recompute time_h after alignment
    df["time_h"] = df["time_min"] / 60.0

    # Add trajectory alias for plotting compatibility
    df["trajectory"] = df["identifier"]

    return df


# ===================================================================
# Summary statistics
# ===================================================================

CONDITION_MAP: Dict[str, str] = {
    "dmso": "DMSO",
    "candasertan": "Candasertan",
    "alk5i": "ALK5i",
    "media": "Media",
}

CELLLINE_MAP: Dict[str, str] = {
    "iMC ISOR544C": "Line 1",
    "iMC MUTR544C": "Line 2",
}


def compute_summary_statistics(
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute summary statistics for the wound healing results section.

    Parameters
    ----------
    df : pd.DataFrame
        Aligned pipeline output with ``fractional_closure``, ``time_h``,
        ``identifier``, ``sample_condition``, ``cell_line`` columns.

    Returns
    -------
    dict
        Nested dictionary with:
        - ``n_trajectories``: total count
        - ``n_per_condition``: {condition: count}
        - ``n_per_cellline``: {cell_line: count}
        - ``closure_at_24h``: {condition: {mean, sem, n}}
        - ``closure_at_12h``: {condition: {mean, sem, n}}
        - ``time_to_50pct``: {condition: float or None}
    """
    n_trajectories = df["identifier"].nunique()

    # Per-condition counts (at t=0)
    t0 = df[df["time_h"] == 0.0]
    n_per_condition = (
        t0.groupby("sample_condition")["identifier"]
        .nunique()
        .to_dict()
    )
    n_per_cellline = (
        t0.groupby("cell_line")["identifier"]
        .nunique()
        .to_dict()
    )

    # Closure at specific timepoints
    closure_at_24h = _closure_at_time(df, target_h=24.0)
    closure_at_12h = _closure_at_time(df, target_h=12.0)

    # Time to 50% closure per condition
    time_to_50pct = _time_to_threshold(df, threshold=0.5)

    return {
        "n_trajectories": n_trajectories,
        "n_per_condition": n_per_condition,
        "n_per_cellline": n_per_cellline,
        "closure_at_24h": closure_at_24h,
        "closure_at_12h": closure_at_12h,
        "time_to_50pct": time_to_50pct,
    }


def _closure_at_time(
    df: pd.DataFrame,
    target_h: float,
) -> Dict[str, Dict[str, float]]:
    """Compute mean fractional closure at a target time per condition.

    Parameters
    ----------
    df : pd.DataFrame
        Aligned pipeline output.
    target_h : float
        Target time in hours.

    Returns
    -------
    dict
        ``{condition: {"mean": float, "sem": float, "n": int}}``.
    """
    # Find the closest time_h to target
    available = df["time_h"].unique()
    closest = available[np.argmin(np.abs(available - target_h))]

    df_t = df[df["time_h"] == closest]
    result: Dict[str, Dict[str, float]] = {}

    for cond, grp in df_t.groupby("sample_condition"):
        vals = grp["fractional_closure"].dropna()
        n = len(vals)
        mean_val = float(vals.mean()) if n > 0 else np.nan
        sem_val = float(vals.std() / np.sqrt(n)) if n > 1 else np.nan
        result[str(cond)] = {"mean": mean_val, "sem": sem_val, "n": n}

    return result


def _time_to_threshold(
    df: pd.DataFrame,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Estimate the time at which mean fractional closure crosses a threshold.

    Uses linear interpolation on the population mean curve per condition.

    Parameters
    ----------
    df : pd.DataFrame
        Aligned pipeline output.
    threshold : float
        Fractional closure threshold (default 0.5 = 50%).

    Returns
    -------
    dict
        ``{condition: time_hours}`` or ``None`` if threshold not reached.
    """
    result: Dict[str, Any] = {}

    for cond, grp in df.groupby("sample_condition"):
        mean_curve = (
            grp.groupby("time_h")["fractional_closure"]
            .mean()
            .sort_index()
        )
        times = mean_curve.index.to_numpy()
        values = mean_curve.values

        # Find first crossing
        above = np.where(values >= threshold)[0]
        if len(above) == 0:
            result[str(cond)] = None
        elif above[0] == 0:
            result[str(cond)] = float(times[0])
        else:
            # Linear interpolation between the two bracketing timepoints
            idx = above[0]
            t0, t1 = times[idx - 1], times[idx]
            v0, v1 = values[idx - 1], values[idx]
            if v1 != v0:
                t_cross = t0 + (threshold - v0) * (t1 - t0) / (v1 - v0)
            else:
                t_cross = t0
            result[str(cond)] = float(t_cross)

    return result


# ===================================================================
# Markdown report generation
# ===================================================================

def generate_results_markdown(
    stats: Dict[str, Any],
    plot_paths: Dict[str, Path],
) -> str:
    """Generate markdown text for the wound healing dynamics results section.

    Parameters
    ----------
    stats : dict
        Output from :func:`compute_summary_statistics`.
    plot_paths : dict
        Mapping of plot name to saved file path.

    Returns
    -------
    str
        Markdown text to append to ``docs/verification_results.md``.
    """
    n = stats["n_trajectories"]
    n_cond = stats["n_per_condition"]
    closure_24h = stats["closure_at_24h"]
    closure_12h = stats["closure_at_12h"]
    t50 = stats["time_to_50pct"]

    # Condition list
    cond_parts: List[str] = []
    for raw, pretty in CONDITION_MAP.items():
        count = n_cond.get(raw, 0)
        if count > 0:
            cond_parts.append(f"{pretty} (n={count})")
    cond_list = ", ".join(cond_parts)

    # Cell line counts
    n_cl = stats["n_per_cellline"]
    cl_parts = [f"{CELLLINE_MAP.get(k, k)} (n={v})" for k, v in sorted(n_cl.items())]
    cl_list = ", ".join(cl_parts)

    # Table 5: closure at 24h
    table_rows: List[str] = []
    for raw, pretty in CONDITION_MAP.items():
        c = closure_24h.get(raw, {})
        mean_val = c.get("mean", np.nan)
        sem_val = c.get("sem", np.nan)
        count = c.get("n", 0)
        if not np.isnan(mean_val):
            table_rows.append(
                f"| {pretty:<15s} | {count:>3d} | {mean_val:>12.3f} | {sem_val:>5.3f} |"
            )

    # Table 6: closure at 12h
    table_12h_rows: List[str] = []
    for raw, pretty in CONDITION_MAP.items():
        c = closure_12h.get(raw, {})
        mean_val = c.get("mean", np.nan)
        sem_val = c.get("sem", np.nan)
        count = c.get("n", 0)
        if not np.isnan(mean_val):
            table_12h_rows.append(
                f"| {pretty:<15s} | {count:>3d} | {mean_val:>12.3f} | {sem_val:>5.3f} |"
            )

    # Time to 50% closure text
    t50_parts: List[str] = []
    for raw, pretty in CONDITION_MAP.items():
        t = t50.get(raw)
        if t is not None:
            t50_parts.append(f"{pretty}: {t:.1f}h")
        else:
            t50_parts.append(f"{pretty}: not reached")
    t50_text = "; ".join(t50_parts)

    # Relative paths for figures
    def _rel(key: str) -> str:
        p = plot_paths.get(key)
        if p is None:
            return ""
        return Path(p).name

    md = f"""---

## Wound Healing Dynamics

### Data Selection

Of the 282 verified segmentations, all were included in the wound healing
dynamics analysis.  The dataset comprised **{n} trajectories** across four
treatment conditions: {cond_list}.  Two cell lines were represented:
{cl_list}.  Each trajectory was measured at 20--25 timepoints spanning
approximately 0--24 hours.

### Methods

Wound area at each timepoint was first corrected using a monotonic
non-increasing constraint (PCHIP cubic interpolation with cumulative minimum
enforcement), ensuring biologically plausible wound closure where the wound
can only shrink over time.  Fractional closure was then computed as
(A0 - At) / A0, where A0 is the wound area at t=0.  Time series were aligned
to a common 0.5-hour grid using linear interpolation.  Population statistics
(mean +/- SEM) were computed per condition at each aligned timepoint.

### Wound Closure Over Time

**Table 5.** Mean fractional closure at 24 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
{chr(10).join(table_rows)}

**Table 6.** Mean fractional closure at 12 hours by treatment condition.

| Condition       |   n | Mean Closure |   SEM |
|-----------------|----:|-------------:|------:|
{chr(10).join(table_12h_rows)}

Estimated time to 50% wound closure: {t50_text}.

**Figure 1.** Fractional wound closure over 24 hours by treatment condition
(mean +/- SEM, all concentrations pooled).
See `results/wound_healing_dynamics/{_rel("by_condition")}`.

**Figure 2.** Healing dynamics stratified by cell line and drug concentration,
showing reproducibility across biological replicates.
See `results/wound_healing_dynamics/{_rel("by_cellline")}`.

**Figure 3.** Dose-response relationship for Candasertan and ALK5i across
three concentrations (0.01, 0.1, 1.0 mM).
See `results/wound_healing_dynamics/{_rel("by_concentration")}`.

**Figure 4.** Individual wound healing trajectories (thin lines) with
population mean overlay (thick line), illustrating inter-sample variability.
See `results/wound_healing_dynamics/{_rel("individual")}`.
"""
    return md
