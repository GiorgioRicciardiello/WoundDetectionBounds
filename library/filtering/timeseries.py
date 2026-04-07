"""
Time-Series Analysis for Wound Healing Experiments
===================================================

Computes wound distance/speed for ALL available time points
(always relative to t=0) and provides plotting functions for time series data.

Functions:
- distance_calculator_timeseries: Compute metrics for all timepoints
- plot_timeseries_by_condition: Plot time series grouped by condition
- plot_timeseries_grouped: Subplots per concentration with line style per condition
"""

from pathlib import Path
from collections import OrderedDict
from typing import Dict, Tuple, Iterable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from tqdm import tqdm


# =============================================================================
# Time-series distance/speed calculator
# =============================================================================

def distance_calculator_timeseries(
    trajectories: Dict,
    debug: bool = False,
    save_path: Path | str | None = None,
    img_alpha: float = 0.3,
) -> pd.DataFrame:
    """
    Calculate wound distance/speed for ALL available time points.
    
    Reference is always t=0. For each trajectory and each timepoint t > 0,
    computes the displacement from t=0 to t.
    
    Parameters
    ----------
    trajectories : Dict
        Trajectories dictionary from the wound healing pipeline.
    debug : bool
        If True, create visualization for each trajectory showing layered
        wound edges at all timepoints (webbed pattern showing closure).
    save_path : Path | str | None
        If provided, save debug figures to this directory.
        If None, display figures interactively (plt.show()).
    img_alpha : float
        Transparency of background image (default: 0.3).
    
    Returns
    -------
    pd.DataFrame with columns:
        trajectory     - trajectory identifier
        t              - current timepoint (hours)
        area_t0        - wound area at t=0 (pixels)
        area_t         - wound area at current t (pixels)
        distance_upper - mean displacement of upper edge (pixels)
        distance_lower - mean displacement of lower edge (pixels)
        distance_mean  - mean of upper and lower (pixels)
        speed_upper    - distance_upper / t (pixels/hour)
        speed_lower    - distance_lower / t (pixels/hour)
        speed_mean     - mean speed (pixels/hour)
        is_closing     - True if both edges move inward
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

    def _debug_plot_timeseries_edges(
        img0: np.ndarray,
        y0_upper: np.ndarray,
        y0_lower: np.ndarray,
        edges_over_time: list,
        traj_key: str,
        save_path: Path | None = None,
        img_alpha: float = 0.3,
    ) -> None:
        """Debug plot showing wound edge displacement over all timepoints."""
        H, W = img0.shape
        x = np.arange(W)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.imshow(img0, cmap="gray", alpha=img_alpha)
        
        n_times = len(edges_over_time)
        cmap = plt.cm.viridis
        colors = [cmap(i / max(n_times - 1, 1)) for i in range(n_times)]
        
        valid0 = ~np.isnan(y0_upper) & ~np.isnan(y0_lower)
        ax.plot(x[valid0], y0_upper[valid0], color="black", lw=2.5, label="t=0 (reference)")
        ax.plot(x[valid0], y0_lower[valid0], color="black", lw=2.5)
        
        ax.fill_between(x, y0_upper, y0_lower, where=valid0, color="gray", alpha=0.15, label="Wound at t=0")
        
        prev_upper = y0_upper.copy()
        prev_lower = y0_lower.copy()
        
        for i, (t, yT_upper, yT_lower) in enumerate(edges_over_time):
            color = colors[i]
            valid = ~np.isnan(yT_upper) & ~np.isnan(yT_lower) & ~np.isnan(prev_upper) & ~np.isnan(prev_lower)
            
            ax.fill_between(x, prev_upper, yT_upper, where=valid, color=color, alpha=0.35)
            ax.fill_between(x, prev_lower, yT_lower, where=valid, color=color, alpha=0.35)
            ax.plot(x[valid], yT_upper[valid], color=color, lw=1.5, ls="-")
            ax.plot(x[valid], yT_lower[valid], color=color, lw=1.5, ls="-", label=f"t={t}h")
            
            prev_upper = yT_upper.copy()
            prev_lower = yT_lower.copy()
        
        ax.set_title(f"{traj_key} - Wound Closure Over Time", fontsize=12, fontweight="bold")
        ax.set_xlabel("X position (pixels)")
        ax.set_ylabel("Y position (pixels)")
        ax.set_xlim(0, W - 1)
        ax.set_ylim(H - 1, 0)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8, title="Timepoints")
        
        plt.tight_layout()
        
        if save_path is not None:
            save_path = Path(save_path)
            save_path.mkdir(parents=True, exist_ok=True)
            fig_path = save_path / f"{traj_key}_timeseries_edges.png"
            fig.savefig(fig_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()

    if save_path is not None:
        save_path = Path(save_path)

    rows = []

    for traj_key, traj_data in tqdm(
        trajectories.items(),
        desc="Computing timeseries metrics",
        total=len(trajectories),
    ):
        results = traj_data.get("results", [])
        if len(results) == 0:
            continue

        times = sorted([r.get("t") for r in results if r.get("t") is not None])
        if 0 not in times:
            continue

        r0 = next(r for r in results if r.get("t") == 0)
        mask0 = r0.get("mask")
        img0 = r0.get("img_raw")
        if mask0 is None:
            continue

        area_t0 = int(np.asarray(mask0).astype(bool).sum())
        y0_upper, y0_lower = extract_wound_edges_y(np.asarray(mask0))

        rows.append({
            "trajectory": traj_key,
            "t": 0,
            "area_t0": area_t0,
            "area_t": area_t0,
            "distance_upper": 0.0,
            "distance_lower": 0.0,
            "distance_mean": 0.0,
            "speed_upper": 0.0,
            "speed_lower": 0.0,
            "speed_mean": 0.0,
            "is_closing": False,
        })

        edges_over_time = []

        for t in times:
            if t == 0:
                continue

            rT = next((r for r in results if r.get("t") == t), None)
            if rT is None:
                continue

            maskT = rT.get("mask")
            if maskT is None:
                continue

            area_t = int(np.asarray(maskT).astype(bool).sum())
            yT_upper, yT_lower = extract_wound_edges_y(np.asarray(maskT))

            edges_over_time.append((t, yT_upper.copy(), yT_lower.copy()))

            valid_upper = ~np.isnan(y0_upper) & ~np.isnan(yT_upper)
            valid_lower = ~np.isnan(y0_lower) & ~np.isnan(yT_lower)

            if valid_upper.sum() == 0 or valid_lower.sum() == 0:
                continue

            # Sign convention: positive = closing (inward movement)
            # Upper edge closing: yT > y0 (moves down in image coords)
            # Lower edge closing: yT < y0 (moves up in image coords)
            dy_upper = yT_upper[valid_upper] - y0_upper[valid_upper]
            dy_lower = y0_lower[valid_lower] - yT_lower[valid_lower]

            distance_upper = np.mean(np.abs(dy_upper))
            distance_lower = np.mean(np.abs(dy_lower))
            distance_mean = np.mean([distance_upper, distance_lower])

            # NOTE: dt is the frame index, not hours.  Speed units are
            # px/frame.  Convert to px/h using imaging interval metadata.
            dt = float(t)
            speed_upper = distance_upper / dt if dt > 0 else 0.0
            speed_lower = distance_lower / dt if dt > 0 else 0.0
            speed_mean = np.mean([speed_upper, speed_lower])

            is_closing = (np.mean(dy_upper) > 0) and (np.mean(dy_lower) > 0)

            rows.append({
                "trajectory": traj_key,
                "t": t,
                "area_t0": area_t0,
                "area_t": area_t,
                "distance_upper": distance_upper,
                "distance_lower": distance_lower,
                "distance_mean": distance_mean,
                "speed_upper": speed_upper,
                "speed_lower": speed_lower,
                "speed_mean": speed_mean,
                "is_closing": bool(is_closing),
            })

        if debug and img0 is not None and len(edges_over_time) > 0:
            _debug_plot_timeseries_edges(
                img0=np.asarray(img0),
                y0_upper=y0_upper,
                y0_lower=y0_lower,
                edges_over_time=edges_over_time,
                traj_key=traj_key,
                save_path=save_path,
                img_alpha=img_alpha,
            )

    return pd.DataFrame(rows)


# =============================================================================
# Time-series plotting
# =============================================================================

def plot_timeseries_by_condition(
    df: pd.DataFrame,
    value_col: str = "distance_mean",
    time_col: str = "t",
    group_col: str = "sample_condition",
    facet_col: str | None = "cell_line",
    concentration: float | Iterable[float] | None = None,
    concentration_col: str = "concentration_mm",
    figsize: tuple = (12, 4),
    show_individual: bool = False,
    show_error: bool = True,
    use_sem: bool = True,
    palette: dict | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    save_path: Path | str | None = None,
) -> Figure:
    """
    Plot time series grouped by condition with optional facets.
    
    Parameters
    ----------
    df : pd.DataFrame
        Long-format dataframe with time series data.
    value_col : str
        Column to plot (e.g., distance_mean, speed_mean).
    time_col : str
        Time axis column.
    group_col : str
        Grouping variable for color/legend.
    facet_col : str | None
        Faceting variable.
    concentration : float | Iterable[float] | None
        Filter to specific concentration(s).
    concentration_col : str
        Concentration column name.
    show_individual : bool
        Show individual trajectory lines.
    show_error : bool
        Show error band.
    use_sem : bool
        Use SEM if True, else STD.
    
    Returns
    -------
    matplotlib.figure.Figure
    """
    if concentration is None:
        concentrations = [None]
    elif isinstance(concentration, (list, tuple, set, np.ndarray)):
        concentrations = list(concentration)
    else:
        concentrations = [concentration]

    if ylabel is None:
        if "speed" in value_col:
            ylabel = f"{value_col} (pixels/hour)"
        elif "distance" in value_col:
            ylabel = f"{value_col} (pixels)"
        elif "area" in value_col:
            ylabel = f"{value_col} (pixels²)"
        else:
            ylabel = value_col

    groups = sorted(df[group_col].dropna().unique())
    if palette is None:
        colors = plt.cm.tab10.colors
        palette = {g: colors[i % len(colors)] for i, g in enumerate(groups)}

    n_conc = len(concentrations)
    fig, axes = plt.subplots(1, n_conc, figsize=(figsize[0] * n_conc, figsize[1]), sharey=True)
    if n_conc == 1:
        axes = [axes]

    error_type = "SEM" if use_sem else "STD"

    for ax, conc in zip(axes, concentrations):
        if conc is not None:
            df_c = df[df[concentration_col] == conc].copy()
            ax.set_title(f"{concentration_col} = {conc}")
        else:
            df_c = df.copy()
            ax.set_title("All concentrations")

        if df_c.empty:
            continue

        for group in groups:
            df_group = df_c[df_c[group_col] == group]
            if df_group.empty:
                continue

            if show_individual and "trajectory" in df_group.columns:
                for _, df_traj in df_group.groupby("trajectory"):
                    df_traj = df_traj.sort_values(time_col)
                    ax.plot(df_traj[time_col], df_traj[value_col], color=palette[group], alpha=0.15, linewidth=0.8)

            df_agg = df_group.groupby(time_col)[value_col].agg(["mean", "std", "count"]).reset_index()

            t_vals = df_agg[time_col].to_numpy()
            means = df_agg["mean"].to_numpy()
            stds = df_agg["std"].to_numpy()
            counts = df_agg["count"].to_numpy()
            errors = stds / np.sqrt(counts) if use_sem else stds

            ax.plot(t_vals, means, color=palette[group], linewidth=2, marker="o", markersize=4, label=group)

            if show_error and np.any(~np.isnan(errors)):
                ax.fill_between(t_vals, means - errors, means + errors, color=palette[group], alpha=0.2)

        ax.set_xlabel("Time (hours)")
        ax.grid(True, alpha=0.3)
        ax.legend(title=f"{group_col} (±{error_type})", loc="upper right", fontsize=8)

    axes[0].set_ylabel(ylabel)

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")

    plt.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    return fig


def plot_timeseries_grouped(
    df: pd.DataFrame,
    value_col: str = "distance_mean",
    time_col: str = "t",
    cellline_col: str = "cell_line",
    condition_col: str = "sample_condition",
    concentration_col: str = "concentration_mm",
    figsize: tuple = (14, 5),
    show_error: bool = True,
    use_sem: bool = True,
    title: str | None = None,
    ylabel: str | None = None,
    save_path: Path | str | None = None,
) -> Figure:
    """
    Plot time series with subplots per concentration.
    
    - One subplot per concentration
    - Color encodes cell line (globally consistent)
    - Line style encodes condition (globally consistent)
    
    Parameters
    ----------
    df : pd.DataFrame
        Long-format dataframe with time series data.
    value_col : str
        Column to plot (e.g., distance_mean, speed_mean).
    time_col : str
        Time axis column.
    cellline_col : str
        Cell line grouping (color).
    condition_col : str
        Condition grouping (line style).
    concentration_col : str
        Faceting variable (one subplot per concentration).
    figsize : tuple
        Figure size.
    show_error : bool
        Show error band (SEM or STD).
    use_sem : bool
        If True use SEM, else STD.
    
    Returns
    -------
    matplotlib.figure.Figure
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

    base_colors = plt.cm.tab10.colors
    cellline_colors = {cl: base_colors[i % len(base_colors)] for i, cl in enumerate(cell_lines)}

    line_styles = ["-", "--", ":", "-."]
    condition_styles = {cond: line_styles[i % len(line_styles)] for i, cond in enumerate(conditions)}

    alphas = np.linspace(1.0, 0.5, max(len(conditions), 1))
    condition_alphas = {cond: alphas[i] for i, cond in enumerate(conditions)}

    fig, axes = plt.subplots(1, n_conc, figsize=figsize, sharey=True)
    if n_conc == 1:
        axes = [axes]

    for ax, conc in zip(axes, concentrations):
        df_conc = df[df[concentration_col] == conc]
        legend_handles = OrderedDict()

        for cell_line in cell_lines:
            base_color = cellline_colors[cell_line]

            for condition in conditions:
                df_group = df_conc[(df_conc[cellline_col] == cell_line) & (df_conc[condition_col] == condition)]

                if df_group.empty:
                    continue

                df_agg = df_group.groupby(time_col)[value_col].agg(["mean", "std", "count"]).reset_index()

                t_vals = df_agg[time_col].to_numpy()
                means = df_agg["mean"].to_numpy()
                stds = df_agg["std"].to_numpy()
                counts = df_agg["count"].to_numpy()
                errors = stds / np.sqrt(counts) if use_sem else stds

                alpha = condition_alphas[condition]
                linestyle = condition_styles[condition]

                ax.plot(t_vals, means, color=base_color, linestyle=linestyle, linewidth=2, alpha=alpha, marker="o", markersize=3)

                if show_error and np.any(~np.isnan(errors)):
                    ax.fill_between(t_vals, means - errors, means + errors, color=base_color, alpha=0.15 * alpha, linewidth=0)

                key = (cell_line, condition)
                if key not in legend_handles:
                    legend_handles[key] = Line2D(
                        [0], [0], color=base_color, linestyle=linestyle, linewidth=2, alpha=alpha,
                        marker="o", markersize=4, label=f"{cell_line} - {condition}"
                    )

        ax.set_title(f"Concentration: {conc}")
        ax.set_xlabel("Time (hours)")
        ax.grid(True, alpha=0.3)

        if legend_handles:
            ax.legend(handles=list(legend_handles.values()), fontsize=7, loc="upper left", frameon=False)

    axes[0].set_ylabel(ylabel)

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")

    plt.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    return fig
