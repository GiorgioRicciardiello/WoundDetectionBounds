"""
generate_reporting.py
=====================

Unified entry-point for wound-healing publication reporting.

Orchestrates figure generation and statistical tables for single-method
(Kalman or Hard) or method-comparison (Kalman vs Hard) analyses.

All analysis parameters are defined as module-level constants in
``ReportingConfig`` — no CLI argument parsing. This is the single source
of truth for all reporting parameters.

Usage
-----
    python -m scripts.generate_reporting

Output
------
Single method (ReportingConfig.do_comparison=False):
    paper_publication/
        fig1_model_quality.{png,pdf}
        fig2_wound_dynamics.{png,pdf}
        tables/statistics.xlsx
        tables/supplementary_tables.xlsx
        figure_captions.txt
        results_summary.xlsx + results_summary.txt

Method comparison (ReportingConfig.do_comparison=True):
    paper_publication/
        kalman/          -- fig1, fig2, tables for Kalman method
        hard/            -- fig1, fig2, tables for hard constraint method
        comparison/
            method_comparison.xlsx   -- per-method summary + pairwise stats
            method_comparison.png    -- visual comparison panel
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from config.config import config
from library.filtering.cross_sectional import distance_calculator
from library.filtering.timeseries import distance_calculator_timeseries
from scripts.publication.generate_figures import (
    GLOBAL_COLOR_MAP,
    _ERROR_TYPE,
    compute_pairwise_vs_dmso,
    compute_qc_constraint_table,
    filter_candesartan,
    generate_fig1_model_quality,
    generate_fig2_wound_dynamics,
    load_quantification_results,
    rename_metadata,
)
from scripts.publication.comparison import (
    per_group_comparison,
    summary_row,
    generate_comparison_figure,
)
from scripts.publication.generate_tables import (
    export_figure_captions,
    export_results_summary,
    export_statistics_tables,
    export_supplementary_tables,
    load_verification_results,
)


# ---------------------------------------------------------------------------
# Analysis configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportingConfig:
    """Immutable analysis parameters for the reporting pipeline."""

    cell_lines: Tuple[str, ...] = ("Line 1", "Line 2")  # "Line 2"
    conditions: Tuple[str, ...] = ("DMSO", "Alk5i")  # "Media",
    concentration: float = 0.1        # mM
    t_min: float = 0.0                # hours
    t_max: float = 20.0               # hours
    method: str = "kalman"            # 'kalman' or 'hard' (ignored if do_comparison=True)
    do_comparison: bool = True       # If True, compare kalman vs hard instead of single method
    # Figure parameters
    dpi: int = 300
    font_scale: float = 1.0
    show_error_band: bool = False
    panel_d_span: Tuple[float, float] = (0.17, 0.83)


# Single source of truth for the default run configuration.
REPORTING_CONFIG = ReportingConfig()


# ---------------------------------------------------------------------------
# Method paths (Kalman / Hard)
# ---------------------------------------------------------------------------

_OUTPUT_DIR: Path = config.get("output_dir")

METHODS: Dict[str, Dict[str, object]] = {
    "kalman": {
        "label": "Kalman",
        "traj_path": _OUTPUT_DIR / "Quantification_kalman" / "trajectories.pickle",
        "table_path": _OUTPUT_DIR / "Quantification_kalman" / "final_legacy_table.xlsx",
    },
    "hard": {
        "label": "Hard",
        "traj_path": _OUTPUT_DIR / "Quantification_hard" / "trajectories.pickle",
        "table_path": _OUTPUT_DIR / "Quantification_hard" / "final_legacy_table.xlsx",
    },
}


# ---------------------------------------------------------------------------
# Data loading and filtering
# ---------------------------------------------------------------------------

def _apply_filters(
    df_legacy: pd.DataFrame,
    trajectories: Dict,
    cell_lines: List[str],
    conditions: List[str],
    concentration: float,
    t_min: float,
    t_max: float,
) -> Tuple[pd.DataFrame, Dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    """
    Filter data to the selected parameters and compute metrics.

    Steps
    -----
    1. Remove candesartan exposures.
    2. Rename raw labels to display names.
    3. Filter by conditions, concentration, and cell lines.
    4. Synchronise trajectories dict to filtered metadata.
    5. Compute QC + constraint table.
    6. Compute time-series metrics; clip to [t_min, t_max].
    7. Compute cross-sectional metrics at the last available timepoint
       up to t_max.

    Parameters
    ----------
    df_legacy : pd.DataFrame
        Raw legacy table from ``load_quantification_results``.
    trajectories : dict
        Raw trajectories dict.
    cell_lines : list of str
        Display names to keep (e.g. ['Line 1', 'Line 2']).
    conditions : list of str
        Display names to keep (e.g. ['DMSO', 'Media', 'Alk5i']).
    concentration : float
        Concentration value (mM) to retain.
    t_min, t_max : float
        Inclusive time window in hours.

    Returns
    -------
    df_meta : pd.DataFrame
        Filtered + renamed legacy table (all timepoints <= t_max).
    traj_filt : dict
        Filtered trajectories.
    df_ts : pd.DataFrame
        Time-series metrics clipped to [t_min, t_max].
    df_cs : pd.DataFrame
        Cross-sectional metrics at t_final.
    df_qc : pd.DataFrame
        QC + constraint table.
    t_final : float
        Actual cross-sectional target timepoint.
    """
    # 1-2. Remove candesartan + rename
    df_filt, traj_nocan = filter_candesartan(df_legacy, trajectories)
    df_meta = rename_metadata(df_filt)

    # 3. Filter by conditions, concentration, and cell lines.
    # "Media" is a zero-dose negative control (concentration_mm == 0.0) and
    # must be included whenever it appears in the requested conditions list,
    # regardless of the concentration argument.
    _ZERO_DOSE_CONTROLS: List[str] = ["Media"]
    concentration_filter = (
        df_meta["sample_condition"].isin(_ZERO_DOSE_CONTROLS)
        | (df_meta["concentration_mm"] == concentration)
    )
    df_meta = df_meta[
        df_meta["sample_condition"].isin(conditions)
        & concentration_filter
        & df_meta["cell_line"].isin(cell_lines)
    ].copy()

    # Limit time axis (keep t=0 for normalisation; drop nothing below t_min
    # in the legacy table — that is handled at metric-level below)
    df_meta = df_meta[df_meta["t_seg"] <= t_max].copy()

    # 4. Sync trajectories to filtered metadata
    valid_ids = set(df_meta["identifier"].unique())
    traj_filt = {k: v for k, v in traj_nocan.items() if k in valid_ids}

    # 5. QC table
    df_qc = compute_qc_constraint_table(traj_filt, df_meta)

    # 6. Time-series metrics
    df_ts_raw = distance_calculator_timeseries(traj_filt)
    meta_unique = (
        df_meta[["identifier", "cell_line", "sample_condition", "concentration_mm"]]
        .drop_duplicates(subset="identifier")
    )
    df_ts = df_ts_raw.merge(
        meta_unique, left_on="trajectory", right_on="identifier", how="inner",
    )
    df_ts = df_ts[(df_ts["t"] >= t_min) & (df_ts["t"] <= t_max)].copy()

    # 7. Cross-sectional: target = last timepoint in the filtered window.
    valid_t_segs = df_meta.loc[df_meta["t_seg"] > 0, "t_seg"].dropna()
    t_final = float(valid_t_segs.max()) if len(valid_t_segs) > 0 else t_max

    df_cs_raw = distance_calculator(traj_filt, t_target=t_final)
    df_cs = df_cs_raw.merge(
        meta_unique, left_on="trajectory", right_on="identifier", how="inner",
    )

    return df_meta, traj_filt, df_ts, df_cs, df_qc, t_final


# ---------------------------------------------------------------------------
# Sample summary
# ---------------------------------------------------------------------------

def _print_sample_summary(df_meta: pd.DataFrame, df_cs: pd.DataFrame) -> None:
    """Print a formatted sample summary table to the console.

    Parameters
    ----------
    df_meta : pd.DataFrame
        Filtered metadata (one row per trajectory-timepoint).
    df_cs : pd.DataFrame
        Cross-sectional data (one row per trajectory at t_final).
    """
    group_cols = ["cell_line", "sample_condition"]

    n_trajectories = (
        df_meta.drop_duplicates(subset="identifier")
        .groupby(group_cols)
        .size()
    )
    n_images = df_meta.groupby(group_cols).size()
    n_cs = df_cs.groupby(group_cols).size()

    print("\n  Sample Summary")
    print(f"  {'Cell Line':<12} | {'Condition':<10} | {'Trajectories':>13} | "
          f"{'Images':>7} | {'Cross-sect':>11}")
    print(f"  {'-'*12}-+-{'-'*10}-+-{'-'*13}-+-{'-'*7}-+-{'-'*11}")

    for (cl, cond) in sorted(n_trajectories.index):
        n_traj = n_trajectories.get((cl, cond), 0)
        n_img = n_images.get((cl, cond), 0)
        n_c = n_cs.get((cl, cond), 0)
        print(f"  {cl:<12} | {cond:<10} | {n_traj:>13} | {n_img:>7} | {n_c:>11}")
    print()


# ---------------------------------------------------------------------------
# Single-method pipeline
# ---------------------------------------------------------------------------

def _run_single_method(
    method_key: str,
    cfg: ReportingConfig,
    output_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict, float]:
    """
    Run the full reporting pipeline for one constraint method.

    Parameters
    ----------
    method_key : str
        'kalman' or 'hard'.
    cfg : ReportingConfig
        Analysis parameters.
    output_dir : Path
        Destination directory for this method's outputs.

    Returns
    -------
    df_ts, df_cs, df_qc, traj_filt, t_final
        Filtered data for downstream comparison use.
    """
    info = METHODS[method_key]
    output_dir.mkdir(parents=True, exist_ok=True)

    _banner(f"Method: {info['label']}")
    _print_config(cfg, output_dir)

    # ------------------------------------------------------------------
    # 1. Load
    # ------------------------------------------------------------------
    print("\n[1/7] Loading data...")
    df_legacy, trajectories = load_quantification_results(
        info["traj_path"], info["table_path"],
    )
    print(f"      {len(trajectories)} trajectories | {len(df_legacy)} rows")

    # Load manual verification results (optional — graceful if missing)
    verif_path = config.get("verification_results")
    df_verification = None
    if verif_path is not None:
        df_verification = load_verification_results(
            Path(verif_path), df_legacy,
        )
        if df_verification is not None:
            print(f"      Verification: {len(df_verification)} t=0 annotations loaded")

    # ------------------------------------------------------------------
    # 2. Filter
    # ------------------------------------------------------------------
    print("\n[2/7] Applying filters...")
    df_meta, traj_filt, df_ts, df_cs, df_qc, t_final = _apply_filters(
        df_legacy=df_legacy,
        trajectories=trajectories,
        cell_lines=list(cfg.cell_lines),
        conditions=list(cfg.conditions),
        concentration=cfg.concentration,
        t_min=cfg.t_min,
        t_max=cfg.t_max,
    )

    n_qc = int(df_qc["qc_t0_valid"].sum())
    print(f"      After filtering: {len(traj_filt)} trajectories | {len(df_meta)} rows")
    print(f"      QC pass (t=0): {n_qc}/{len(df_qc)} ({100*n_qc/max(len(df_qc),1):.1f}%)")
    print(f"      Time-series: {len(df_ts)} rows | {df_ts['trajectory'].nunique()} trajectories")
    print(f"      Cross-sectional: {len(df_cs)} trajectories at t~{t_final:.0f} h")

    _print_sample_summary(df_meta, df_cs)

    # ------------------------------------------------------------------
    # 3. Pairwise significance tests
    # ------------------------------------------------------------------
    print("[3/7] Computing pairwise significance tests vs DMSO...")
    if "DMSO" not in cfg.conditions:
        warnings.warn(
            "DMSO not in conditions; pairwise significance tests skipped.",
        )
        speed_brackets: List[Dict] = []
        distance_brackets: List[Dict] = []
    else:
        treatment_conds = [c for c in cfg.conditions if c != "DMSO"]
        speed_brackets = compute_pairwise_vs_dmso(
            df_cs, "speed_mean", conditions=treatment_conds,
        )
        distance_brackets = compute_pairwise_vs_dmso(
            df_cs, "distance_mean", conditions=treatment_conds,
        )
        for b in speed_brackets + distance_brackets:
            sym = _sig_symbol(b["p_corrected"])
            metric = "speed" if b in speed_brackets else "dist"
            print(
                f"      {metric:>5} | {b['cell_line']} | {b['condition']} vs DMSO"
                f" | d={b['cohens_d']:+.2f} | p_corr={b['p_corrected']:.4f} {sym}"
            )

    # ------------------------------------------------------------------
    # 4. Figures
    # ------------------------------------------------------------------
    print("\n[4/7] Generating figures...")
    generate_fig1_model_quality(
        trajectories=traj_filt,
        df_meta=df_meta,
        df_qc=df_qc,
        output_dir=output_dir,
        dpi=cfg.dpi,
        font_scale=cfg.font_scale,
        panel_d_span=cfg.panel_d_span,
        show_error_band=cfg.show_error_band,
    )
    generate_fig2_wound_dynamics(
        df_ts=df_ts,
        df_cs=df_cs,
        output_dir=output_dir,
        t_final=t_final,
        speed_brackets=speed_brackets,
        distance_brackets=distance_brackets,
        dpi=cfg.dpi,
        font_scale=cfg.font_scale,
        show_error_band=cfg.show_error_band,
    )

    # ------------------------------------------------------------------
    # 5. Tables
    # ------------------------------------------------------------------
    print("\n[5/7] Exporting tables...")
    export_statistics_tables(df_ts=df_ts, df_cs=df_cs, output_dir=output_dir)

    n_per_group = (
        df_cs.groupby(["cell_line", "sample_condition"]).size().to_dict()
    )
    n_per_group_str = {
        f"{cl} - {cond}": n for (cl, cond), n in n_per_group.items()
    }
    export_supplementary_tables(
        df_ts=df_ts, df_cs=df_cs, df_qc=df_qc, df_meta=df_meta,
        pairwise_speed=speed_brackets,
        pairwise_distance=distance_brackets,
        output_dir=output_dir,
    )

    # ------------------------------------------------------------------
    # 6. Figure captions
    # ------------------------------------------------------------------
    print("\n[6/7] Exporting figure captions...")
    export_figure_captions(
        output_dir=output_dir,
        t_final=t_final,
        rep_key=None,
        n_per_group=n_per_group_str,
        error_type=_ERROR_TYPE,
    )

    # ------------------------------------------------------------------
    # 7. Results summary (census, manual review, QC, wound dynamics)
    # ------------------------------------------------------------------
    print("\n[7/7] Exporting results summary...")
    export_results_summary(
        df_legacy=df_legacy,
        trajectories=trajectories,
        df_meta=df_meta,
        traj_filt=traj_filt,
        df_qc=df_qc,
        df_cs=df_cs,
        df_ts=df_ts,
        t_final=t_final,
        method_label=str(info["label"]),
        output_dir=output_dir,
        df_verification=df_verification,
    )

    return df_ts, df_cs, df_qc, traj_filt, t_final


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner(text: str) -> None:
    """Print a section banner."""
    print(f"\n{'='*60}")
    print(text)
    print(f"{'='*60}")


def _print_config(cfg: ReportingConfig, output_dir: Path) -> None:
    """Print the active run configuration.

    Parameters
    ----------
    cfg : ReportingConfig
        Analysis parameters.
    output_dir : Path
        Output directory for this run.
    """
    print(f"  Cell lines    : {list(cfg.cell_lines)}")
    print(f"  Conditions    : {list(cfg.conditions)}")
    print(f"  Concentration : {cfg.concentration} mM")
    print(f"  Time window   : {cfg.t_min}\u2013{cfg.t_max} h")
    print(f"  Output dir    : {output_dir}")


def _sig_symbol(p: float) -> str:
    """Map a corrected p-value to a significance symbol."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Comparison pipeline (Kalman vs Hard)
# ---------------------------------------------------------------------------

def _run_comparison(cfg: ReportingConfig, pub_root: Path) -> None:
    """Run the comparison pipeline: Kalman vs Hard constraint methods.

    Saves all outputs (figures, tables, results summary) to a
    ``method_comparison`` subdirectory of the publication folder.

    Parameters
    ----------
    cfg : ReportingConfig
        Analysis parameters (controls cell lines, conditions, filtering).
    pub_root : Path
        Root publication (manuscript) output directory.
    """
    _banner("METHOD COMPARISON: Kalman vs Hard Constraint")
    print(f"  Controlled by: ReportingConfig")
    print()

    # ------------------------------------------------------------------
    # 1. Run both methods through the shared pipeline
    # ------------------------------------------------------------------
    print("=" * 60)
    print("Running both constraint methods...")
    print("=" * 60)

    comp_root = pub_root / "method_comparison"
    results: Dict[str, Tuple] = {}
    for method_key in ("kalman", "hard"):
        out_dir = comp_root / method_key
        results[method_key] = _run_single_method(method_key, cfg, out_dir)

    # ------------------------------------------------------------------
    # 2. Build comparison tables
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("Computing comparison metrics...")
    print(f"{'='*60}")

    df_ts_k, df_cs_k, df_qc_k, traj_k, t_final = results["kalman"]
    df_ts_h, df_cs_h, df_qc_h, traj_h, _ = results["hard"]

    summary_k = summary_row("kalman", df_ts_k, df_cs_k, df_qc_k, traj_k, t_final)
    summary_h = summary_row("hard", df_ts_h, df_cs_h, df_qc_h, traj_h, t_final)
    df_summary = pd.DataFrame([summary_k, summary_h])

    df_per_group = per_group_comparison(df_cs_k, df_cs_h)

    # Pairwise significance (each method independently)
    treatment_conds = [c for c in cfg.conditions if c != "DMSO"]
    if "DMSO" in cfg.conditions and treatment_conds:
        pw_rows: List[Dict] = []
        for method_label, df_cs in [("Kalman", df_cs_k), ("Hard", df_cs_h)]:
            for metric in ["speed_mean", "distance_mean"]:
                for row in compute_pairwise_vs_dmso(
                    df_cs, metric, conditions=list(treatment_conds),
                ):
                    row["method"] = method_label
                    row["metric"] = metric
                    pw_rows.append(row)
        df_pairwise = pd.DataFrame(pw_rows)
    else:
        df_pairwise = pd.DataFrame()

    # ------------------------------------------------------------------
    # 3. Save comparison tables
    # ------------------------------------------------------------------
    comp_dir = comp_root / "comparison"
    comp_dir.mkdir(parents=True, exist_ok=True)

    xlsx_path = comp_dir / "method_comparison.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="summary", index=False)
        df_per_group.to_excel(writer, sheet_name="per_group", index=False)
        if not df_pairwise.empty:
            df_pairwise.to_excel(writer, sheet_name="pairwise_vs_dmso", index=False)

    print(f"\n[OK] Comparison tables: {xlsx_path}")

    # ------------------------------------------------------------------
    # 4. Print summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(df_summary.T.to_string())

    print(f"\n--- Per-Group Differences (Kalman - Hard) ---")
    if not df_per_group.empty:
        for _, row in df_per_group.iterrows():
            print(
                f"  {row['cell_line']:>8} | {row['condition']:>6} | "
                f"{row['metric']:>15} | K={row['kalman_mean']:>8.3f} | "
                f"H={row['hard_mean']:>8.3f} | diff={row['diff']:>+8.3f} "
                f"({row['diff_pct']:>+.1f}%)"
            )

    # ------------------------------------------------------------------
    # 5. Generate comparison figure
    # ------------------------------------------------------------------
    print(f"\nGenerating comparison figure...")
    generate_comparison_figure(
        df_cs_kalman=df_cs_k,
        df_cs_hard=df_cs_h,
        df_ts_kalman=df_ts_k,
        df_ts_hard=df_ts_h,
        output_dir=comp_dir,
        t_final=t_final,
    )

    print(f"\n{'='*60}")
    print(f"All outputs in: {comp_root}")
    print(f"  kalman/     - Kalman-filtered figures + tables + results summary")
    print(f"  hard/       - Hard constraint figures + tables + results summary")
    print(f"  comparison/ - Side-by-side comparison + method_comparison.xlsx")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Unified reporting pipeline entry point.

    Controlled entirely by ``REPORTING_CONFIG``:
    - If ``do_comparison=False`` (default): runs single method (Kalman or Hard).
    - If ``do_comparison=True``: compares Kalman vs Hard.

    All parameters (cell lines, conditions, time window, figure settings) are
    defined in ``ReportingConfig`` — the single source of truth.
    """
    cfg = REPORTING_CONFIG

    pub_root: Path = config.get("publication_dir")

    _banner("WOUND HEALING REPORTING PIPELINE")
    _print_config(cfg, pub_root)

    if cfg.do_comparison:
        _run_comparison(cfg, pub_root)
    else:
        _run_single_method(cfg.method, cfg, pub_root)

    _banner("Done")
    print(f"  All outputs: {pub_root}")


if __name__ == "__main__":
    main()
