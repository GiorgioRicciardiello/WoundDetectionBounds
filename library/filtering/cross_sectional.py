"""
Cross-Sectional Analysis for Wound Healing Experiments
=======================================================

Single-timepoint (cross-sectional) analysis for comparing conditions
at specific times. Computes speed/distance from t=0 to t=target.

Functions:
- distance_calculator: Compute speed at a single target time
- filter_trajectories_by_t0_wound_distribution: QC filter using t=0 mask
- select_best_experiments_across_wells_cross_sectional: Select wells closest to mean
- plot_speed_by_cellline_condition: Bar plots by cell line and condition
"""

from pathlib import Path
from typing import Dict, Tuple, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from tqdm import tqdm


# =============================================================================
# Utility functions
# =============================================================================

def _find_nearest_time(times, target):
    """
    Nearest time to target.
    If tie, choose the MAX (round up).
    """
    times = np.asarray(times, dtype=float)
    diffs = np.abs(times - target)
    min_diff = diffs.min()
    return times[diffs == min_diff].max()


# =============================================================================
# Trajectory filtering
# =============================================================================

def filter_trajectories_by_t0_wound_distribution(
    trajectories: Dict,
    verify_kwargs: dict | None = None,
) -> Tuple[Dict, pd.DataFrame]:
    """
    Filter trajectories using ONLY the t=0 wound mask
    and verify_wound_by_distribution.

    Parameters
    ----------
    trajectories : dict
        Original trajectories dictionary
    verify_kwargs : dict | None
        Extra arguments passed to verify_wound_by_distribution

    Returns
    -------
    filtered_trajectories : dict
        Trajectories that pass QC at t=0
    keep_table_df : pd.DataFrame
        Per-trajectory decision with columns: trajectory, keep
    """
    from library.woundtrack.qc import verify_wound_by_distribution

    if verify_kwargs is None:
        verify_kwargs = {}

    filtered_trajectories = {}
    keep_table = {}

    for traj_key, traj_data in tqdm(
            trajectories.items(),
            total=len(trajectories),
            desc="QC trajectories (t=0)"
    ):
        results = traj_data.get("results", [])
        t0_entry = next((r for r in results if r.get("t", None) == 0), None)

        if t0_entry is None or "mask" not in t0_entry:
            keep_table[traj_key] = False
            continue

        qc = verify_wound_by_distribution(t0_entry["mask"], **verify_kwargs)

        keep = bool(qc["valid"])
        keep_table[traj_key] = keep

        if keep:
            filtered_trajectories[traj_key] = traj_data

    keep_table_df = pd.DataFrame.from_dict(keep_table, orient="index", columns=["keep"])
    keep_table_df = keep_table_df.reset_index().rename(columns={"index": "trajectory"})

    return filtered_trajectories, keep_table_df


# =============================================================================
# Well selection
# =============================================================================

def _select_experiments(
    df_master: pd.DataFrame,
    time: float = 0.0,
    concentration: float = 0.1,
    sample_condition: str = "candasertan",
    cell_line: str = 'iMC MUTR544C',
    experiment: str = "EXP1",
    n_select: int = 3,
    value_col: str = "wound_area",
) -> pd.DataFrame:
    """Select best wells for experiment at time based on wound_area."""
    
    def _pick_closest_to_mean(df, value_col='wound_area', n=3):
        mean_val = df[value_col].mean()
        return (
            df.assign(dist_to_mean=(df[value_col] - mean_val).abs())
            .sort_values('dist_to_mean')
            .head(n)
            .drop(columns='dist_to_mean')
        )

    df_well_at_drug = df_master.loc[
        (df_master["experiment"] == experiment) &
        (df_master["t_seg"] == time) &
        (df_master["cell_line"] == cell_line) &
        (df_master["concentration_mm"] == concentration) &
        (df_master["sample_condition"] == sample_condition)
    ]

    n_good_wells = df_well_at_drug.shape[0]
    report_str = (
        f"{experiment:<5} | {time:>4.1f} | {cell_line:<14} | "
        f"{concentration:>4.1f} | {sample_condition:<12} | {n_good_wells:>2d}"
    )

    if n_good_wells == 0:
        print(f"\033[31m{report_str}\033[0m")
        return pd.DataFrame()
    else:
        print(report_str)

    if n_good_wells <= n_select:
        n_select = n_good_wells

    df_best_wells = _pick_closest_to_mean(df_well_at_drug, value_col=value_col, n=n_select)
    df_best_wells['total_wells'] = n_good_wells

    return df_best_wells


def select_best_experiments_across_wells_cross_sectional(
    df_map: pd.DataFrame,
    time: float = 0,
) -> pd.DataFrame:
    """
    Select best experimental data across wells based on wound_area criteria.
    
    Parameters
    ----------
    df_map : pd.DataFrame
        DataFrame with columns: concentration_mm, cell_line, sample_condition, experiment
    time : float
        Time point for selection (default: 0)
    
    Returns
    -------
    pd.DataFrame
        Best wells with all time points
    """
    header = (
        f"{'EXP':<5} | {'TIME':>4} | {'CELL_LINE':<14} | "
        f"{'CONC':>4} | {'CONDITION':<12} | {'N':>2}"
    )
    print(header)
    print("-" * len(header))

    concentrations = df_map.concentration_mm.unique()
    cell_lines = df_map["cell_line"].unique()
    sample_conditions = df_map["sample_condition"].unique()
    experiments = df_map["experiment"].unique()
    
    results = []
    for experiment in experiments:
        for concentration in concentrations:
            for cell_line in cell_lines:
                for sample_condition in sample_conditions:
                    df_best_wells = _select_experiments(
                        df_master=df_map,
                        time=time,
                        experiment=experiment,
                        concentration=concentration,
                        sample_condition=sample_condition,
                        cell_line=cell_line,
                    )
                    if not df_best_wells.empty:
                        results.append(df_best_wells)

    df_best_wells_all = pd.concat(results, ignore_index=True)
    df_best_well_series = pd.merge(
        df_map,
        df_best_wells_all[['identifier', 'total_wells']],
        how='inner',
        on='identifier'
    )
    return df_best_well_series


# =============================================================================
# Distance/Speed Calculator
# =============================================================================

def distance_calculator(
    trajectories: Dict,
    t_target: float = 12,
    debug: bool = False,
) -> pd.DataFrame:
    """
    Calculate wound closing speed using masks at t=0 and t=t_target.

    Speed is computed as the mean vertical displacement per unit time,
    averaged across x and across upper/lower wound edges.

    Parameters
    ----------
    trajectories : Dict
        Trajectories dictionary from wound healing pipeline
    t_target : float
        Target time point for comparison (default: 12)
    debug : bool
        If True, show debug plots

    Returns
    -------
    pd.DataFrame with columns:
        trajectory, t_used, area_t0, area_tT, distance_upper, distance_lower,
        distance_mean, speed_upper, speed_lower, speed_mean, is_closing
    """

    def extract_wound_edges_y(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Extract upper and lower wound edges per x-column."""
        H, W = mask.shape
        mask = mask.astype(bool)
        y_upper = np.full(W, np.nan)
        y_lower = np.full(W, np.nan)
        for x in range(W):
            ys = np.where(mask[:, x])[0]
            if ys.size > 0:
                y_upper[x] = ys.min()
                y_lower[x] = ys.max()
        return y_upper, y_lower

    def _debug_plot_wound_edges_overlay(
            img0: np.ndarray,
            y0_upper: np.ndarray,
            y0_lower: np.ndarray,
            yT_upper: np.ndarray,
            yT_lower: np.ndarray,
            traj_key: str,
            t_used: float,
            img_alpha: float = 0.25,
            line_width: float = 1.5,
    ) -> None:
        H, W = img0.shape
        x = np.arange(W)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.imshow(img0, cmap="gray", alpha=img_alpha)

        ax.plot(x, y0_upper, color="cyan", lw=line_width, label="upper t=0")
        ax.plot(x, yT_upper, color="cyan", lw=line_width, ls="--", label="upper t=T")
        ax.fill_between(x, y0_upper, yT_upper,
                       where=~np.isnan(y0_upper) & ~np.isnan(yT_upper),
                       color="cyan", alpha=0.25, interpolate=True)

        ax.plot(x, y0_lower, color="magenta", lw=line_width, label="lower t=0")
        ax.plot(x, yT_lower, color="magenta", lw=line_width, ls="--", label="lower t=T")
        ax.fill_between(x, y0_lower, yT_lower,
                       where=~np.isnan(y0_lower) & ~np.isnan(yT_lower),
                       color="magenta", alpha=0.25, interpolate=True)

        ax.set_title(f"{traj_key} | t=0 → t={t_used}")
        ax.set_xlim(0, W - 1)
        ax.set_ylim(H - 1, 0)
        ax.legend(frameon=False, fontsize=9)
        plt.tight_layout()
        plt.show()

    rows = []

    for traj_key, traj_data in trajectories.items():
        results = traj_data.get("results", [])
        if len(results) == 0:
            continue

        times = [r.get("t") for r in results if r.get("t") is not None]
        if 0 not in times:
            continue

        t_used = _find_nearest_time(times, t_target)

        r0 = next(r for r in results if r.get("t") == 0)
        rT = next(r for r in results if r.get("t") == t_used)

        img0 = r0.get("img_raw")
        imgT = rT.get("img_raw")
        mask0 = r0.get("mask")
        maskT = rT.get("mask")

        if mask0 is None or maskT is None:
            continue

        area_t0 = int(mask0.astype(bool).sum())
        area_tT = int(maskT.astype(bool).sum())

        y0_upper, y0_lower = extract_wound_edges_y(mask0)
        yT_upper, yT_lower = extract_wound_edges_y(maskT)

        valid_upper = ~np.isnan(y0_upper) & ~np.isnan(yT_upper)
        valid_lower = ~np.isnan(y0_lower) & ~np.isnan(yT_lower)

        if valid_upper.sum() == 0 or valid_lower.sum() == 0:
            continue

        # Sign convention: positive = closing (inward movement)
        # Upper edge closing: yT > y0 (moves down in image coords)
        # Lower edge closing: yT < y0 (moves up in image coords)
        dy_upper = yT_upper[valid_upper] - y0_upper[valid_upper]
        dy_lower = y0_lower[valid_lower] - yT_lower[valid_lower]

        # NOTE: dt is the frame index, not hours.  Speed units are
        # px/frame.  Convert to px/h by dividing by the imaging interval
        # (e.g. 2 h/frame for Incucyte).  See calibration module (TODO).
        dt = float(t_used)

        distance_upper = np.mean(np.abs(dy_upper))
        distance_lower = np.mean(np.abs(dy_lower))
        distance_mean = np.mean([distance_upper, distance_lower])

        speed_upper = distance_upper / dt if dt > 0 else 0.0
        speed_lower = distance_lower / dt if dt > 0 else 0.0
        speed_mean = np.mean([speed_upper, speed_lower])

        is_closing = (np.mean(dy_upper) > 0) and (np.mean(dy_lower) > 0)

        if debug and img0 is not None and imgT is not None:
            _debug_plot_wound_edges_overlay(
                img0=img0, y0_upper=y0_upper, y0_lower=y0_lower,
                yT_upper=yT_upper, yT_lower=yT_lower,
                traj_key=traj_key, t_used=t_used, img_alpha=0.7,
            )

        rows.append({
            "trajectory": traj_key,
            "t_used": t_used,
            "t_seg": t_used,  # Alias for compatibility
            "area_t0": area_t0,
            "area_tT": area_tT,
            "distance_upper": distance_upper,
            "distance_lower": distance_lower,
            "distance_mean": distance_mean,
            "speed_upper": speed_upper,
            "speed_lower": speed_lower,
            "speed_mean": speed_mean,
            "is_closing": bool(is_closing),
        })

    return pd.DataFrame(rows)


# =============================================================================
# Time selection utility
# =============================================================================

def select_closest_times(
    df: pd.DataFrame,
    group_col: str = "sample_name",
    time_col: str = "t_seg",
    target_times=(0, 3, 6, 12, 24)
) -> pd.DataFrame:
    """
    For each group, select rows closest to specified time points.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    group_col : str
        Column to group by
    time_col : str
        Time column
    target_times : tuple
        Target times to select
    
    Returns
    -------
    pd.DataFrame
        Filtered dataframe with rows closest to target times
    """
    rows = []
    for _, group in df.groupby(group_col):
        times = group[time_col].values
        for t in target_times:
            nearest_t = _find_nearest_time(times, t)
            row = group[group[time_col] == nearest_t].iloc[0]
            rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


# =============================================================================
# Plotting
# =============================================================================

def plot_speed_by_cellline_condition(
    df: pd.DataFrame,
    value_col: str = "speed_mean",
    cellline_col: str = "cell_line",
    condition_col: str = "sample_condition",
    concentration_col: str = "concentration_mm",
    figsize: tuple = (14, 4),
    palette: dict | None = None,
    bar_width: float = 0.25,
    show_points: bool = True,
    title: str | None = None,
    ylabel: str | None = None,
) -> Figure:
    """
    Plot a measure across cell lines, comparing sample conditions.
    
    Creates one subplot per concentration. X-axis = cell_line (categorical),
    bars/points grouped by sample_condition (legend).
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe filtered to a single time point.
    value_col : str
        Column to plot (speed_mean, distance_mean, area_t0, etc.)
    cellline_col : str
        Column for x-axis grouping.
    condition_col : str
        Column for bar grouping (legend).
    concentration_col : str
        Column for subplots.
    show_points : bool
        If True, overlay individual data points.
    
    Returns
    -------
    Figure
    """
    if ylabel is None:
        if "speed" in value_col:
            ylabel = f"{value_col} (pixels/hour)"
        elif "distance" in value_col:
            ylabel = f"{value_col} (pixels)"
        elif "area" in value_col:
            ylabel = f"{value_col} (pixels²)"
        else:
            ylabel = value_col

    concentrations = sorted(df[concentration_col].dropna().unique())
    cell_lines = sorted(df[cellline_col].dropna().unique())
    conditions = sorted(df[condition_col].dropna().unique())
    
    n_conc = len(concentrations)
    n_conditions = len(conditions)
    
    if palette is None:
        colors = plt.cm.tab10.colors
        palette = {cond: colors[i % len(colors)] for i, cond in enumerate(conditions)}
    
    fig, axes = plt.subplots(1, n_conc, figsize=(figsize[0], figsize[1]), sharey=True)
    if n_conc == 1:
        axes = [axes]
    
    for ax, conc in zip(axes, concentrations):
        df_conc = df[df[concentration_col] == conc]
        
        df_agg = df_conc.groupby([cellline_col, condition_col])[value_col].agg(
            ["mean", "std", "count"]
        ).reset_index()
        
        x = np.arange(len(cell_lines))
        total_width = bar_width * n_conditions
        offsets = np.linspace(-total_width/2 + bar_width/2, 
                               total_width/2 - bar_width/2, 
                               n_conditions)
        
        for i, condition in enumerate(conditions):
            df_cond = df_agg[df_agg[condition_col] == condition]
            
            means = []
            stds = []
            for cl in cell_lines:
                row = df_cond[df_cond[cellline_col] == cl]
                if not row.empty:
                    means.append(row["mean"].values[0])
                    stds.append(row["std"].values[0])
                else:
                    means.append(0)
                    stds.append(0)
            
            ax.bar(x + offsets[i], means, width=bar_width, label=condition,
                   color=palette.get(condition, f"C{i}"), alpha=0.7,
                   edgecolor="black", linewidth=0.5)
            
            ax.errorbar(x + offsets[i], means, yerr=stds, fmt="none",
                       ecolor="black", capsize=3, capthick=1)
            
            if show_points:
                df_raw = df_conc[df_conc[condition_col] == condition]
                for j, cl in enumerate(cell_lines):
                    points = df_raw[df_raw[cellline_col] == cl][value_col].values
                    if len(points) > 0:
                        jitter = np.random.uniform(-bar_width/4, bar_width/4, len(points))
                        ax.scatter(x[j] + offsets[i] + jitter, points,
                                  color=palette.get(condition, f"C{i}"),
                                  edgecolor="black", s=30, alpha=0.8, zorder=3)
        
        ax.set_xlabel("Cell Line")
        ax.set_xticks(x)
        ax.set_xticklabels(cell_lines, ha='center')
        ax.grid(axis="y", alpha=0.3)
    
    axes[0].set_ylabel(ylabel)
    axes[-1].legend(title="Condition", loc="upper right", fontsize=8)
    
    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")
    
    plt.tight_layout()
    return fig
