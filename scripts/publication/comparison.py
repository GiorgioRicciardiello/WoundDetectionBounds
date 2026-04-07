"""
Method Comparison Functions
===========================

Comparison-specific functions for Kalman vs Hard constraint method analysis.
Generates side-by-side comparison tables and figures.

These functions are imported and used by scripts.generate_reporting when
ReportingConfig.do_comparison = True.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from scripts.publication.generate_figures import (
    compute_pairwise_vs_dmso,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Display conditions (candesartan excluded)
ALLOWED_CONDITIONS = ["DMSO", "Media", "Alk5i"]


# ---------------------------------------------------------------------------
# Summary and comparison functions
# ---------------------------------------------------------------------------

def summary_row(
    method_key: str,
    df_ts: pd.DataFrame,
    df_cs: pd.DataFrame,
    df_qc: pd.DataFrame,
    traj_filt: Dict,
    t_final: float,
) -> Dict:
    """Compute summary statistics for one method.

    Parameters
    ----------
    method_key : str
        'kalman' or 'hard'.
    df_ts : pd.DataFrame
        Time-series data.
    df_cs : pd.DataFrame
        Cross-sectional data.
    df_qc : pd.DataFrame
        QC table.
    traj_filt : dict
        Filtered trajectories.
    t_final : float
        Cross-sectional target timepoint.

    Returns
    -------
    dict
        Summary statistics including method label, trajectory count,
        QC pass rate, constraint rate, and closure metrics.
    """
    from scripts.generate_reporting import METHODS

    n_traj = len(traj_filt)
    n_qc_pass = int(df_qc["qc_t0_valid"].sum())
    qc_rate = 100.0 * n_qc_pass / max(n_traj, 1)

    constraint_rate = 100.0 * df_qc["constraint_rate"].mean()

    mean_area_t0 = df_cs["area_t0"].mean() if "area_t0" in df_cs.columns else np.nan
    mean_area_tT = df_cs["area_tT"].mean() if "area_tT" in df_cs.columns else np.nan
    mean_distance = df_cs["distance_mean"].mean() if len(df_cs) > 0 else np.nan
    mean_speed = df_cs["speed_mean"].mean() if len(df_cs) > 0 else np.nan
    std_distance = df_cs["distance_mean"].std() if len(df_cs) > 0 else np.nan
    std_speed = df_cs["speed_mean"].std() if len(df_cs) > 0 else np.nan

    closing_rate = 100.0 * df_cs["is_closing"].mean() if len(df_cs) > 0 else np.nan

    return {
        "method": METHODS[method_key]["label"],
        "n_trajectories": n_traj,
        "n_qc_pass": n_qc_pass,
        "qc_pass_rate_%": round(qc_rate, 1),
        "constraint_rate_%": round(constraint_rate, 1),
        "mean_area_t0_px": round(mean_area_t0, 0),
        f"mean_area_t{int(t_final)}_px": round(mean_area_tT, 0),
        "mean_distance_px": round(mean_distance, 2),
        "std_distance_px": round(std_distance, 2),
        "mean_speed_px_per_frame": round(mean_speed, 2),
        "std_speed_px_per_frame": round(std_speed, 2),
        "closing_rate_%": round(closing_rate, 1),
        "n_cs_trajectories": len(df_cs),
        "n_ts_rows": len(df_ts),
        "t_final": t_final,
    }


def per_group_comparison(
    df_cs_kalman: pd.DataFrame,
    df_cs_hard: pd.DataFrame,
) -> pd.DataFrame:
    """Per cell_line x condition comparison between methods.

    Parameters
    ----------
    df_cs_kalman : pd.DataFrame
        Cross-sectional data for Kalman method.
    df_cs_hard : pd.DataFrame
        Cross-sectional data for hard constraint method.

    Returns
    -------
    pd.DataFrame
        Columns: cell_line, condition, metric, kalman_mean, hard_mean,
        diff, diff_pct.
    """
    rows = []
    group_cols = ["cell_line", "sample_condition"]
    metrics = ["distance_mean", "speed_mean"]

    for (cl, cond), grp_k in df_cs_kalman.groupby(group_cols):
        grp_h = df_cs_hard[
            (df_cs_hard["cell_line"] == cl)
            & (df_cs_hard["sample_condition"] == cond)
        ]
        if grp_h.empty:
            continue

        for metric in metrics:
            k_mean = grp_k[metric].mean()
            h_mean = grp_h[metric].mean()
            diff = k_mean - h_mean
            diff_pct = 100.0 * diff / (h_mean + 1e-12)

            rows.append({
                "cell_line": cl,
                "condition": cond,
                "metric": metric,
                "kalman_mean": round(k_mean, 3),
                "hard_mean": round(h_mean, 3),
                "diff": round(diff, 3),
                "diff_pct": round(diff_pct, 2),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Comparison figure
# ---------------------------------------------------------------------------

def generate_comparison_figure(
    df_cs_kalman: pd.DataFrame,
    df_cs_hard: pd.DataFrame,
    df_ts_kalman: pd.DataFrame,
    df_ts_hard: pd.DataFrame,
    output_dir: Path,
    t_final: float,
) -> None:
    """Generate a side-by-side comparison figure.

    Layout:
        [A] Distance bar chart: Kalman vs Hard per cell_line x condition
        [B] Speed bar chart: Kalman vs Hard
        [C] Time-series overlay: Kalman (solid) vs Hard (dashed)

    Parameters
    ----------
    df_cs_kalman : pd.DataFrame
        Cross-sectional data for Kalman method.
    df_cs_hard : pd.DataFrame
        Cross-sectional data for hard constraint method.
    df_ts_kalman : pd.DataFrame
        Time-series data for Kalman method.
    df_ts_hard : pd.DataFrame
        Time-series data for hard constraint method.
    output_dir : Path
        Output directory for the figure.
    t_final : float
        Cross-sectional target timepoint.
    """
    plt.rcParams.update({"font.family": "Arial", "font.size": 10})

    fig = plt.figure(figsize=(16, 5))
    gs = GridSpec(1, 3, figure=fig, wspace=0.35)

    cell_lines = sorted(df_cs_kalman["cell_line"].dropna().unique())
    conditions = [c for c in ALLOWED_CONDITIONS if c in df_cs_kalman["sample_condition"].unique()]

    # --- Panel A: Distance comparison ---
    ax_dist = fig.add_subplot(gs[0, 0])
    paired_bar(ax_dist, df_cs_kalman, df_cs_hard, "distance_mean",
                cell_lines, conditions,
                ylabel="Distance (px)", title=f"Closure Distance (t={int(t_final)})")
    ax_dist.text(-0.12, 1.05, "A", transform=ax_dist.transAxes,
                 fontsize=14, fontweight="bold", va="top")

    # --- Panel B: Speed comparison ---
    ax_speed = fig.add_subplot(gs[0, 1])
    paired_bar(ax_speed, df_cs_kalman, df_cs_hard, "speed_mean",
                cell_lines, conditions,
                ylabel="Speed (px/frame)", title=f"Closure Speed (t={int(t_final)})")
    ax_speed.text(-0.12, 1.05, "B", transform=ax_speed.transAxes,
                  fontsize=14, fontweight="bold", va="top")

    # --- Panel C: Time-series overlay ---
    ax_ts = fig.add_subplot(gs[0, 2])
    timeseries_overlay(ax_ts, df_ts_kalman, df_ts_hard, cell_lines, conditions)
    ax_ts.text(-0.12, 1.05, "C", transform=ax_ts.transAxes,
               fontsize=14, fontweight="bold", va="top")

    for ext in ("png", "pdf"):
        out = output_dir / f"method_comparison.{ext}"
        save_kw = {"bbox_inches": "tight"}
        if ext == "png":
            save_kw["dpi"] = 300
        fig.savefig(out, **save_kw)
        print(f"[OK] Saved: {out}")
    plt.close(fig)


def paired_bar(
    ax: plt.Axes,
    df_k: pd.DataFrame,
    df_h: pd.DataFrame,
    value_col: str,
    cell_lines: List[str],
    conditions: List[str],
    ylabel: str = "",
    title: str = "",
) -> None:
    """Grouped bar chart comparing Kalman vs Hard for each group.

    Parameters
    ----------
    ax : plt.Axes
        Matplotlib axes to draw on.
    df_k : pd.DataFrame
        Kalman method data.
    df_h : pd.DataFrame
        Hard constraint method data.
    value_col : str
        Column name to plot (e.g. 'distance_mean').
    cell_lines : list of str
        Cell line names to include.
    conditions : list of str
        Condition names to include.
    ylabel : str
        Y-axis label.
    title : str
        Subplot title.
    """
    bar_width = 0.15
    x = np.arange(len(cell_lines))
    n_cond = len(conditions)

    for i, cond in enumerate(conditions):
        offset_base = (i - (n_cond - 1) / 2) * (2 * bar_width + 0.04)

        means_k, means_h, sems_k, sems_h = [], [], [], []
        for cl in cell_lines:
            vals_k = df_k[(df_k["cell_line"] == cl) & (df_k["sample_condition"] == cond)][value_col]
            vals_h = df_h[(df_h["cell_line"] == cl) & (df_h["sample_condition"] == cond)][value_col]
            means_k.append(vals_k.mean() if len(vals_k) > 0 else 0)
            means_h.append(vals_h.mean() if len(vals_h) > 0 else 0)
            sems_k.append(vals_k.sem() if len(vals_k) > 1 else 0)
            sems_h.append(vals_h.sem() if len(vals_h) > 1 else 0)

        ax.bar(x + offset_base - bar_width / 2, means_k, bar_width,
               yerr=sems_k, color="#0072B2", alpha=0.7 - 0.15 * i,
               edgecolor="black", linewidth=0.5, capsize=2,
               label=f"{cond} Kalman" if i == 0 or True else "")
        ax.bar(x + offset_base + bar_width / 2, means_h, bar_width,
               yerr=sems_h, color="#E69F00", alpha=0.7 - 0.15 * i,
               edgecolor="black", linewidth=0.5, capsize=2,
               label=f"{cond} Hard" if i == 0 or True else "")

    ax.set_xticks(x)
    ax.set_xticklabels(cell_lines, fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold", fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Compact legend
    handles, labels = ax.get_legend_handles_labels()
    # Deduplicate
    seen = set()
    unique_h, unique_l = [], []
    for h, l in zip(handles, labels):
        if l not in seen:
            seen.add(l)
            unique_h.append(h)
            unique_l.append(l)
    ax.legend(unique_h, unique_l, fontsize=6, ncol=2, frameon=False, loc="upper right")


def timeseries_overlay(
    ax: plt.Axes,
    df_ts_k: pd.DataFrame,
    df_ts_h: pd.DataFrame,
    cell_lines: List[str],
    conditions: List[str],
) -> None:
    """Overlay Kalman (solid) and Hard (dashed) time-series.

    Parameters
    ----------
    ax : plt.Axes
        Matplotlib axes to draw on.
    df_ts_k : pd.DataFrame
        Time-series data for Kalman method.
    df_ts_h : pd.DataFrame
        Time-series data for hard constraint method.
    cell_lines : list of str
        Cell line names to include.
    conditions : list of str
        Condition names to include.
    """
    colors = {"Line 1": "#0072B2", "Line 2": "#E69F00"}

    for cl in cell_lines:
        for cond in conditions:
            color = colors.get(cl, "#999999")

            for df, ls, method_label in [(df_ts_k, "-", "K"), (df_ts_h, "--", "H")]:
                sub = df[(df["cell_line"] == cl) & (df["sample_condition"] == cond)]
                if sub.empty:
                    continue
                g = sub.groupby("t")["distance_mean"]
                ts_mean = g.mean()
                ts_sem = g.sem()

                ax.plot(ts_mean.index, ts_mean.values,
                        color=color, linestyle=ls, linewidth=1.5, alpha=0.8,
                        label=f"{cl} {cond} ({method_label})")
                ax.fill_between(
                    ts_mean.index,
                    ts_mean.values - 1.96 * ts_sem.values,
                    ts_mean.values + 1.96 * ts_sem.values,
                    color=color, alpha=0.08,
                )

    ax.set_xlabel("Time (frames)")
    ax.set_ylabel("Distance (px)")
    ax.set_title("Edge Displacement (solid=Kalman, dashed=Hard)",
                 fontweight="bold", fontsize=11)
    ax.grid(alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=5, ncol=2, frameon=False, loc="upper left")
