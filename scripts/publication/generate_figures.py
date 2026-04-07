"""
Publication Figure Generator
============================

Generates publication-quality figures from the Quantification wound healing model
results. Uses only the Quantification model (Quantification_results folder). Candesartan
is excluded from all analyses; conditions shown are DMSO, Media, Alk5i.
Analysis is fixed to concentration ANALYSIS_CONCENTRATION_MM (default 0.1 mM).

Output directory: paper_publication/

Figures generated
-----------------
fig1_model_quality.png + .pdf
    Panel A-C : Representative timelapse with wound boundaries + scale bar.
    Panel D   : QC pass rate at t=0 per condition x cell line.
    Panel E   : Monotonic constraint rate per condition x cell line.
    Panel F   : Normalised wound area closure over time (95% CI).

fig2_wound_dynamics.png + .pdf
    Panel A   : Cross-sectional speed with significance brackets.
    Panel B   : Cross-sectional distance with significance brackets.
    Panel C   : Time series of wound edge displacement (95% CI).

tables/statistics.xlsx, tables/supplementary_tables.xlsx, figure_captions.txt

Usage
-----
Run as a script from the project root:
    python -m scripts.publication.generate_figures
"""

from __future__ import annotations

import pickle
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from scipy import stats as sp_stats

from config.config import config
from library.filtering.cross_sectional import distance_calculator
from library.filtering.timeseries import distance_calculator_timeseries
from scripts.publication.figure_panels import (
    CELL_LINE_COLORS,
    CONDITION_ORDER,
    panel_crosssectional_bar,
    panel_image_with_borders,
    panel_image_with_closures,
    panel_normalized_area,
    panel_timeseries_distance,
)
from scripts.publication.generate_tables import (
    export_figure_captions,
    export_statistics_tables,
    export_supplementary_tables,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL_KEY: str = "Quantification_results"

# Conditions to keep (candesartan excluded)
_KEEP_CONDITIONS_RAW: List[str] = ["media", "dmso", "alk5i"]

# Fixed concentration for all analyses (mM)
ANALYSIS_CONCENTRATION_MM: float = 0.1

# Mapping: raw label -> display label
_CONDITION_RENAME: Dict[str, str] = {
    "media": "Media",
    "dmso":  "DMSO",
    "alk5i": "Alk5i",
}
_CELLLINE_RENAME: Dict[str, str] = {
    "iMC MUTR544C": "Line 2",
    "iMC ISOR544C": "Line 1",
}

GLOBAL_COLOR_MAP: Dict[str, str] = CELL_LINE_COLORS

# Default error type for publication figures
_ERROR_TYPE: str = "ci95"
UM_PER_PIXEL: float = 1.24


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_quantification_results(
    traj_path: Path,
    table_path: Path,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Load the Quantification model outputs: legacy table and trajectory dictionary.

    Parameters
    ----------
    traj_path : Path
        Path to the trajectories pickle file.
    table_path : Path
        Path to the final legacy table Excel file.

    Returns
    -------
    df_legacy : pd.DataFrame
        Final aggregated legacy table.
    trajectories : dict
        Trajectories keyed by identifier string.

    Raises
    ------
    FileNotFoundError
        If either required file is missing.
    """
    if not traj_path.exists():
        raise FileNotFoundError(f"Trajectories not found: {traj_path}")
    if not table_path.exists():
        raise FileNotFoundError(f"Legacy table not found: {table_path}")

    with traj_path.open("rb") as f:
        trajectories: Dict = pickle.load(f)

    df_legacy = pd.read_excel(table_path)
    return df_legacy, trajectories


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def rename_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename raw cell line and condition labels to display-ready strings.

    Cell line: iMC MUTR544C -> Line 2, iMC ISOR544C -> Line 1
    Condition: media/dmso/alk5i -> Media/DMSO/Alk5i

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with cell_line and sample_condition columns.

    Returns
    -------
    pd.DataFrame
        New DataFrame with renamed columns (no in-place mutation).
    """
    df = df.copy()
    df["cell_line"] = df["cell_line"].map(_CELLLINE_RENAME).fillna(df["cell_line"])
    df["sample_condition"] = (
        df["sample_condition"].str.lower()
        .map(_CONDITION_RENAME)
        .fillna(df["sample_condition"])
    )
    return df


def filter_candesartan(
    df: pd.DataFrame,
    trajectories: Dict,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Remove candesartan exposures from both the DataFrame and trajectory dict.

    Parameters
    ----------
    df : pd.DataFrame
        Legacy table (may have raw or renamed condition values).
    trajectories : dict
        Full trajectories dict.

    Returns
    -------
    df_filtered : pd.DataFrame
        Table with candesartan rows removed.
    traj_filtered : dict
        Trajectories with candesartan entries removed.
    """
    cond_col = df["sample_condition"].str.lower()
    mask_keep = cond_col.isin(_KEEP_CONDITIONS_RAW) | cond_col.isin(
        [v.lower() for v in _CONDITION_RENAME.values()]
    )
    df_filtered = df.loc[mask_keep].copy()

    traj_filtered = {
        k: v for k, v in trajectories.items()
        if not k.endswith("-Candasertan") and not k.endswith("-candasertan")
    }

    n_removed_rows = len(df) - len(df_filtered)
    n_removed_traj = len(trajectories) - len(traj_filtered)
    print(
        f"[filter_candesartan] Removed {n_removed_rows} rows, "
        f"{n_removed_traj} trajectories."
    )
    return df_filtered, traj_filtered


def compute_qc_constraint_table(
    trajectories: Dict,
    df_meta: pd.DataFrame,
    identifier_col: str = "identifier",
) -> pd.DataFrame:
    """
    Compute per-trajectory QC validity and constraint rate, merged with metadata.

    Parameters
    ----------
    trajectories : dict
        Trajectories after candesartan filtering.
    df_meta : pd.DataFrame
        Metadata table with identifier, cell_line, sample_condition columns.
    identifier_col : str
        Column name for trajectory identifier in df_meta.

    Returns
    -------
    pd.DataFrame
        One row per trajectory with columns:
        identifier, qc_t0_valid, constraint_rate, cell_line, sample_condition.
    """
    rows = []
    for traj_key, traj_data in trajectories.items():
        results = traj_data.get("results", [])
        if not results:
            continue

        t0 = next((r for r in results if r.get("t") == 0), None)
        qc_valid = bool(t0.get("qc", {}).get("valid", False)) if t0 is not None else False

        constrained_flags = [
            r.get("constrained", False)
            for r in results
            if r.get("t", 0) > 0
        ]
        constraint_rate = (
            float(np.mean(constrained_flags)) if constrained_flags else np.nan
        )

        rows.append({
            identifier_col: traj_key,
            "qc_t0_valid": qc_valid,
            "constraint_rate": constraint_rate,
        })

    df_qc = pd.DataFrame(rows)

    meta_unique = (
        df_meta[[identifier_col, "cell_line", "sample_condition"]]
        .drop_duplicates(subset=identifier_col)
    )
    df_qc = df_qc.merge(meta_unique, on=identifier_col, how="left")
    return df_qc


def select_representative_trajectory(
    trajectories: Dict,
    df_meta: pd.DataFrame,
    cell_line: str,
    condition: str,
    identifier_col: str = "identifier",
) -> Optional[str]:
    """
    Select the most average trajectory for a given cell line and condition.

    Selection criterion: among QC-passing trajectories (t=0 QC valid, ≥3
    timepoints), find the one whose normalised area curve (area(t)/area(t=0))
    is closest to the population mean curve, measured by mean squared error
    over the timepoints shared with the majority of trajectories.

    This ensures the panel shows a biologically representative sample rather
    than an outlier (best or worst closure).

    Parameters
    ----------
    trajectories : dict
        Filtered trajectories dict.
    df_meta : pd.DataFrame
        Metadata with renamed cell_line and sample_condition.
    cell_line : str
        Display name (e.g. 'Line 1').
    condition : str
        Display name (e.g. 'DMSO').
    identifier_col : str
        Column name for trajectory identifier in df_meta.

    Returns
    -------
    str | None
        Key of the most average trajectory, or None if no candidates found.
    """
    candidate_ids = (
        df_meta.loc[
            (df_meta["cell_line"] == cell_line)
            & (df_meta["sample_condition"] == condition),
            identifier_col,
        ]
        .unique()
    )

    # ------------------------------------------------------------------
    # Step 1: Build normalised area series for each valid candidate.
    # norm_series[key] = {t_value: norm_area}
    # ------------------------------------------------------------------
    norm_series: Dict[str, Dict[float, float]] = {}

    for key in candidate_ids:
        traj = trajectories.get(key)
        if traj is None:
            continue
        results = traj.get("results", [])
        if len(results) < 3:
            continue

        t0_result = next((r for r in results if r.get("t") == 0), None)
        if t0_result is None or not t0_result.get("qc", {}).get("valid", False):
            continue

        area_t0 = t0_result.get("area") or (
            np.asarray(t0_result["mask"]).astype(bool).sum()
            if t0_result.get("mask") is not None else None
        )
        if area_t0 is None or area_t0 == 0:
            continue

        series: Dict[float, float] = {}
        for r in results:
            t_val = r.get("t")
            if t_val is None:
                continue
            area = r.get("area") or (
                np.asarray(r["mask"]).astype(bool).sum()
                if r.get("mask") is not None else None
            )
            if area is not None:
                series[float(t_val)] = float(area) / float(area_t0)

        if len(series) >= 3:
            norm_series[key] = series

    if not norm_series:
        return None

    # ------------------------------------------------------------------
    # Step 2: Compute the population mean curve over shared timepoints.
    # Use timepoints present in at least half of the candidates.
    # ------------------------------------------------------------------
    from collections import Counter

    t_counts: Counter = Counter()
    for series in norm_series.values():
        t_counts.update(series.keys())

    min_presence = max(1, len(norm_series) // 2)
    shared_t = sorted(t for t, cnt in t_counts.items() if cnt >= min_presence)

    if not shared_t:
        # Fallback: use all timepoints present in any trajectory
        shared_t = sorted(t_counts.keys())

    # Mean normalised area at each shared timepoint
    mean_curve: Dict[float, float] = {}
    for t in shared_t:
        values = [s[t] for s in norm_series.values() if t in s]
        mean_curve[t] = float(np.mean(values))

    # ------------------------------------------------------------------
    # Step 3: Select the candidate with minimum MSE vs. the mean curve.
    # ------------------------------------------------------------------
    best_key: Optional[str] = None
    best_mse: float = np.inf

    for key, series in norm_series.items():
        common = [t for t in shared_t if t in series]
        if not common:
            continue
        mse = float(np.mean(
            [(series[t] - mean_curve[t]) ** 2 for t in common]
        ))
        if mse < best_mse:
            best_mse = mse
            best_key = key

    return best_key


def pick_timelapse_timepoints(
    results: List[Dict],
    n_points: int = 3,
) -> List[Dict]:
    """
    Select approximately evenly spaced timepoints from a trajectory's results.

    Parameters
    ----------
    results : list of dict
        Trajectory results.
    n_points : int
        Number of timepoints to select (default 3: start, mid, end).

    Returns
    -------
    list of dict
        Selected result dicts.
    """
    results_sorted = sorted(
        [r for r in results if r.get("t") is not None],
        key=lambda r: r["t"],
    )
    if len(results_sorted) <= n_points:
        return results_sorted

    n = len(results_sorted)
    indices = np.round(np.linspace(0, n - 1, n_points)).astype(int)
    seen: set = set()
    selected = []
    for idx in indices:
        if idx not in seen:
            selected.append(results_sorted[idx])
            seen.add(idx)

    return selected


def _mask_area_mm2(
    mask: Optional[np.ndarray],
    um_per_pixel: float = UM_PER_PIXEL,
) -> Optional[float]:
    """
    Compute the wound area (mm²) represented by a boolean mask.
    """
    if mask is None:
        return None
    mask_bool = np.asarray(mask).astype(bool)
    pix_count = int(mask_bool.sum())
    if pix_count <= 0:
        return None
    return float(pix_count) * (um_per_pixel ** 2) / 1e6


def _format_timelapse_panel_title(
    result: Dict,
    um_per_pixel: float = UM_PER_PIXEL,
) -> str:
    """
    Build a panel title that includes the timepoint and wound area.
    """
    time_val = float(result.get("t", 0.0))
    base_title = f"t = {time_val:.0f} h"
    area_mm2 = _mask_area_mm2(result.get("mask"), um_per_pixel=um_per_pixel)
    if area_mm2 is not None:
        return f"{base_title} · A = {area_mm2:.2f} mm²"
    return base_title


# ---------------------------------------------------------------------------
# Pairwise significance tests (vs DMSO)
# ---------------------------------------------------------------------------

def compute_pairwise_vs_dmso(
    df: pd.DataFrame,
    value_col: str,
    cell_lines: Optional[List[str]] = None,
    conditions: Optional[List[str]] = None,
    control: str = "DMSO",
) -> List[Dict]:
    """
    Compute Welch's t-tests for each treatment vs DMSO, within each cell line.

    Applies Bonferroni correction across all comparisons.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain cell_line, sample_condition, and the value_col.
    value_col : str
        Column to compare (e.g. 'speed_mean', 'distance_mean').
    cell_lines : list | None
        Cell lines to include. If None, uses all unique values.
    conditions : list | None
        Treatment conditions to compare against control.
    control : str
        Control condition name (default 'DMSO').

    Returns
    -------
    list of dict
        Each dict: cell_line, condition, control, t_stat, p_raw,
        p_corrected, cohens_d, ci_lower, ci_upper, n_treatment, n_control.
    """
    if cell_lines is None:
        cell_lines = sorted(df["cell_line"].dropna().unique())
    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c != control and
                      c in df["sample_condition"].unique()]

    results_raw: List[Dict] = []

    for cl in cell_lines:
        ctrl_vals = df.loc[
            (df["cell_line"] == cl) & (df["sample_condition"] == control),
            value_col,
        ].dropna().values

        if len(ctrl_vals) < 2:
            continue

        for cond in conditions:
            treat_vals = df.loc[
                (df["cell_line"] == cl) & (df["sample_condition"] == cond),
                value_col,
            ].dropna().values

            if len(treat_vals) < 2:
                continue

            t_stat, p_raw = sp_stats.ttest_ind(treat_vals, ctrl_vals, equal_var=False)

            # Cohen's d (pooled SD)
            n_t, n_c = len(treat_vals), len(ctrl_vals)
            pooled_sd = np.sqrt(
                ((n_t - 1) * np.var(treat_vals, ddof=1)
                 + (n_c - 1) * np.var(ctrl_vals, ddof=1))
                / (n_t + n_c - 2)
            )
            cohens_d = (np.mean(treat_vals) - np.mean(ctrl_vals)) / (pooled_sd + 1e-12)

            # 95% CI of the mean difference
            mean_diff = np.mean(treat_vals) - np.mean(ctrl_vals)
            se_diff = np.sqrt(np.var(treat_vals, ddof=1) / n_t
                              + np.var(ctrl_vals, ddof=1) / n_c)
            ci_lower = mean_diff - 1.96 * se_diff
            ci_upper = mean_diff + 1.96 * se_diff

            results_raw.append({
                "cell_line": cl,
                "condition": cond,
                "control": control,
                "t_stat": float(t_stat),
                "p_raw": float(p_raw),
                "cohens_d": float(cohens_d),
                "ci_lower": float(ci_lower),
                "ci_upper": float(ci_upper),
                "n_treatment": n_t,
                "n_control": n_c,
            })

    # Bonferroni correction
    n_comparisons = max(len(results_raw), 1)
    for r in results_raw:
        r["p_corrected"] = min(r["p_raw"] * n_comparisons, 1.0)

    return results_raw


# ---------------------------------------------------------------------------
# Helper: dual-format figure export
# ---------------------------------------------------------------------------

def _save_figure(
    fig: plt.Figure,
    output_dir: Path,
    name: str,
    dpi: int = 300,
) -> None:
    """
    Save a figure as both PNG (raster, 300 DPI) and PDF (vector).

    Parameters
    ----------
    fig : Figure
        Matplotlib figure to save.
    output_dir : Path
        Destination directory.
    name : str
        Base filename without extension.
    dpi : int
        DPI for PNG export.
    """
    for ext in ("png", "pdf"):
        out_path = output_dir / f"{name}.{ext}"
        save_kwargs = {"bbox_inches": "tight"}
        if ext == "png":
            save_kwargs["dpi"] = dpi
        fig.savefig(out_path, **save_kwargs)
        print(f"[OK] Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 1: Model detection quality
# ---------------------------------------------------------------------------

def generate_fig1_model_quality(
    trajectories: Dict,
    df_meta: pd.DataFrame,
    df_qc: pd.DataFrame,
    output_dir: Path,
    dpi: int = 300,
    font_scale: float = 1.0,
    panel_d_span: Tuple[float, float] = (0.17, 0.83),
    show_error_band: bool = False,
) -> Optional[str]:
    """
    Generate Figure 1: Model Detection Quality.

    Layout (2 rows x 3 columns)
    ----------------------------
    Row 0 [A, B, C]: Three timelapse images from the same trajectory,
                     each showing ALL detected wound borders (t=0, t_mid,
                     t_final) overlaid in yellow/teal/red so the viewer
                     can track progressive closure on every panel.
                     Scale bar on the last panel.
    Row 1 [D]      : Normalised wound area (A/A0) over time. By default
                     spans from center of panel A to center of panel C.

    QC pass rate and constraint rate are reported as metrics in the
    supplementary tables, not as figure panels.

    Parameters
    ----------
    trajectories : dict
        Filtered trajectory dict (no candesartan).
    df_meta : pd.DataFrame
        Metadata with renamed labels.
    df_qc : pd.DataFrame
        QC + constraint table (used only for text reporting here).
    output_dir : Path
        Destination directory.
    dpi : int
        Output resolution for PNG.
    font_scale : float
        Global font size multiplier.
    panel_d_span : tuple of (float, float)
        Horizontal extent of Panel D in normalised figure coordinates
        (0.0 = left edge, 1.0 = right edge).  Default (0.17, 0.83)
        centres Panel D from mid-A to mid-C.  Use (0.0, 1.0) for
        full-width.

    Returns
    -------
    str | None
        Representative trajectory key used for timelapse, or None.
    """
    plt.rcParams.update({"font.family": "Arial", "font.size": 10})

    fig = plt.figure(figsize=(14, 9.4))
    gs = GridSpec(
        2, 3, figure=fig,
        height_ratios=[1.35, 0.95],
        hspace=0.38,
        wspace=0.16,
    )

    # --- Select representative trajectory ---
    rep_key = select_representative_trajectory(
        trajectories, df_meta, "Line 1", "DMSO"
    )
    if rep_key is None:
        rep_key = select_representative_trajectory(
            trajectories, df_meta, "Line 2", "DMSO"
        )
    if rep_key is None:
        warnings.warn("No representative DMSO trajectory found; skipping timelapse.")
        selected_results = []
    else:
        selected_results = pick_timelapse_timepoints(
            trajectories[rep_key]["results"], n_points=3
        )

    # --- Row 0: Interval-based closure shading ---
    # Panel A: W0 boundary only.
    # Panel B: W0 + W_mid boundaries; Δ(0→mid) blue fill.
    # Panel C: all three boundaries; Δ(0→mid) blue + Δ(mid→final) orange fills.
    panel_titles = [
        _format_timelapse_panel_title(r, um_per_pixel=UM_PER_PIXEL)
        for r in selected_results
    ]
    n_panels = len(selected_results)

    # Extract binary masks and t-values from the three selected results.
    raw_masks: List[Optional[np.ndarray]] = []
    t_values: List[float] = []
    for r in selected_results:
        m = r.get("mask")
        raw_masks.append(np.asarray(m).astype(bool) if m is not None else None)
        t_values.append(float(r.get("t", 0)))

    # Pad to length 3 so index access is safe.
    while len(raw_masks) < 3:
        raw_masks.append(None)
    while len(t_values) < 3:
        t_values.append(t_values[-1] + 12.0 if t_values else 12.0)

    mask_t0   = raw_masks[0]
    mask_tmid = raw_masks[1]
    mask_tfin = raw_masks[2]
    t_labels: Tuple[float, float, float] = (t_values[0], t_values[1], t_values[2])

    for col_idx, result in enumerate(selected_results):
        ax = fig.add_subplot(gs[0, col_idx])
        img = result.get("img_raw")

        if img is None:
            ax.axis("off")
            ax.set_title(panel_titles[col_idx], fontsize=10)
            continue

        is_last = (col_idx == n_panels - 1)
        panel_image_with_closures(
            ax=ax,
            img_raw=np.asarray(img),
            mask_t0=mask_t0,
            mask_tmid=mask_tmid if col_idx >= 1 else None,
            mask_tfinal=mask_tfin if col_idx >= 2 else None,
            t_labels=t_labels,
            title=panel_titles[col_idx],
            panel_label=chr(ord("A") + col_idx),
            font_scale=font_scale,
            show_scale_bar=is_last,
            um_per_pixel=UM_PER_PIXEL,
            scale_bar_um=200.0,
            show_legend=is_last,
        )

    if rep_key:
        fig.text(
            0.5, 0.97, f"Representative trajectory: {rep_key}",
            ha="center", va="top", fontsize=8, color="gray", style="italic",
        )

    # --- Compute mean closure percentages for panel D title ---
    df_norm = df_meta.copy()
    t0_areas_meta = (
        df_norm[df_norm["t_seg"] == 0]
        .groupby("identifier")["wound_area"]
        .first()
        .rename("area_t0")
    )
    df_norm = df_norm.merge(t0_areas_meta, on="identifier", how="left")
    df_norm["norm_area"] = df_norm["wound_area"] / (df_norm["area_t0"] + 1e-8)

    all_t_seg = sorted(df_norm["t_seg"].dropna().unique())
    t_mid_val = (
        min(all_t_seg, key=lambda t: abs(t - 12)) if all_t_seg else None
    )
    t_final_val = max(all_t_seg) if all_t_seg else None

    closure_pct_t12: Optional[float] = None
    closure_pct_t24: Optional[float] = None
    if t_mid_val is not None:
        mean_norm_mid = df_norm[df_norm["t_seg"] == t_mid_val]["norm_area"].mean()
        closure_pct_t12 = (1.0 - float(mean_norm_mid)) * 100.0
    if t_final_val is not None:
        mean_norm_fin = df_norm[df_norm["t_seg"] == t_final_val]["norm_area"].mean()
        closure_pct_t24 = (1.0 - float(mean_norm_fin)) * 100.0

    # --- Row 1: Normalised wound area ---
    # Position Panel D using normalised figure coordinates.
    # Vertical extent derived from the GridSpec row 1 bounding box.
    gs_bbox = gs[1, 0].get_position(fig)
    d_left = panel_d_span[0]
    d_right = panel_d_span[1]
    d_bottom = gs_bbox.y0
    d_top = gs_bbox.y1
    ax_area = fig.add_axes([d_left, d_bottom, d_right - d_left, d_top - d_bottom])
    panel_normalized_area(
        ax=ax_area, df_legacy=df_meta, color_map=GLOBAL_COLOR_MAP,
        panel_label="D", font_scale=font_scale * 1.1, error_type=_ERROR_TYPE,
        show_error_band=show_error_band,
        closure_pct_t12=closure_pct_t12,
        closure_pct_t24=closure_pct_t24,
        t_label_12=float(t_mid_val) if t_mid_val is not None else 12.0,
        t_label_24=float(t_final_val) if t_final_val is not None else 24.0,
    )

    _save_figure(fig, output_dir, "fig1_model_quality", dpi=dpi)
    plt.close(fig)

    return rep_key


# ---------------------------------------------------------------------------
# Figure 2: Wound healing dynamics
# ---------------------------------------------------------------------------

def generate_fig2_wound_dynamics(
    df_ts: pd.DataFrame,
    df_cs: pd.DataFrame,
    output_dir: Path,
    t_final: float = 20.0,
    speed_brackets: Optional[List[Dict]] = None,
    distance_brackets: Optional[List[Dict]] = None,
    dpi: int = 300,
    font_scale: float = 1.0,
    show_error_band: bool = False,
) -> None:
    """
    Generate Figure 2: Wound Healing Dynamics.

    Layout (2 rows x 2 columns, right column spanning both rows)
    ------------------------------------------------------------
    [A, top-left]    : Speed bar chart with significance brackets.
    [B, bottom-left] : Distance bar chart with significance brackets.
    [C, right, full] : Time series of wound edge displacement (95% CI).

    Parameters
    ----------
    df_ts : pd.DataFrame
        Time series data merged with metadata.
    df_cs : pd.DataFrame
        Cross-sectional data at t_final.
    output_dir : Path
        Destination directory.
    t_final : float
        Time label for bar chart titles.
    speed_brackets : list of dict | None
        Significance brackets for speed bar chart.
    distance_brackets : list of dict | None
        Significance brackets for distance bar chart.
    dpi : int
        Output resolution for PNG.
    font_scale : float
        Global font size multiplier.
    """
    plt.rcParams.update({"font.family": "Arial", "font.size": 10})

    fig = plt.figure(figsize=(14, 8))
    gs = GridSpec(
        2, 2, figure=fig,
        width_ratios=[1, 1.4],
        wspace=0.32, hspace=0.45,
    )

    ax_speed = fig.add_subplot(gs[0, 0])
    ax_dist = fig.add_subplot(gs[1, 0])
    ax_ts = fig.add_subplot(gs[:, 1])

    panel_crosssectional_bar(
        ax=ax_speed, df_cs=df_cs,
        value_col="speed_mean", color_map=GLOBAL_COLOR_MAP,
        ylabel="Speed (pixels/h)",
        title=f"Closure Speed at t={int(t_final)} h",
        significance_brackets=speed_brackets,
        panel_label="A", font_scale=font_scale,
    )
    ax_speed.set_xlabel("")

    panel_crosssectional_bar(
        ax=ax_dist, df_cs=df_cs,
        value_col="distance_mean", color_map=GLOBAL_COLOR_MAP,
        ylabel="Distance (pixels)",
        title=f"Closure Distance at t={int(t_final)} h",
        significance_brackets=distance_brackets,
        panel_label="B", font_scale=font_scale,
    )

    panel_timeseries_distance(
        ax=ax_ts, df_ts=df_ts,
        value_col="distance_mean", color_map=GLOBAL_COLOR_MAP,
        ylabel="Wound edge displacement (pixels)",
        title="Wound Edge Displacement Over Time",
        error_type=_ERROR_TYPE,
        show_error_band=show_error_band,
        show_individual=False,
        panel_label="C", font_scale=font_scale * 1.1,
    )

    _save_figure(fig, output_dir, "fig2_wound_dynamics", dpi=dpi)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main(
    traj_path: Optional[Path] = None,
    table_path: Optional[Path] = None,
    pub_dir: Optional[Path] = None,
) -> None:
    """
    Orchestrate the full publication figure generation pipeline.

    Parameters
    ----------
    traj_path : Path or None
        Path to trajectories.pickle.  Defaults to config value.
    table_path : Path or None
        Path to final_legacy_table.xlsx.  Defaults to config value.
    pub_dir : Path or None
        Output directory for figures and tables.  Defaults to config value.

    Steps
    -----
    1. Load Quantification model results (trajectories + legacy table).
    2. Filter out candesartan; rename labels to display-ready strings.
    3. Compute QC + constraint table per trajectory.
    4. Compute time series and cross-sectional metrics.
    5. Compute pairwise significance tests vs DMSO.
    6. Generate Figure 1 (model quality) and Figure 2 (wound dynamics).
    7. Export statistical tables, supplementary tables, and figure captions.
    """
    # ------------------------------------------------------------------
    # Paths (from arguments or config/config.py)
    # ------------------------------------------------------------------
    if traj_path is None:
        traj_path = config.get("trajectories_pickle")
    if table_path is None:
        table_path = config.get("final_legacy_table")
    if pub_dir is None:
        pub_dir = config.get("publication_dir")
    pub_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PUBLICATION FIGURE GENERATOR")
    print("=" * 60)
    print(f"Trajectories pickle : {traj_path}")
    print(f"Legacy table        : {table_path}")
    print(f"Publication output  : {pub_dir}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load
    # ------------------------------------------------------------------
    print("\n[1/7] Loading Quantification results...")
    df_legacy, trajectories = load_quantification_results(traj_path, table_path)
    print(f"      Loaded {len(trajectories)} trajectories, {len(df_legacy)} rows.")

    # ------------------------------------------------------------------
    # 2. Filter candesartan + rename
    # ------------------------------------------------------------------
    print("\n[2/7] Filtering candesartan and renaming labels...")
    df_filt, traj_filt = filter_candesartan(df_legacy, trajectories)
    df_meta = rename_metadata(df_filt)
    print(
        f"      Kept {len(traj_filt)} trajectories, "
        f"{len(df_meta)} rows after filtering."
    )

    # ------------------------------------------------------------------
    # 3. QC + constraint table
    # ------------------------------------------------------------------
    print("\n[3/7] Computing QC and monotonic constraint table...")
    df_qc = compute_qc_constraint_table(traj_filt, df_meta)
    n_pass = df_qc["qc_t0_valid"].sum()
    print(
        f"      {n_pass}/{len(df_qc)} trajectories pass t=0 QC "
        f"({100 * n_pass / max(len(df_qc), 1):.1f}%)."
    )

    # ------------------------------------------------------------------
    # 4. Compute time series and cross-sectional metrics
    # ------------------------------------------------------------------
    print("\n[4/7] Computing wound metrics...")

    df_ts_raw = distance_calculator_timeseries(traj_filt)

    meta_unique = df_meta[
        ["identifier", "cell_line", "sample_condition", "concentration_mm"]
    ].drop_duplicates(subset="identifier")

    df_ts = df_ts_raw.merge(
        meta_unique, left_on="trajectory", right_on="identifier", how="inner",
    )

    max_times = [
        max((r.get("t", 0) for r in v.get("results", [])), default=0)
        for v in traj_filt.values()
    ]
    t_final = float(np.median([t for t in max_times if t > 0])) if max_times else 20.0
    print(f"      Cross-sectional target time: {t_final:.1f} h")

    df_cs_raw = distance_calculator(traj_filt, t_target=t_final)
    df_cs = df_cs_raw.merge(
        meta_unique, left_on="trajectory", right_on="identifier", how="inner",
    )

    # Filter conditions + concentration
    allowed_display = ["DMSO", "Media", "Alk5i"]
    df_ts = df_ts[
        df_ts["sample_condition"].isin(allowed_display)
        & (df_ts["concentration_mm"] == ANALYSIS_CONCENTRATION_MM)
    ].copy()
    df_cs = df_cs[
        df_cs["sample_condition"].isin(allowed_display)
        & (df_cs["concentration_mm"] == ANALYSIS_CONCENTRATION_MM)
    ].copy()
    print(f"      Concentration filter: {ANALYSIS_CONCENTRATION_MM} mM")
    print(f"      Time series: {len(df_ts)} rows, {df_ts['trajectory'].nunique()} trajectories.")
    print(f"      Cross-sectional: {len(df_cs)} trajectories at t~{t_final:.0f} h.")

    # ------------------------------------------------------------------
    # 5. Pairwise significance vs DMSO
    # ------------------------------------------------------------------
    print("\n[5/7] Computing pairwise significance tests...")
    speed_brackets = compute_pairwise_vs_dmso(df_cs, "speed_mean")
    distance_brackets = compute_pairwise_vs_dmso(df_cs, "distance_mean")
    for b in speed_brackets:
        sym = "***" if b["p_corrected"] < 0.001 else "**" if b["p_corrected"] < 0.01 else "*" if b["p_corrected"] < 0.05 else "ns"
        print(f"      Speed  | {b['cell_line']} | {b['condition']} vs {b['control']} | d={b['cohens_d']:.2f} | p_corr={b['p_corrected']:.4f} {sym}")
    for b in distance_brackets:
        sym = "***" if b["p_corrected"] < 0.001 else "**" if b["p_corrected"] < 0.01 else "*" if b["p_corrected"] < 0.05 else "ns"
        print(f"      Dist   | {b['cell_line']} | {b['condition']} vs {b['control']} | d={b['cohens_d']:.2f} | p_corr={b['p_corrected']:.4f} {sym}")

    # ------------------------------------------------------------------
    # 6. Generate Figures
    # ------------------------------------------------------------------
    print("\n[6/7] Generating figures...")
    rep_key = generate_fig1_model_quality(
        trajectories=traj_filt,
        df_meta=df_meta,
        df_qc=df_qc,
        output_dir=pub_dir,
    )

    generate_fig2_wound_dynamics(
        df_ts=df_ts,
        df_cs=df_cs,
        output_dir=pub_dir,
        t_final=t_final,
        speed_brackets=speed_brackets,
        distance_brackets=distance_brackets,
    )

    # ------------------------------------------------------------------
    # 7. Export tables and captions
    # ------------------------------------------------------------------
    print("\n[7/7] Exporting tables and captions...")

    export_statistics_tables(df_ts=df_ts, df_cs=df_cs, output_dir=pub_dir)

    export_supplementary_tables(
        df_ts=df_ts, df_cs=df_cs, df_qc=df_qc, df_meta=df_meta,
        pairwise_speed=speed_brackets,
        pairwise_distance=distance_brackets,
        output_dir=pub_dir,
    )

    # Build n_per_group for captions
    n_per_group = (
        df_cs.groupby(["cell_line", "sample_condition"])
        .size()
        .to_dict()
    )
    n_per_group_str = {
        f"{cl} - {cond}": n for (cl, cond), n in n_per_group.items()
    }

    export_figure_captions(
        output_dir=pub_dir,
        t_final=t_final,
        rep_key=rep_key,
        n_per_group=n_per_group_str,
        error_type=_ERROR_TYPE,
    )

    print("\n" + "=" * 60)
    print(f"Done. Outputs written to: {pub_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
