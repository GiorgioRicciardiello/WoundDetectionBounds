"""
Methods-Paper Reporting (candesartan-free)
==========================================

Dedicated reporting entry-point for the *methods* manuscript in ``latexdoc/``.

This manuscript presents the Quantification segmentation pipeline as a
**methodological** contribution. Unlike the general reporting pipeline
(``scripts/generate_reporting.py``), the candesartan exposure experiment is
removed *in its entirety* — every trajectory, every legacy-table row, and
every manual annotation belonging to the ``-Candasertan`` exposure — so that
candesartan never appears in any census, accuracy, QC, or dynamics output, not
even as an "excluded" line. Validation collapses to the ALK5i exposure
experiment (conditions DMSO, Media, Alk5i).

Why a separate exclusion (not ``filter_candesartan``)
-----------------------------------------------------
``scripts.publication.generate_figures.filter_candesartan`` is inconsistent: it
strips the candesartan *condition* from the DataFrame but drops the whole
candesartan *exposure* from the trajectory dict. Because the manuscript reports
sample sizes by exposure experiment, this module instead applies a single,
explicit exposure-level exclusion (``exclude_candesartan_experiment``) up front
and reuses every downstream helper unchanged.

Reuse
-----
All heavy lifting is delegated to the existing, validated helpers; this module
only adds the exposure-level exclusion and a consolidated "numbers for LaTeX"
report.

Determinism
-----------
No new randomness is introduced. All statistics flow through the same seeded /
deterministic helpers used by the production pipeline, so re-runs are identical.

Usage
-----
    python -m scripts.publication.manuscript_methods_paper

Outputs (under ``paper_publication/methods_paper/``)
----------------------------------------------------
    fig1_model_quality.{png,pdf}
    fig2_wound_dynamics.{png,pdf}
    tables/statistics.xlsx
    tables/supplementary_tables.xlsx
    results_summary.{xlsx,txt}
    figure_captions.txt
    pixel_metrics.csv            -- recomputed Dice/IoU/... (ALK5i polygons)
    latex_numbers.txt            -- consolidated values to transcribe into .tex
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.config import config
from library.filtering.cross_sectional import distance_calculator
from library.filtering.timeseries import distance_calculator_timeseries
from scripts.publication.generate_figures import (
    ANALYSIS_CONCENTRATION_MM,
    _ERROR_TYPE,
    compute_pairwise_vs_dmso,
    compute_qc_constraint_table,
    generate_fig1_model_quality,
    generate_fig2_wound_dynamics,
    load_quantification_results,
    rename_metadata,
)
from scripts.publication.generate_tables import (
    export_figure_captions,
    export_results_summary,
    export_statistics_tables,
    export_supplementary_tables,
    load_verification_results,
)


# ---------------------------------------------------------------------------
# Configuration (single source of truth for this manuscript)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MethodsPaperConfig:
    """Immutable analysis parameters for the methods-paper report."""

    cell_lines: Tuple[str, ...] = ("Line 1", "Line 2")
    conditions: Tuple[str, ...] = ("DMSO", "Media", "Alk5i")
    concentration: float = ANALYSIS_CONCENTRATION_MM  # mM (Media is zero-dose)
    t_min: float = 0.0   # hours
    t_max: float = 20.0  # hours
    method_key: str = "Quantification_kalman"
    method_label: str = "Kalman"
    dpi: int = 300
    font_scale: float = 1.0
    show_error_band: bool = False
    panel_d_span: Tuple[float, float] = (0.17, 0.83)


CONFIG = MethodsPaperConfig()

# Exposure suffixes that identify the candesartan experiment (case variants).
_CANDESARTAN_EXPOSURES: Tuple[str, ...] = ("candasertan", "candesartan")

# Zero-dose negative control(s): kept regardless of the concentration filter.
_ZERO_DOSE_CONTROLS: Tuple[str, ...] = ("Media",)

# Columns of pixel-level metrics stored per polygon in the verification file.
_PIXEL_METRIC_COLS: Tuple[str, ...] = (
    "dice", "iou", "precision", "recall", "f1", "accuracy", "hausdorff_95",
)


# ---------------------------------------------------------------------------
# Candesartan-experiment exclusion (the one behavioural difference)
# ---------------------------------------------------------------------------

def _exposure_of_identifier(identifier: pd.Series) -> pd.Series:
    """Return the exposure token (substring after the last ``-``) of each id.

    Parameters
    ----------
    identifier : pd.Series
        Trajectory identifiers of the form ``<sample>-<experiment>-<exposure>``.

    Returns
    -------
    pd.Series
        Lower-cased exposure token for each identifier.
    """
    return identifier.astype(str).str.rsplit("-", n=1).str[-1].str.lower()


def exclude_candesartan_experiment(
    df_legacy: pd.DataFrame,
    trajectories: Dict,
    df_verification: Optional[pd.DataFrame],
) -> Tuple[pd.DataFrame, Dict, Optional[pd.DataFrame], Dict[str, int]]:
    """Remove the entire candesartan exposure experiment from all inputs.

    The candesartan experiment is identified by the exposure token (the
    substring after the final ``-`` in each trajectory identifier / key). All
    rows, trajectories, and manual annotations belonging to that exposure are
    dropped — including the DMSO and Media control wells acquired within the
    candesartan experiment — so that the remaining data describe the ALK5i
    experiment exclusively.

    Parameters
    ----------
    df_legacy : pd.DataFrame
        Raw legacy table with an ``identifier`` column.
    trajectories : dict
        Raw trajectories keyed by identifier string.
    df_verification : pd.DataFrame or None
        Manual annotations (enriched by ``load_verification_results``). Must
        contain either an ``exposure`` column or a ``trajectory_key`` column.

    Returns
    -------
    df_legacy_kept : pd.DataFrame
        Legacy table with candesartan-exposure rows removed.
    traj_kept : dict
        Trajectories with candesartan-exposure entries removed.
    verif_kept : pd.DataFrame or None
        Annotations with candesartan-exposure rows removed (``None`` if input
        was ``None``).
    counts : dict
        Diagnostic removal counts for logging / assertions.
    """
    # --- Legacy table -----------------------------------------------------
    legacy_exposure = _exposure_of_identifier(df_legacy["identifier"])
    legacy_is_candesartan = legacy_exposure.isin(_CANDESARTAN_EXPOSURES)
    df_legacy_kept = df_legacy.loc[~legacy_is_candesartan].copy()

    # --- Trajectories -----------------------------------------------------
    traj_kept = {
        k: v
        for k, v in trajectories.items()
        if not str(k).lower().endswith(_CANDESARTAN_EXPOSURES)
    }

    # --- Verification annotations ----------------------------------------
    verif_kept: Optional[pd.DataFrame] = None
    n_verif_removed = 0
    if df_verification is not None:
        if "exposure" in df_verification.columns:
            verif_is_candesartan = (
                df_verification["exposure"].astype(str).str.lower()
                .isin(_CANDESARTAN_EXPOSURES)
            )
        else:
            verif_is_candesartan = _exposure_of_identifier(
                df_verification["trajectory_key"]
            ).isin(_CANDESARTAN_EXPOSURES)
        verif_kept = df_verification.loc[~verif_is_candesartan].copy()
        n_verif_removed = int(verif_is_candesartan.sum())

    counts = {
        "rows_removed": int(legacy_is_candesartan.sum()),
        "rows_kept": int(len(df_legacy_kept)),
        "traj_removed": int(len(trajectories) - len(traj_kept)),
        "traj_kept": int(len(traj_kept)),
        "verif_removed": n_verif_removed,
        "verif_kept": int(len(verif_kept)) if verif_kept is not None else 0,
    }
    return df_legacy_kept, traj_kept, verif_kept, counts


# ---------------------------------------------------------------------------
# Filtering + metric computation (mirrors generate_reporting._apply_filters,
# minus the candesartan step which is now done up front)
# ---------------------------------------------------------------------------

def prepare_analysis_frames(
    df_legacy_kept: pd.DataFrame,
    traj_kept: Dict,
    cfg: MethodsPaperConfig,
) -> Tuple[pd.DataFrame, Dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    """Rename, filter, and compute QC / time-series / cross-sectional frames.

    Parameters
    ----------
    df_legacy_kept : pd.DataFrame
        Candesartan-free legacy table.
    traj_kept : dict
        Candesartan-free trajectories.
    cfg : MethodsPaperConfig
        Analysis parameters.

    Returns
    -------
    df_meta : pd.DataFrame
        Filtered + renamed legacy table (all timepoints <= ``t_max``).
    traj_filt : dict
        Trajectories synchronised to ``df_meta``.
    df_ts : pd.DataFrame
        Time-series metrics over ``[t_min, t_max]``.
    df_cs : pd.DataFrame
        Cross-sectional metrics at ``t_final``.
    df_qc : pd.DataFrame
        QC + monotonic-constraint table.
    t_final : float
        Cross-sectional target timepoint (hours).
    """
    df_meta = rename_metadata(df_legacy_kept)

    concentration_filter = (
        df_meta["sample_condition"].isin(_ZERO_DOSE_CONTROLS)
        | (df_meta["concentration_mm"] == cfg.concentration)
    )
    df_meta = df_meta[
        df_meta["sample_condition"].isin(cfg.conditions)
        & concentration_filter
        & df_meta["cell_line"].isin(cfg.cell_lines)
        & (df_meta["t_seg"] <= cfg.t_max)
    ].copy()

    valid_ids = set(df_meta["identifier"].unique())
    traj_filt = {k: v for k, v in traj_kept.items() if k in valid_ids}

    df_qc = compute_qc_constraint_table(traj_filt, df_meta)

    # Single analysis cohort: only trajectories passing t=0 quality control.
    # Every downstream frame (time-series mixed model, cross-sectional effects,
    # normalised closure) is computed on this same set so that the manuscript
    # reports one consistent n. QC-failing trajectories carry unreliable masks
    # whose spurious closure would otherwise contaminate the time-series and
    # invert the area-based condition ranking (see Results).
    qc_pass_ids = set(df_qc.loc[df_qc["qc_t0_valid"], "identifier"])

    meta_unique = (
        df_meta[["identifier", "cell_line", "sample_condition", "concentration_mm"]]
        .drop_duplicates(subset="identifier")
    )

    df_ts = (
        distance_calculator_timeseries(traj_filt)
        .merge(meta_unique, left_on="trajectory", right_on="identifier", how="inner")
    )
    df_ts = df_ts[
        (df_ts["t"] >= cfg.t_min)
        & (df_ts["t"] <= cfg.t_max)
        & (df_ts["trajectory"].isin(qc_pass_ids))
    ].copy()

    valid_t_segs = df_meta.loc[df_meta["t_seg"] > 0, "t_seg"].dropna()
    t_final = float(valid_t_segs.max()) if len(valid_t_segs) > 0 else cfg.t_max

    df_cs = (
        distance_calculator(traj_filt, t_target=t_final)
        .merge(meta_unique, left_on="trajectory", right_on="identifier", how="inner")
    )
    df_cs = df_cs[df_cs["trajectory"].isin(qc_pass_ids)].copy()

    return df_meta, traj_filt, df_ts, df_cs, df_qc, t_final


# ---------------------------------------------------------------------------
# Recomputed pixel-level segmentation metrics (ALK5i polygons only)
# ---------------------------------------------------------------------------

def compute_pixel_metrics(
    verif_kept: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Aggregate pixel-level metrics over expert-annotated polygons.

    Uses the per-image ``dice``/``iou``/... columns already stored in the
    verification workbook. A polygon annotation is identified by the presence
    of a finite ``dice`` value (the ``polygon_drawn`` flag is unreliable and is
    not used).

    Parameters
    ----------
    verif_kept : pd.DataFrame or None
        Candesartan-free verification annotations.

    Returns
    -------
    pd.DataFrame or None
        One row per metric with mean / sd / min / max / n columns, or
        ``None`` if no polygon annotations are available.
    """
    if verif_kept is None or "dice" not in verif_kept.columns:
        return None

    polygons = verif_kept.dropna(subset=["dice"])
    if polygons.empty:
        return None

    rows: List[Dict[str, float]] = []
    for col in _PIXEL_METRIC_COLS:
        if col not in polygons.columns:
            continue
        vals = polygons[col].dropna().values.astype(float)
        if vals.size == 0:
            continue
        rows.append({
            "metric": col,
            "mean": float(np.mean(vals)),
            "sd": float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0,
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "n": int(vals.size),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Consolidated LaTeX-numbers report
# ---------------------------------------------------------------------------

def write_latex_numbers(
    output_dir: Path,
    counts: Dict[str, int],
    df_meta: pd.DataFrame,
    df_cs: pd.DataFrame,
    df_qc: pd.DataFrame,
    t_final: float,
    pixel_metrics: Optional[pd.DataFrame],
) -> None:
    """Write a plain-text digest of the key numbers for the manuscript.

    Parameters
    ----------
    output_dir : Path
        Destination directory.
    counts : dict
        Candesartan-exclusion diagnostics.
    df_meta, df_cs, df_qc : pd.DataFrame
        Filtered analysis frames.
    t_final : float
        Cross-sectional timepoint (hours).
    pixel_metrics : pd.DataFrame or None
        Recomputed pixel-level metric summary.
    """
    lines: List[str] = []
    lines.append("LATEX NUMBERS (candesartan-free, ALK5i experiment only)")
    lines.append("=" * 60)
    lines.append("")
    lines.append("[Candesartan exclusion]")
    for k, v in counts.items():
        lines.append(f"  {k:<16}: {v}")
    lines.append("")

    lines.append("[Analysis cohort — trajectories per cell line x condition]")
    n_traj = (
        df_meta.drop_duplicates(subset="identifier")
        .groupby(["cell_line", "sample_condition"]).size()
    )
    for (cl, cond), n in n_traj.sort_index().items():
        lines.append(f"  {cl:<8} | {cond:<6}: {n}")
    lines.append(f"  TOTAL trajectories (filtered): {df_meta['identifier'].nunique()}")
    lines.append("")

    lines.append(f"[Cross-sectional cohort @ t={t_final:.0f} h]")
    n_cs = df_cs.groupby(["cell_line", "sample_condition"]).size()
    for (cl, cond), n in n_cs.sort_index().items():
        lines.append(f"  {cl:<8} | {cond:<6}: {n}")
    lines.append(f"  TOTAL cross-sectional: {df_cs['trajectory'].nunique()}")
    lines.append("")

    lines.append("[QC pass rate @ t=0 per group]")
    qc = (
        df_qc.groupby(["cell_line", "sample_condition"])
        .agg(n=("qc_t0_valid", "size"), n_pass=("qc_t0_valid", "sum"))
    )
    for (cl, cond), r in qc.sort_index().iterrows():
        rate = 100.0 * r["n_pass"] / max(r["n"], 1)
        lines.append(f"  {cl:<8} | {cond:<6}: {int(r['n_pass'])}/{int(r['n'])} ({rate:.1f}%)")
    lines.append("")

    if pixel_metrics is not None and not pixel_metrics.empty:
        lines.append("[Pixel-level metrics — expert polygons, ALK5i only]")
        n_poly = int(pixel_metrics["n"].max())
        lines.append(f"  n polygons: {n_poly}")
        for _, r in pixel_metrics.iterrows():
            lines.append(
                f"  {r['metric']:<12}: mean={r['mean']:.3f} sd={r['sd']:.3f} "
                f"min={r['min']:.3f} max={r['max']:.3f} (n={int(r['n'])})"
            )
        lines.append("")

    lines.append("See results_summary.txt for the full census / accuracy / QC")
    lines.append("confusion matrix, and supplementary_tables.xlsx for the")
    lines.append("closure tables, pairwise comparisons, and mixed-model output.")

    out_path = output_dir / "latex_numbers.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] LaTeX numbers digest: {out_path}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main(
    traj_path: Optional[Path] = None,
    table_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    cfg: MethodsPaperConfig = CONFIG,
) -> None:
    """Run the full candesartan-free methods-paper reporting pipeline.

    Parameters
    ----------
    traj_path : Path or None
        Trajectories pickle. Defaults to the Kalman method path under
        ``config['output_dir']``.
    table_path : Path or None
        Final legacy table. Defaults to the Kalman method path.
    output_dir : Path or None
        Output directory. Defaults to ``<publication_dir>/methods_paper``.
    cfg : MethodsPaperConfig
        Analysis parameters.
    """
    output_root: Path = config.get("output_dir")
    if traj_path is None:
        traj_path = output_root / cfg.method_key / "trajectories.pickle"
    if table_path is None:
        table_path = output_root / cfg.method_key / "experiments.xlsx"
    if output_dir is None:
        output_dir = config.get("publication_dir") / "methods_paper"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("METHODS-PAPER REPORTING (candesartan-free)")
    print("=" * 60)
    print(f"Trajectories : {traj_path}")
    print(f"Legacy table : {table_path}")
    print(f"Output dir   : {output_dir}")
    print(f"Conditions   : {list(cfg.conditions)} @ {cfg.concentration} mM")
    print("=" * 60)

    # 1. Load raw data + manual annotations
    print("\n[1/8] Loading data...")
    df_legacy, trajectories = load_quantification_results(traj_path, table_path)
    print(f"      {len(trajectories)} trajectories | {len(df_legacy)} rows")

    verif_path = config.get("verification_results")
    df_verification = None
    if verif_path is not None and Path(verif_path).exists():
        df_verification = load_verification_results(Path(verif_path), df_legacy)
        if df_verification is not None:
            print(f"      Verification annotations: {len(df_verification)}")

    # 2. Exclude the entire candesartan exposure experiment
    print("\n[2/8] Excluding candesartan experiment...")
    df_legacy_kept, traj_kept, verif_kept, counts = exclude_candesartan_experiment(
        df_legacy, trajectories, df_verification,
    )
    print(
        f"      Removed {counts['traj_removed']} trajectories, "
        f"{counts['rows_removed']} rows, {counts['verif_removed']} annotations."
    )
    print(
        f"      Kept {counts['traj_kept']} trajectories (ALK5i experiment), "
        f"{counts['rows_kept']} rows."
    )
    # Hard invariant: no candesartan must survive anywhere.
    assert not df_legacy_kept["sample_condition"].str.lower().eq("candasertan").any(), \
        "Candesartan condition rows survived the exclusion."
    assert not any(
        str(k).lower().endswith(_CANDESARTAN_EXPOSURES) for k in traj_kept
    ), "Candesartan trajectories survived the exclusion."

    # 3. Filter + compute analysis frames
    print("\n[3/8] Filtering and computing metrics...")
    df_meta, traj_filt, df_ts, df_cs, df_qc, t_final = prepare_analysis_frames(
        df_legacy_kept, traj_kept, cfg,
    )
    n_qc = int(df_qc["qc_t0_valid"].sum())
    print(f"      Filtered: {len(traj_filt)} trajectories | {len(df_meta)} rows")
    print(f"      QC pass (t=0): {n_qc}/{len(df_qc)}")
    print(f"      Cross-sectional target: t={t_final:.1f} h "
          f"({df_cs['trajectory'].nunique()} trajectories)")

    # 4. Pairwise significance vs DMSO
    print("\n[4/8] Pairwise significance vs DMSO...")
    treatment_conds = [c for c in cfg.conditions if c != "DMSO"]
    speed_brackets = compute_pairwise_vs_dmso(df_cs, "speed_mean", conditions=treatment_conds)
    distance_brackets = compute_pairwise_vs_dmso(df_cs, "distance_mean", conditions=treatment_conds)

    # 5. Figures
    # Figure 1 panel D (normalised closure) and the representative-trajectory
    # selection must use the QC-validated cohort, consistent with every other
    # analysis in the manuscript (the cross-sectional/distance frames already
    # reduce to the QC-pass set). Trajectories that fail t=0 QC carry unreliable
    # masks whose spurious "closure" otherwise inflates the panel-D curve.
    print("\n[5/8] Generating figures...")
    qc_pass_ids = set(df_qc.loc[df_qc["qc_t0_valid"], "identifier"])
    df_meta_qc = df_meta[df_meta["identifier"].isin(qc_pass_ids)].copy()
    print(f"      Fig.1 panel D uses QC-pass cohort: "
          f"{df_meta_qc['identifier'].nunique()}/{df_meta['identifier'].nunique()} trajectories")
    rep_key = generate_fig1_model_quality(
        trajectories=traj_filt, df_meta=df_meta_qc, df_qc=df_qc,
        output_dir=output_dir, dpi=cfg.dpi, font_scale=cfg.font_scale,
        panel_d_span=cfg.panel_d_span, show_error_band=cfg.show_error_band,
    )
    generate_fig2_wound_dynamics(
        df_ts=df_ts, df_cs=df_cs, output_dir=output_dir, t_final=t_final,
        speed_brackets=speed_brackets, distance_brackets=distance_brackets,
        dpi=cfg.dpi, font_scale=cfg.font_scale, show_error_band=cfg.show_error_band,
    )

    # 6. Tables + captions
    print("\n[6/8] Exporting statistics and supplementary tables...")
    export_statistics_tables(df_ts=df_ts, df_cs=df_cs, output_dir=output_dir)
    export_supplementary_tables(
        df_ts=df_ts, df_cs=df_cs, df_qc=df_qc, df_meta=df_meta,
        pairwise_speed=speed_brackets, pairwise_distance=distance_brackets,
        output_dir=output_dir,
    )
    n_per_group_str = {
        f"{cl} - {cond}": n
        for (cl, cond), n in df_cs.groupby(["cell_line", "sample_condition"]).size().items()
    }
    export_figure_captions(
        output_dir=output_dir, t_final=t_final, rep_key=rep_key,
        n_per_group=n_per_group_str, error_type=_ERROR_TYPE,
    )

    # 7. Results summary (census / accuracy / QC) — candesartan-free inputs
    print("\n[7/8] Exporting results summary...")
    export_results_summary(
        df_legacy=df_legacy_kept,
        trajectories=traj_kept,
        df_meta=df_meta,
        traj_filt=traj_filt,
        df_qc=df_qc,
        df_cs=df_cs,
        df_ts=df_ts,
        t_final=t_final,
        method_label=cfg.method_label,
        output_dir=output_dir,
        df_verification=verif_kept,
    )

    # 8. Pixel metrics + consolidated LaTeX-numbers digest
    print("\n[8/8] Recomputing pixel metrics and writing LaTeX digest...")
    pixel_metrics = compute_pixel_metrics(verif_kept)
    if pixel_metrics is not None:
        pixel_metrics.to_csv(output_dir / "pixel_metrics.csv", index=False)
        print(f"[OK] Pixel metrics: {output_dir / 'pixel_metrics.csv'}")
    write_latex_numbers(
        output_dir, counts, df_meta, df_cs, df_qc, t_final, pixel_metrics,
    )

    print("\n" + "=" * 60)
    print(f"Done. Methods-paper outputs written to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
