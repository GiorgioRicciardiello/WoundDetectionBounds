"""
A collection of functions for processing and analyzing wound healing data. This module
includes utilities for loading data, aggregating statistics, computing healing ratios,
enforcing monotonic corrections, aligning time-series data, and converting time units.
"""
import pandas as pd
from pathlib import Path
import numpy as np
from typing import Iterable, Optional, Literal
from scipy.interpolate import PchipInterpolator


# --------------------------------------------------
# Load data
# --------------------------------------------------
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_excel(path)

# --------------------------------------------------
# Aggregate mean ± std (ordinal time)
# --------------------------------------------------
def aggregate_mean_std(
    df: pd.DataFrame,
    group_cols: list[str],
    time_col: str = "time_min",
    value_col: str = "wound_area",
):
    df = df.dropna(subset=[value_col])

    agg = (
        df
        .groupby(group_cols + [time_col])
        .agg(
            mean_area=(value_col, "mean"),
            std_area=(value_col, "std"),
            n=("identifier", "nunique"),
        )
        .reset_index()
        .sort_values(time_col)
    )
    return agg


# --------------------------------------------------
# Healing ratio from corrected area
# --------------------------------------------------
def compute_fractional_closure(
    df: pd.DataFrame,
    area_col: str = "wound_area",
    time_col: str = "time_min",
    group_col: str = "identifier",
) -> pd.DataFrame:
    """
    Compute healing ratio from wound area over time.

    Healing ratio is defined as:
        (A0 - A_t) / A0

    where A0 is the wound area at the first time point of each group.

    The function operates group-wise and appends a new column
    to the returned DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe containing wound area measurements.
    area_col : str
        Column containing wound area values.
    time_col : str
        Time column used to order observations.
    group_col : str
        Column defining independent wound trajectories.
    output_col : str
        Name of the output column containing the healing ratio.

    Returns
    -------
    pd.DataFrame
        Copy of the input DataFrame with an additional column:
        - `output_col` (float): healing ratio in [0, 1] (or NaN if invalid).
    """
    df = df.copy()

    def _normalize(group: pd.DataFrame) -> pd.DataFrame:
        # 🔒 restore group identity
        group[group_col] = group.name

        group = group.sort_values(time_col)
        A0 = group.iloc[0][area_col]

        if A0 <= 0:
            group["fractional_closure"] = np.nan
        else:
            group["fractional_closure"] = (A0 - group[area_col]) / A0

        return group

    df = df.groupby(group_col, group_keys=False).apply(_normalize)
    return df



def compute_closure_rate(
    df: pd.DataFrame,
    rate_col: str = "closure_rate",
    time_col: str = "time_min",
    group_col: str = "condition_id",
    ci_method: Literal["sem", "bootstrap"] = "sem",
    ci_level: float = 0.95,
    n_bootstrap: int = 1000,
    random_state: int | None = None,
) -> pd.DataFrame:
    """
    Compute confidence intervals for wound closure rate over time.

    The function aggregates closure rates across trajectories
    and computes pointwise confidence intervals.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe containing closure rates per trajectory.
    rate_col : str
        Column with closure rate values.
    time_col : str
        Time column.
    group_col : str
        Column defining replicate groups (e.g. condition, treatment).
    ci_method : {"sem", "bootstrap"}
        Method used to estimate confidence intervals.
    ci_level : float
        Confidence level (default: 0.95).
    n_bootstrap : int
        Number of bootstrap resamples (used if ci_method="bootstrap").
    random_state : int | None
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Aggregated dataframe with columns:
        - mean_rate
        - ci_lower
        - ci_upper
        - n
    """

    rng = np.random.default_rng(random_state)
    z = 1.96 if ci_level == 0.95 else abs(
        np.percentile(
            np.random.standard_normal(100000),
            [(1 - ci_level) / 2 * 100, (1 + ci_level) / 2 * 100]
        )[1]
    )

    results = []

    grouped = df.groupby([group_col, time_col])

    for (group_id, t), g in grouped:
        rates = g[rate_col].dropna().to_numpy()
        n = len(rates)

        if n == 0:
            continue

        mean_rate = float(np.mean(rates))

        if ci_method == "sem" and n > 1:
            sem = np.std(rates, ddof=1) / np.sqrt(n)
            ci_lower = mean_rate - z * sem
            ci_upper = mean_rate + z * sem

        elif ci_method == "bootstrap" and n > 1:
            boot_means = np.empty(n_bootstrap)

            for i in range(n_bootstrap):
                sample = rng.choice(rates, size=n, replace=True)
                boot_means[i] = np.mean(sample)

            alpha = (1 - ci_level) / 2
            ci_lower = np.quantile(boot_means, alpha)
            ci_upper = np.quantile(boot_means, 1 - alpha)

        else:
            ci_lower = np.nan
            ci_upper = np.nan

        results.append({
            group_col: group_id,
            time_col: t,
            "mean_rate": mean_rate,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n": n,
        })

    return pd.DataFrame(results)

# --------------------------------------------------
# Monotonic wound area correction
# --------------------------------------------------
def enforce_smooth_monotonic_curve(
    df: pd.DataFrame,
    area_col: str = "wound_area",
    time_col: str = "time_min",
    group_col: str = "identifier",
    corrected_col: str = "wound_area_corrected",
) -> pd.DataFrame:
    """
    Enforce monotonic non-increasing wound area per group
    and apply smooth monotonic cubic interpolation (PCHIP).
    """

    df = df.copy()


    def _apply(group: pd.DataFrame) -> pd.DataFrame:
        # 🔒 restore group key
        group[group_col] = group.name

        group = group.sort_values(time_col)

        x = group[time_col].to_numpy(dtype=float)
        y = group[area_col].to_numpy(dtype=float)

        y = np.minimum.accumulate(y)

        if len(x) >= 3:
            y = PchipInterpolator(x, y)(x)

        group[corrected_col] = y
        return group

    df = df.groupby(group_col, group_keys=False).apply(_apply)
    return df



# --------------------------------------------------
# Align time points at different instances between experiments
# --------------------------------------------------
def align_times_within_identifiers(
    df: pd.DataFrame,
    time_col: str = "time_min",
    group_col: str = "identifier",
    value_cols: Iterable[str] = ("wound_area_corrected",),
    target_times: Optional[Iterable[float]] = None,
    method: str = "nearest",  # "nearest" or "interpolate"
) -> pd.DataFrame:
    """
    Align time-series data within each identifier so trajectories with
    different sampling times can be compared on a common time axis.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched legacy dataframe (after monotonic correction).
    time_col : str
        Numeric time column (e.g. time_min).
    group_col : str
        Column defining independent trajectories (identifier).
    value_cols : iterable of str
        Columns to align (e.g. wound_area_corrected, healing_ratio).
    target_times : iterable or None
        Target time points (same units as time_col). If None, uses the
        union of rounded integer times across all identifiers.
    method : str
        'nearest' (default, safe for ordinal data) or 'interpolate'.

    Returns
    -------
    pd.DataFrame
        Time-aligned dataframe.
    """
    # -----------------------------
    # Validation
    # -----------------------------
    required = {time_col, group_col, *value_cols}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy().sort_values([group_col, time_col])

    # Identify metadata columns (constant within identifier)
    meta_cols = [
        c for c in df.columns
        if c not in set(value_cols) | {time_col}
    ]

    # -----------------------------
    # Define target time grid
    # -----------------------------
    if target_times is None:
        target_times = np.sort(
            df[time_col].round().astype(int).unique()
        )
    else:
        target_times = np.asarray(target_times)

    aligned_blocks = []

    # -----------------------------
    # Align per identifier
    # -----------------------------
    for ident, g in df.groupby(group_col):
        g = g.sort_values(time_col)

        # Base output frame with target times
        out = pd.DataFrame({
            group_col: ident,
            time_col: target_times,
        })

        # ---- propagate metadata (constant per identifier) ----
        meta = g.iloc[0][meta_cols]
        for col in meta_cols:
            out[col] = meta[col]

        # ---- align value columns ----
        t_src = g[time_col].values

        if method == "nearest":
            idx = np.abs(
                t_src[:, None] - target_times[None, :]
            ).argmin(axis=0)

            for col in value_cols:
                out[col] = g.iloc[idx][col].values

        elif method == "interpolate":
            for col in value_cols:
                out[col] = np.interp(
                    target_times,
                    t_src,
                    g[col].values,
                )
        else:
            raise ValueError("method must be 'nearest' or 'interpolate'")

        aligned_blocks.append(out)

    df_out = pd.concat(aligned_blocks, ignore_index=True)

    return df_out


# --------------------------------------------------
# convert time from minutes to hours
# --------------------------------------------------
def add_time_hours(
    df: pd.DataFrame,
    time_col: str = "time_min",
    new_col: str = "time_h",
    round_to: float = 0.5,  # hours
) -> pd.DataFrame:
    """
    Convert time from minutes to hours and align to a regular grid.
    """
    df = df.copy()
    df[new_col] = df[time_col] / 60.0
    df[new_col] = (df[new_col] / round_to).round() * round_to
    return df