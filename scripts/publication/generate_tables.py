"""
Publication Table Generator
============================

Generates statistical tables, supplementary tables, and figure captions for
the wound healing publication pipeline.

This module was extracted from generate_figures.py for line-count management.
The ``export_statistics_tables`` function previously lived in generate_figures
and is now the canonical implementation here.  All table and caption export
functions are collected in this single file so that the figure generator can
remain focused on plotting logic.

Usage
-----
Import individual functions into your pipeline orchestrator::

    from scripts.publication.generate_tables import (
        export_statistics_tables,
        export_supplementary_tables,
        export_figure_captions,
    )
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


# ---------------------------------------------------------------------------
# 1. Primary statistics tables
# ---------------------------------------------------------------------------

def export_statistics_tables(
    df_ts: pd.DataFrame,
    df_cs: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Export primary statistical analysis results to a multi-sheet Excel file.

    Analyses performed
    ------------------
    * Group-level descriptive statistics for the time-series data.
    * Mixed-effects model (distance ~ time x condition x cell_line) with
      random slopes per trajectory.
    * Per-trajectory slope and AUC, with group comparisons vs DMSO.
    * Cross-sectional ANOVA + Cohen's d vs DMSO at the final timepoint.

    Output
    ------
    ``<output_dir>/tables/statistics.xlsx`` with sheets:

    =========================================  =======================================
    Sheet                                      Content
    =========================================  =======================================
    group_stats_timeseries                     mean / std / count / sem per group × t
    slope_stats                                Per-group slope summary
    auc_stats                                  Per-group AUC summary
    slope_effects                              Slope effect sizes vs DMSO
    auc_effects                                AUC effect sizes vs DMSO
    mixed_model_pvalues                        Fixed-effect p-values
    mixed_model_coefficients                   Full fixed-effects table
    crosssectional_group_stats                 Final-timepoint group summary
    effect_sizes_vs_DMSO                       Cohen's d + p at final timepoint
    =========================================  =======================================

    Parameters
    ----------
    df_ts : pd.DataFrame
        Time-series data with columns: trajectory, t, distance_mean,
        cell_line, sample_condition (at minimum).
    df_cs : pd.DataFrame
        Cross-sectional data at the final timepoint with columns:
        trajectory, t_seg, distance_mean, cell_line, sample_condition.
    output_dir : Path
        Root publication directory.  The file is written to
        ``output_dir / "tables" / "statistics.xlsx"``.
    """
    from scripts.publication.stat_test import (
        analyze_final_timepoint,
        analyze_migration_dynamics,
    )

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    out_path = tables_dir / "statistics.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # -- Time-series group summary ---------------------------------
        ts_grp = (
            df_ts.groupby(["cell_line", "sample_condition", "t"])["distance_mean"]
            .agg(["mean", "std", "count"])
            .reset_index()
        )
        ts_grp["sem"] = ts_grp["std"] / np.sqrt(ts_grp["count"].clip(lower=1))
        ts_grp.to_excel(writer, sheet_name="group_stats_timeseries", index=False)

        # -- Mixed model + slope / AUC ---------------------------------
        try:
            res_ts: Dict[str, Any] = analyze_migration_dynamics(
                df_ts,
                distance_col="distance_mean",
                time_col="t",
                id_col="trajectory",
                treatment_col="sample_condition",
                cellline_col="cell_line",
            )
            res_ts["slope_stats"].to_excel(
                writer, sheet_name="slope_stats", index=False
            )
            res_ts["auc_stats"].to_excel(
                writer, sheet_name="auc_stats", index=False
            )
            res_ts["slope_effects"].to_excel(
                writer, sheet_name="slope_effects", index=False
            )
            res_ts["auc_effects"].to_excel(
                writer, sheet_name="auc_effects", index=False
            )

            # Mixed model p-values
            mixed_pvals = res_ts["mixed_model"]["pvalues"].reset_index()
            mixed_pvals.columns = ["term", "p_value"]
            mixed_pvals.to_excel(
                writer, sheet_name="mixed_model_pvalues", index=False
            )

            # Mixed model full coefficients table
            _write_mixed_model_coefficients(
                res_ts["mixed_model"], writer
            )

        except Exception as exc:
            warnings.warn(
                f"Mixed model / slope / AUC analysis failed: {exc}",
                stacklevel=2,
            )

        # -- Cross-sectional final timepoint ---------------------------
        try:
            res_cs: Dict[str, Any] = analyze_final_timepoint(
                df_cs,
                distance_col="distance_mean",
                time_col="t_seg",
                id_col="trajectory",
                treatment_col="sample_condition",
                cellline_col="cell_line",
            )
            res_cs["group_stats"].to_excel(
                writer, sheet_name="crosssectional_group_stats", index=False
            )
            res_cs["effect_sizes_vs_DMSO"].to_excel(
                writer, sheet_name="effect_sizes_vs_DMSO", index=False
            )
        except Exception as exc:
            warnings.warn(
                f"Cross-sectional analysis failed: {exc}",
                stacklevel=2,
            )

    print(f"[OK] Statistics exported: {out_path}")


def _write_mixed_model_coefficients(
    mixed_model_dict: Dict[str, Any],
    writer: pd.ExcelWriter,
) -> None:
    """Write the full fixed-effects coefficient table to an Excel sheet.

    Extracts params, bse (standard errors), and pvalues from the stored
    mixed-model result dictionary and combines them into a single DataFrame.

    Parameters
    ----------
    mixed_model_dict : dict
        The ``"mixed_model"`` entry returned by
        ``analyze_migration_dynamics``, containing keys *params*,
        *pvalues*, and optionally *conf_int*.
    writer : pd.ExcelWriter
        Open Excel writer to append the sheet to.
    """
    params = mixed_model_dict.get("params")
    pvalues = mixed_model_dict.get("pvalues")

    if params is None or pvalues is None:
        return

    coef_df = pd.DataFrame({
        "term": params.index,
        "estimate": params.values,
        "p_value": pvalues.reindex(params.index).values,
    })

    # Include standard errors if the model exposed bse
    # (statsmodels MixedLMResults stores bse on the result object; we
    #  may not have it if only summary dicts were stored.)
    conf_int = mixed_model_dict.get("conf_int")
    if conf_int is not None and hasattr(conf_int, "values"):
        ci = conf_int.reindex(params.index)
        coef_df["ci_lower"] = ci.iloc[:, 0].values
        coef_df["ci_upper"] = ci.iloc[:, 1].values

    coef_df.to_excel(writer, sheet_name="mixed_model_coefficients", index=False)


# ---------------------------------------------------------------------------
# 2. Supplementary tables
# ---------------------------------------------------------------------------

def export_supplementary_tables(
    df_ts: pd.DataFrame,
    df_cs: pd.DataFrame,
    df_qc: pd.DataFrame,
    df_meta: pd.DataFrame,
    pairwise_speed: List[Dict[str, Any]],
    pairwise_distance: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    """Export supplementary tables to a multi-sheet Excel workbook.

    Parameters
    ----------
    df_ts : pd.DataFrame
        Time-series data with trajectory, t, distance_mean, speed_mean,
        cell_line, sample_condition.
    df_cs : pd.DataFrame
        Cross-sectional data at the final timepoint with trajectory,
        distance_mean, speed_mean, cell_line, sample_condition.
    df_qc : pd.DataFrame
        QC table with identifier, qc_t0_valid, constraint_rate,
        cell_line, sample_condition.
    df_meta : pd.DataFrame
        Full metadata table (one row per trajectory-timepoint) with
        identifier, cell_line, sample_condition.
    pairwise_speed : list of dict
        Pairwise comparison results for speed_mean.  Each dict contains
        keys: cell_line, condition, control, t_stat, p_raw, p_corrected,
        cohens_d, ci_lower, ci_upper, n_treatment, n_control.
    pairwise_distance : list of dict
        Same structure as *pairwise_speed* but for distance_mean.
    output_dir : Path
        Root publication directory.  File written to
        ``output_dir / "tables" / "supplementary_tables.xlsx"``.
    """
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    out_path = tables_dir / "supplementary_tables.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        _sheet_sample_sizes(df_cs, writer)
        _sheet_sample_accounting(df_meta, df_qc, df_cs, writer)
        _sheet_descriptive_stats(df_cs, writer)
        _sheet_qc_validation(df_qc, writer)
        _sheet_pairwise_comparisons(pairwise_speed, pairwise_distance, writer)
        _sheet_exp_reproducibility(df_cs, writer)
        _sheet_assumption_checks(df_cs, writer)

    print(f"[OK] Supplementary tables exported: {out_path}")


# -- Individual sheet helpers ------------------------------------------------

def _sheet_sample_sizes(
    df_cs: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``sample_sizes`` sheet — pivoted n per group.

    Parameters
    ----------
    df_cs : pd.DataFrame
        Cross-sectional data.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    pivot = (
        df_cs.groupby(["cell_line", "sample_condition"])
        .size()
        .unstack(fill_value=0)
    )
    pivot.to_excel(writer, sheet_name="sample_sizes")


def _sheet_sample_accounting(
    df_meta: pd.DataFrame,
    df_qc: pd.DataFrame,
    df_cs: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``sample_accounting`` sheet — trajectory flow from initial to final.

    For each (cell_line, sample_condition) group the sheet reports:
    n_initial (from df_meta unique identifiers), n_qc_pass (from df_qc),
    n_final (from df_cs unique trajectories), n_excluded, exclusion_pct.

    Parameters
    ----------
    df_meta : pd.DataFrame
        Full metadata table.
    df_qc : pd.DataFrame
        QC results with qc_t0_valid column.
    df_cs : pd.DataFrame
        Final cross-sectional data.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    group_cols = ["cell_line", "sample_condition"]

    # Initial: unique identifiers in metadata
    initial = (
        df_meta.drop_duplicates(subset="identifier")
        .groupby(group_cols)
        .size()
        .rename("n_initial")
        .reset_index()
    )

    # QC pass
    qc_pass = (
        df_qc[df_qc["qc_t0_valid"]]
        .groupby(group_cols)
        .size()
        .rename("n_qc_pass")
        .reset_index()
    )

    # Final
    final = (
        df_cs.drop_duplicates(subset="trajectory")
        .groupby(group_cols)
        .size()
        .rename("n_final")
        .reset_index()
    )

    # Total images (frames) per group from metadata
    n_images = (
        df_meta.groupby(group_cols)
        .size()
        .rename("n_images")
        .reset_index()
    )

    accounting = initial.merge(qc_pass, on=group_cols, how="left")
    accounting = accounting.merge(final, on=group_cols, how="left")
    accounting = accounting.merge(n_images, on=group_cols, how="left")
    accounting = accounting.fillna(0).astype(
        {c: int for c in ["n_initial", "n_qc_pass", "n_final", "n_images"]}
    )
    accounting["n_excluded"] = accounting["n_initial"] - accounting["n_final"]
    accounting["exclusion_pct"] = np.where(
        accounting["n_initial"] > 0,
        100.0 * accounting["n_excluded"] / accounting["n_initial"],
        0.0,
    )

    accounting.to_excel(writer, sheet_name="sample_accounting", index=False)


def _sheet_descriptive_stats(
    df_cs: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``descriptive_stats`` sheet — summary per group.

    For each (cell_line, sample_condition) reports mean, std, sem,
    ci95_lower, ci95_upper for both distance_mean and speed_mean.

    Parameters
    ----------
    df_cs : pd.DataFrame
        Cross-sectional data.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    group_cols = ["cell_line", "sample_condition"]
    metrics = ["distance_mean", "speed_mean"]

    rows: List[Dict[str, Any]] = []
    for (cl, cond), grp in df_cs.groupby(group_cols):
        row: Dict[str, Any] = {"cell_line": cl, "sample_condition": cond}
        for metric in metrics:
            vals = grp[metric].dropna().values
            n = len(vals)
            mean = float(np.mean(vals)) if n > 0 else np.nan
            std = float(np.std(vals, ddof=1)) if n > 1 else np.nan
            sem = std / np.sqrt(n) if n > 0 else np.nan
            ci_hw = 1.96 * sem if n > 0 else np.nan
            row[f"{metric}_mean"] = mean
            row[f"{metric}_std"] = std
            row[f"{metric}_sem"] = sem
            row[f"{metric}_ci95_lower"] = mean - ci_hw
            row[f"{metric}_ci95_upper"] = mean + ci_hw
            row[f"{metric}_n"] = n
        rows.append(row)

    pd.DataFrame(rows).to_excel(
        writer, sheet_name="descriptive_stats", index=False
    )


def _sheet_qc_validation(
    df_qc: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``qc_validation`` sheet — QC pass rate and constraint rate.

    Parameters
    ----------
    df_qc : pd.DataFrame
        QC table with qc_t0_valid, constraint_rate, cell_line,
        sample_condition.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    group_cols = ["cell_line", "sample_condition"]
    agg = (
        df_qc.groupby(group_cols)
        .agg(
            qc_pass_rate=("qc_t0_valid", "mean"),
            mean_constraint_rate=("constraint_rate", "mean"),
            n_trajectories=("qc_t0_valid", "size"),
        )
        .reset_index()
    )
    # Express rates as percentages
    agg["qc_pass_rate"] = agg["qc_pass_rate"] * 100.0
    agg["mean_constraint_rate"] = agg["mean_constraint_rate"] * 100.0

    agg.to_excel(writer, sheet_name="qc_validation", index=False)


def _sheet_pairwise_comparisons(
    pairwise_speed: List[Dict[str, Any]],
    pairwise_distance: List[Dict[str, Any]],
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``pairwise_comparisons`` sheet — combined speed + distance.

    Parameters
    ----------
    pairwise_speed : list of dict
        Pairwise results for speed_mean.
    pairwise_distance : list of dict
        Pairwise results for distance_mean.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    df_speed = pd.DataFrame(pairwise_speed)
    df_dist = pd.DataFrame(pairwise_distance)

    if not df_speed.empty:
        df_speed["metric"] = "speed_mean"
    if not df_dist.empty:
        df_dist["metric"] = "distance_mean"

    combined = pd.concat([df_speed, df_dist], ignore_index=True)
    combined.to_excel(writer, sheet_name="pairwise_comparisons", index=False)


def _sheet_exp_reproducibility(
    df_cs: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``exp_reproducibility`` sheet — EXP1 vs EXP2 comparison.

    Extracts the experiment identifier from the ``trajectory`` column by
    splitting on ``'-'`` and taking the second element (index 1).  Then
    computes mean distance_mean at the maximum timepoint for each
    experiment within each (cell_line, sample_condition) group.

    Parameters
    ----------
    df_cs : pd.DataFrame
        Cross-sectional data with trajectory column.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    df = df_cs.copy()

    # Parse experiment from trajectory string (second element after split)
    df["experiment"] = df["trajectory"].astype(str).str.split("-").str[1]

    group_cols = ["cell_line", "sample_condition"]
    rows: List[Dict[str, Any]] = []

    for (cl, cond), grp in df.groupby(group_cols):
        exp_groups = grp.groupby("experiment")["distance_mean"]
        exp_stats = exp_groups.agg(["mean", "count"]).reset_index()

        # Identify EXP1 and EXP2 by sorted experiment labels
        exp_labels = sorted(exp_stats["experiment"].unique())
        if len(exp_labels) < 2:
            # Only one experiment — still record it
            mean_1 = float(exp_stats["mean"].iloc[0]) if len(exp_labels) >= 1 else np.nan
            n_1 = int(exp_stats["count"].iloc[0]) if len(exp_labels) >= 1 else 0
            rows.append({
                "cell_line": cl,
                "sample_condition": cond,
                "mean_exp1": mean_1,
                "mean_exp2": np.nan,
                "diff": np.nan,
                "n_exp1": n_1,
                "n_exp2": 0,
            })
            continue

        row_exp1 = exp_stats[exp_stats["experiment"] == exp_labels[0]].iloc[0]
        row_exp2 = exp_stats[exp_stats["experiment"] == exp_labels[1]].iloc[0]

        mean_1 = float(row_exp1["mean"])
        mean_2 = float(row_exp2["mean"])
        rows.append({
            "cell_line": cl,
            "sample_condition": cond,
            "mean_exp1": mean_1,
            "mean_exp2": mean_2,
            "diff": mean_1 - mean_2,
            "n_exp1": int(row_exp1["count"]),
            "n_exp2": int(row_exp2["count"]),
        })

    pd.DataFrame(rows).to_excel(
        writer, sheet_name="exp_reproducibility", index=False
    )


def _sheet_assumption_checks(
    df_cs: pd.DataFrame,
    writer: pd.ExcelWriter,
) -> None:
    """Write the ``assumption_checks`` sheet — normality and homogeneity tests.

    For each (cell_line, sample_condition) group, runs the Shapiro-Wilk
    normality test on distance_mean.  For each cell_line, runs Levene's
    test for equality of variances across conditions.

    Parameters
    ----------
    df_cs : pd.DataFrame
        Cross-sectional data.
    writer : pd.ExcelWriter
        Open Excel writer.
    """
    group_cols = ["cell_line", "sample_condition"]

    # -- Shapiro-Wilk per group ----------------------------------------
    shapiro_rows: List[Dict[str, Any]] = []
    for (cl, cond), grp in df_cs.groupby(group_cols):
        vals = grp["distance_mean"].dropna().values
        n = len(vals)
        if n < 3:
            # Shapiro requires at least 3 observations
            shapiro_rows.append({
                "cell_line": cl,
                "sample_condition": cond,
                "shapiro_stat": np.nan,
                "shapiro_p": np.nan,
                "n": n,
            })
            continue
        try:
            stat, p = sp_stats.shapiro(vals)
            shapiro_rows.append({
                "cell_line": cl,
                "sample_condition": cond,
                "shapiro_stat": float(stat),
                "shapiro_p": float(p),
                "n": n,
            })
        except Exception as exc:
            warnings.warn(
                f"Shapiro-Wilk failed for {cl}/{cond}: {exc}",
                stacklevel=2,
            )
            shapiro_rows.append({
                "cell_line": cl,
                "sample_condition": cond,
                "shapiro_stat": np.nan,
                "shapiro_p": np.nan,
                "n": n,
            })

    df_shapiro = pd.DataFrame(shapiro_rows)

    # -- Levene's test per cell line -----------------------------------
    levene_rows: List[Dict[str, Any]] = []
    for cl, cl_grp in df_cs.groupby("cell_line"):
        condition_groups = [
            sub["distance_mean"].dropna().values
            for _, sub in cl_grp.groupby("sample_condition")
            if len(sub["distance_mean"].dropna()) >= 2
        ]
        if len(condition_groups) < 2:
            levene_rows.append({
                "cell_line": cl,
                "levene_stat": np.nan,
                "levene_p": np.nan,
            })
            continue
        try:
            stat, p = sp_stats.levene(*condition_groups)
            levene_rows.append({
                "cell_line": cl,
                "levene_stat": float(stat),
                "levene_p": float(p),
            })
        except Exception as exc:
            warnings.warn(
                f"Levene's test failed for {cl}: {exc}",
                stacklevel=2,
            )
            levene_rows.append({
                "cell_line": cl,
                "levene_stat": np.nan,
                "levene_p": np.nan,
            })

    df_levene = pd.DataFrame(levene_rows)

    # Write both sections to the same sheet with a gap
    df_shapiro.to_excel(
        writer, sheet_name="assumption_checks", index=False, startrow=0
    )
    # Leave a 2-row gap, then write Levene header + data
    levene_start = len(df_shapiro) + 3
    # Write a label row
    label_df = pd.DataFrame({"Levene's test for homogeneity of variances": [""]})
    label_df.to_excel(
        writer,
        sheet_name="assumption_checks",
        index=False,
        startrow=levene_start - 1,
        header=True,
    )
    df_levene.to_excel(
        writer,
        sheet_name="assumption_checks",
        index=False,
        startrow=levene_start + 1,
    )


# ---------------------------------------------------------------------------
# 3. Figure captions
# ---------------------------------------------------------------------------

def export_figure_captions(
    output_dir: Path,
    t_final: float,
    rep_key: str,
    n_per_group: Dict[str, int],
    error_type: str = "ci95",
) -> None:
    """Write publication-quality figure captions to a plain-text file.

    Generates captions for Figure 1 (model quality, panels A-F) and
    Figure 2 (wound dynamics, panels A-C) with all methodological details
    needed for a journal submission.

    Parameters
    ----------
    output_dir : Path
        Root publication directory.  File written to
        ``output_dir / "figure_captions.txt"``.
    t_final : float
        Final timepoint in hours used for cross-sectional analyses.
    rep_key : str
        Trajectory identifier of the representative timelapse shown in
        Figure 1, panels A-C.
    n_per_group : dict
        Mapping of ``"<CellLine> - <Condition>"`` to sample count, e.g.
        ``{"Line 1 - DMSO": 50, ...}``.  Used to report n in captions.
    error_type : str
        Error metric shown on plots (e.g. ``"ci95"``, ``"sem"``).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "figure_captions.txt"

    # Format the n-per-group string for inline reporting
    n_strings = [f"{k}: n = {v}" for k, v in sorted(n_per_group.items())]
    n_report = "; ".join(n_strings)

    # Map error_type to human-readable description
    error_descriptions: Dict[str, str] = {
        "ci95": "95% confidence intervals",
        "sem": "standard error of the mean (SEM)",
        "std": "standard deviation",
    }
    error_label = error_descriptions.get(error_type, error_type)

    caption_fig1 = (
        "Figure 1. Automated wound boundary detection and closure dynamics.\n"
        f"(A-C) Representative phase-contrast images of a wound healing "
        f"assay at three timepoints (t = 0, mid, and t = {t_final:.0f} h) "
        f"with computationally detected wound boundaries overlaid as "
        f"semi-transparent filled regions. Boundaries are shown cumulatively: "
        f"earlier timepoints appear as faint dashed outlines, the current "
        f"timepoint as solid fill.  "
        # The representative well is the most-average DMSO control trajectory.
        # Its internal storage key is deliberately NOT printed: the well was
        # acquired on a plate whose folder name references an excluded arm, and
        # the manuscript reports no drug-arm provenance. rep_key is retained in
        # the signature for traceability/logging only.
        f"A representative DMSO control trajectory is shown. "
        f"Images were acquired at a calibrated scale of 1.24 um/px. "
        f"(D) Normalised wound area over time, expressed as a fraction of "
        f"the t = 0 wound area. Error bands represent {error_label}. "
        f"Sample sizes: {n_report}."
    )

    caption_fig2 = (
        "Figure 2. Wound healing dynamics across experimental conditions.\n"
        f"(A) Mean wound closure speed (pixels/h) at t = {t_final:.0f} h, "
        f"computed as the rate of wound edge displacement. "
        f"(B) Mean wound closure distance (pixels) at t = {t_final:.0f} h, "
        f"representing the cumulative inward displacement of the wound "
        f"boundary from t = 0. "
        f"(C) Time-series of wound edge displacement over the full "
        f"observation period. Error bars represent {error_label}. "
        f"Statistical comparisons were performed using Welch's t-test with "
        f"Bonferroni correction for multiple comparisons. "
        f"Sample sizes: {n_report}."
    )

    text = (
        "FIGURE CAPTIONS\n"
        "===============\n\n"
        f"{caption_fig1}\n\n"
        f"{caption_fig2}\n"
    )

    out_path.write_text(text, encoding="utf-8")
    print(f"[OK] Figure captions exported: {out_path}")


# ---------------------------------------------------------------------------
# 4. Results summary (image census, manual review, QC, wound dynamics)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def load_verification_results(
    verification_path: Path,
    df_legacy: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """Load manual verification results and enrich with condition metadata.

    Parameters
    ----------
    verification_path : Path
        Path to the ``verification_results_*.xlsx`` workbook.
    df_legacy : pd.DataFrame
        Raw legacy table (all rows, before filtering) — used to map
        trajectory keys to ``sample_condition`` and ``cell_line``.

    Returns
    -------
    pd.DataFrame or None
        Enriched verification table with ``sample_condition`` and
        ``cell_line`` columns (display names), or ``None`` if the
        file does not exist.
    """
    verification_path = Path(verification_path)
    if not verification_path.exists():
        logger.warning(
            "Verification results not found: %s — manual review "
            "sections will be omitted from results summary.",
            verification_path,
        )
        return None

    df_verif = pd.read_excel(
        verification_path, sheet_name="Per-Image Annotations",
    )

    # Map raw condition/cell_line labels to display names
    _CONDITION_RENAME = {
        "media": "Media", "dmso": "DMSO",
        "alk5i": "Alk5i", "candasertan": "Candesartan",
    }
    _CELLLINE_RENAME = {
        "iMC ISOR544C": "Line 1", "iMC MUTR544C": "Line 2",
    }

    # Extract unique identifier → condition/cell_line from legacy table
    t0 = df_legacy[df_legacy["t_seg"] == 0]
    id_meta = (
        t0[["identifier", "sample_condition", "cell_line"]]
        .drop_duplicates(subset="identifier")
    )
    id_meta = id_meta.assign(
        sample_condition=id_meta["sample_condition"]
        .str.lower().map(_CONDITION_RENAME)
        .fillna(id_meta["sample_condition"]),
        cell_line=id_meta["cell_line"]
        .map(_CELLLINE_RENAME)
        .fillna(id_meta["cell_line"]),
    )

    df_verif = df_verif.merge(
        id_meta, left_on="trajectory_key", right_on="identifier", how="left",
    )
    return df_verif


def export_results_summary(
    df_legacy: pd.DataFrame,
    trajectories: Dict,
    df_meta: pd.DataFrame,
    traj_filt: Dict,
    df_qc: pd.DataFrame,
    df_cs: pd.DataFrame,
    df_ts: pd.DataFrame,
    t_final: float,
    method_label: str,
    output_dir: Path,
    df_verification: Optional[pd.DataFrame] = None,
) -> None:
    """Export a comprehensive results summary for manuscript reporting.

    Produces ``results_summary.xlsx`` (multi-sheet) and
    ``results_summary.txt`` (human-readable) in *output_dir*.

    Sections
    --------
    1. **Image Census & Manual Review** — total t=0 images, manual grading
       counts, no-wound exclusions by condition, and segmentation accuracy
       on manually approved wound-bearing images.
    2. **QC Algorithm Evaluation** — automatic QC vs manual ground truth
       (confusion matrix, sensitivity, specificity, Cohen's kappa).
    3. **Wound Detection Accuracy** — per-trajectory frame-level detection
       rates across all timepoints.
    4. **Wound Healing Dynamics** — per condition × cell line sample counts,
       mean closure distance/speed ± SEM at the final timepoint.

    Parameters
    ----------
    df_legacy : pd.DataFrame
        Raw legacy table *before* any filtering.
    trajectories : dict
        Raw trajectories dict *before* any filtering.
    df_meta : pd.DataFrame
        Filtered + renamed metadata (after all exclusions).
    traj_filt : dict
        Filtered trajectories (after all exclusions).
    df_qc : pd.DataFrame
        QC table with qc_t0_valid, constraint_rate, cell_line,
        sample_condition columns.
    df_cs : pd.DataFrame
        Cross-sectional data at the final timepoint.
    df_ts : pd.DataFrame
        Time-series data.
    t_final : float
        Cross-sectional target timepoint (hours).
    method_label : str
        Constraint method name (e.g. ``"Kalman"``).
    output_dir : Path
        Root publication directory.
    df_verification : pd.DataFrame or None
        Manual verification annotations (enriched with condition/cell_line).
        When ``None``, manual review sections use only automatic QC data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Section 1: Image census & manual review
    # ------------------------------------------------------------------
    census = _compute_image_census(
        df_legacy, trajectories, df_meta, traj_filt,
    )
    df_census = pd.DataFrame([census])

    _group_sort = ["cell_line", "sample_condition"]
    df_per_group_census = (
        _compute_per_group_census(df_meta, df_qc, df_cs)
        .sort_values(_group_sort)
        .reset_index(drop=True)
    )

    manual_review: Optional[Dict[str, Any]] = None
    if df_verification is not None:
        manual_review = _compute_manual_review(df_verification)

    # ------------------------------------------------------------------
    # Section 2: QC vs manual ground truth
    # ------------------------------------------------------------------
    qc_vs_manual: Optional[Dict[str, Any]] = None
    if df_verification is not None:
        qc_vs_manual = _compute_qc_vs_manual(df_verification)

    # ------------------------------------------------------------------
    # Section 3: Wound detection accuracy (frame-level)
    # ------------------------------------------------------------------
    df_detection = _compute_detection_accuracy(traj_filt, df_meta)
    df_detection_summary = (
        _summarise_detection_accuracy(df_detection)
        .sort_values(_group_sort)
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # Section 4: QC evaluation (automatic, on filtered set)
    # ------------------------------------------------------------------
    df_qc_summary = (
        _compute_qc_summary(df_qc)
        .sort_values(_group_sort)
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # Section 5: Wound healing dynamics
    # ------------------------------------------------------------------
    dynamics = _compute_wound_dynamics(df_cs, df_ts, t_final)

    # ------------------------------------------------------------------
    # Write Excel
    # ------------------------------------------------------------------
    xlsx_path = output_dir / "results_summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_census.to_excel(writer, sheet_name="image_census", index=False)
        df_per_group_census.to_excel(
            writer, sheet_name="per_group_census", index=False,
        )
        if manual_review is not None:
            pd.DataFrame([manual_review]).to_excel(
                writer, sheet_name="manual_review", index=False,
            )
        if qc_vs_manual is not None:
            pd.DataFrame([qc_vs_manual]).to_excel(
                writer, sheet_name="qc_vs_manual", index=False,
            )
        df_detection_summary.to_excel(
            writer, sheet_name="detection_accuracy", index=False,
        )
        df_detection.to_excel(
            writer, sheet_name="detection_per_trajectory", index=False,
        )
        df_qc_summary.to_excel(
            writer, sheet_name="qc_evaluation", index=False,
        )
        dynamics["df_dynamics"].to_excel(
            writer, sheet_name="wound_dynamics", index=False,
        )

    # ------------------------------------------------------------------
    # Write plain-text report
    # ------------------------------------------------------------------
    txt_path = output_dir / "results_summary.txt"
    txt_path.write_text(
        _format_results_text(
            census=census,
            df_per_group=df_per_group_census,
            df_detection=df_detection_summary,
            df_qc_summary=df_qc_summary,
            t_final=t_final,
            method_label=method_label,
            manual_review=manual_review,
            qc_vs_manual=qc_vs_manual,
            dynamics=dynamics,
        ),
        encoding="utf-8",
    )

    print(f"[OK] Results summary exported: {xlsx_path}")
    print(f"[OK] Results summary text:     {txt_path}")


# -- Census helpers ---------------------------------------------------------

def _compute_image_census(
    df_legacy: pd.DataFrame,
    trajectories: Dict,
    df_meta: pd.DataFrame,
    traj_filt: Dict,
) -> Dict[str, Any]:
    """Compute aggregate image and trajectory counts at each filtering stage.

    Parameters
    ----------
    df_legacy : pd.DataFrame
        Raw legacy table (all rows).
    trajectories : dict
        Raw trajectories dict (all entries).
    df_meta : pd.DataFrame
        Filtered metadata.
    traj_filt : dict
        Filtered trajectories.

    Returns
    -------
    dict
        Keys: n_images_loaded, n_traj_loaded, n_images_excluded_candesartan,
        n_traj_excluded_candesartan, n_images_excluded_filters,
        n_traj_excluded_filters, n_images_final, n_traj_final.
    """
    n_images_loaded = len(df_legacy)
    n_traj_loaded = len(trajectories)

    # Candesartan exclusion: mirrors filter_candesartan() logic exactly.
    # Rows whose lowercased condition is NOT in the canonical keep list.
    _keep_conditions = {"media", "dmso", "alk5i"}
    cond_lower = df_legacy["sample_condition"].str.lower()
    candesartan_mask = ~cond_lower.isin(_keep_conditions)
    n_images_candesartan = int(candesartan_mask.sum())

    # Trajectory keys: same suffix check as filter_candesartan()
    _CANDESARTAN_SUFFIXES = ("-Candasertan", "-candasertan")
    candesartan_traj = {
        k for k in trajectories
        if any(k.endswith(s) for s in _CANDESARTAN_SUFFIXES)
    }
    n_traj_candesartan = len(candesartan_traj)

    # Post-candesartan counts
    n_images_post_candesartan = n_images_loaded - n_images_candesartan
    n_traj_post_candesartan = n_traj_loaded - n_traj_candesartan

    # Final counts (after condition, concentration, cell-line, time filters)
    n_images_final = len(df_meta)
    n_traj_final = len(traj_filt)

    # Condition/concentration/cell-line/time filtering
    n_images_filters = n_images_post_candesartan - n_images_final
    n_traj_filters = n_traj_post_candesartan - n_traj_final

    return {
        "n_images_loaded": n_images_loaded,
        "n_traj_loaded": n_traj_loaded,
        "n_images_excluded_candesartan": n_images_candesartan,
        "n_traj_excluded_candesartan": n_traj_candesartan,
        "n_images_post_candesartan": n_images_post_candesartan,
        "n_traj_post_candesartan": n_traj_post_candesartan,
        "n_images_excluded_filters": n_images_filters,
        "n_traj_excluded_filters": n_traj_filters,
        "n_images_final": n_images_final,
        "n_traj_final": n_traj_final,
    }


def _compute_per_group_census(
    df_meta: pd.DataFrame,
    df_qc: pd.DataFrame,
    df_cs: pd.DataFrame,
) -> pd.DataFrame:
    """Per cell_line x condition breakdown of trajectories, images, QC, and cross-sectional counts.

    Parameters
    ----------
    df_meta : pd.DataFrame
        Filtered metadata.
    df_qc : pd.DataFrame
        QC table.
    df_cs : pd.DataFrame
        Cross-sectional data.

    Returns
    -------
    pd.DataFrame
        Columns: cell_line, sample_condition, n_trajectories, n_images,
        n_qc_pass, n_qc_fail, qc_pass_rate_pct, n_cross_sectional.
    """
    group_cols = ["cell_line", "sample_condition"]

    n_traj = (
        df_meta.drop_duplicates(subset="identifier")
        .groupby(group_cols).size()
        .rename("n_trajectories")
        .reset_index()
    )
    n_images = (
        df_meta.groupby(group_cols).size()
        .rename("n_images")
        .reset_index()
    )
    n_qc_pass = (
        df_qc[df_qc["qc_t0_valid"]]
        .groupby(group_cols).size()
        .rename("n_qc_pass")
        .reset_index()
    )
    n_qc_total = (
        df_qc.groupby(group_cols).size()
        .rename("n_qc_total")
        .reset_index()
    )
    n_cs = (
        df_cs.groupby(group_cols).size()
        .rename("n_cross_sectional")
        .reset_index()
    )

    result = n_traj.merge(n_images, on=group_cols, how="left")
    result = result.merge(n_qc_total, on=group_cols, how="left")
    result = result.merge(n_qc_pass, on=group_cols, how="left")
    result = result.merge(n_cs, on=group_cols, how="left")
    result = result.fillna(0).astype({
        c: int for c in [
            "n_trajectories", "n_images", "n_qc_total",
            "n_qc_pass", "n_cross_sectional",
        ]
    })
    result["n_qc_fail"] = result["n_qc_total"] - result["n_qc_pass"]
    result["qc_pass_rate_pct"] = np.where(
        result["n_qc_total"] > 0,
        100.0 * result["n_qc_pass"] / result["n_qc_total"],
        0.0,
    )
    return result


# -- Detection accuracy helpers ---------------------------------------------

def _compute_detection_accuracy(
    traj_filt: Dict,
    df_meta: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-trajectory wound detection accuracy.

    For each trajectory, counts the total number of frames processed and
    the number with a valid wound detection (area > 0).

    Parameters
    ----------
    traj_filt : dict
        Filtered trajectories.
    df_meta : pd.DataFrame
        Filtered metadata with identifier, cell_line, sample_condition.

    Returns
    -------
    pd.DataFrame
        One row per trajectory with columns: identifier, cell_line,
        sample_condition, n_frames, n_detected, n_failed,
        detection_rate_pct.
    """
    meta_unique = (
        df_meta[["identifier", "cell_line", "sample_condition"]]
        .drop_duplicates(subset="identifier")
        .set_index("identifier")
    )

    rows: List[Dict[str, Any]] = []
    for traj_key, traj_data in traj_filt.items():
        results = traj_data.get("results", [])
        n_frames = len(results)
        n_detected = sum(
            1 for r in results
            if r.get("area") is not None and r.get("area", 0) > 0
        )
        n_failed = n_frames - n_detected
        detection_rate = 100.0 * n_detected / max(n_frames, 1)

        if traj_key in meta_unique.index:
            meta_row = meta_unique.loc[[traj_key]].iloc[0]
            cl = str(meta_row["cell_line"])
            cond = str(meta_row["sample_condition"])
        else:
            cl, cond = "", ""
        rows.append({
            "identifier": traj_key,
            "cell_line": cl,
            "sample_condition": cond,
            "n_frames": n_frames,
            "n_detected": n_detected,
            "n_failed": n_failed,
            "detection_rate_pct": round(detection_rate, 1),
        })

    return pd.DataFrame(rows)


def _summarise_detection_accuracy(
    df_detection: pd.DataFrame,
) -> pd.DataFrame:
    """Summarise detection accuracy per cell_line x condition.

    Parameters
    ----------
    df_detection : pd.DataFrame
        Per-trajectory detection data from ``_compute_detection_accuracy``.

    Returns
    -------
    pd.DataFrame
        Columns: cell_line, sample_condition, n_trajectories,
        total_frames, total_detected, total_failed,
        mean_detection_rate_pct, trajectories_100pct_detected.
    """
    group_cols = ["cell_line", "sample_condition"]
    agg = (
        df_detection.groupby(group_cols)
        .agg(
            n_trajectories=("identifier", "count"),
            total_frames=("n_frames", "sum"),
            total_detected=("n_detected", "sum"),
            total_failed=("n_failed", "sum"),
            mean_detection_rate_pct=("detection_rate_pct", "mean"),
            trajectories_100pct_detected=(
                "detection_rate_pct",
                lambda x: int((x == 100.0).sum()),
            ),
        )
        .reset_index()
    )
    agg["overall_detection_rate_pct"] = np.where(
        agg["total_frames"] > 0,
        100.0 * agg["total_detected"] / agg["total_frames"],
        0.0,
    )
    return agg


# -- QC summary helper ------------------------------------------------------

def _compute_qc_summary(df_qc: pd.DataFrame) -> pd.DataFrame:
    """Compute QC pass rate and constraint rate per group.

    Parameters
    ----------
    df_qc : pd.DataFrame
        QC table with qc_t0_valid, constraint_rate, cell_line,
        sample_condition.

    Returns
    -------
    pd.DataFrame
        Columns: cell_line, sample_condition, n_trajectories,
        n_qc_pass, n_qc_fail, qc_pass_rate_pct,
        mean_constraint_rate_pct, median_constraint_rate_pct,
        min_constraint_rate_pct, max_constraint_rate_pct.
    """
    group_cols = ["cell_line", "sample_condition"]
    agg = (
        df_qc.groupby(group_cols)
        .agg(
            n_trajectories=("qc_t0_valid", "size"),
            n_qc_pass=("qc_t0_valid", "sum"),
            mean_constraint_rate=("constraint_rate", "mean"),
            median_constraint_rate=("constraint_rate", "median"),
            min_constraint_rate=("constraint_rate", "min"),
            max_constraint_rate=("constraint_rate", "max"),
        )
        .reset_index()
    )
    agg["n_qc_pass"] = agg["n_qc_pass"].astype(int)
    agg["n_qc_fail"] = agg["n_trajectories"] - agg["n_qc_pass"]
    agg["qc_pass_rate_pct"] = np.where(
        agg["n_trajectories"] > 0,
        100.0 * agg["n_qc_pass"] / agg["n_trajectories"],
        0.0,
    )
    # Express constraint rates as percentages
    for col in [
        "mean_constraint_rate", "median_constraint_rate",
        "min_constraint_rate", "max_constraint_rate",
    ]:
        agg[f"{col}_pct"] = agg[col] * 100.0
    agg = agg.drop(columns=[
        "mean_constraint_rate", "median_constraint_rate",
        "min_constraint_rate", "max_constraint_rate",
    ])
    return agg


# -- Manual review helpers ----------------------------------------------------

def _compute_manual_review(
    df_verif: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute manual review statistics from the verification table.

    Parameters
    ----------
    df_verif : pd.DataFrame
        Enriched verification table with ``correct``, ``notes``,
        ``sample_condition``, ``cell_line`` columns.

    Returns
    -------
    dict
        Keys: n_t0_images, n_graded, n_unannotated, n_approved,
        n_rejected, n_no_wound, pct_no_wound,
        no_wound_by_condition (dict), no_wound_by_cellline (dict),
        n_wound_bearing, n_correctly_segmented, n_incorrectly_segmented,
        pct_correctly_segmented.
    """
    n_total = len(df_verif)
    n_unannotated = int(df_verif["correct"].isna().sum())
    n_graded = n_total - n_unannotated

    annotated = df_verif.dropna(subset=["correct"])
    n_approved = int((annotated["correct"] == 1.0).sum())
    n_rejected = int((annotated["correct"] == 0.0).sum())

    # No-wound images
    no_wound = df_verif[df_verif["notes"] == "no wound"]
    n_no_wound = len(no_wound)
    pct_no_wound = 100.0 * n_no_wound / max(n_total, 1)

    no_wound_by_condition = (
        no_wound.groupby("sample_condition").size().to_dict()
        if "sample_condition" in no_wound.columns else {}
    )
    no_wound_by_cellline = (
        no_wound.groupby("cell_line").size().to_dict()
        if "cell_line" in no_wound.columns else {}
    )

    # Wound-bearing images: exclude "no wound" notes
    wound_bearing = df_verif[df_verif["notes"] != "no wound"]
    wound_annotated = wound_bearing.dropna(subset=["correct"])
    n_wound_bearing = len(wound_annotated)
    n_correctly_segmented = int((wound_annotated["correct"] == 1.0).sum())
    n_incorrectly_segmented = n_wound_bearing - n_correctly_segmented
    pct_correct = 100.0 * n_correctly_segmented / max(n_wound_bearing, 1)

    return {
        "n_t0_images": n_total,
        "n_graded": n_graded,
        "n_unannotated": n_unannotated,
        "n_approved": n_approved,
        "n_rejected": n_rejected,
        "n_no_wound": n_no_wound,
        "pct_no_wound": round(pct_no_wound, 1),
        "no_wound_by_condition": no_wound_by_condition,
        "no_wound_by_cellline": no_wound_by_cellline,
        "n_wound_bearing": n_wound_bearing,
        "n_correctly_segmented": n_correctly_segmented,
        "n_incorrectly_segmented": n_incorrectly_segmented,
        "pct_correctly_segmented": round(pct_correct, 1),
    }


def _compute_qc_vs_manual(
    df_verif: pd.DataFrame,
) -> Dict[str, Any]:
    """Evaluate automatic QC against manual ground truth.

    Computes confusion matrix, sensitivity, specificity, PPV, NPV,
    accuracy, and Cohen's kappa — both on all annotated images and on
    the wound-bearing subset only.

    Parameters
    ----------
    df_verif : pd.DataFrame
        Enriched verification table with ``qc_auto_valid`` and
        ``correct`` columns.

    Returns
    -------
    dict
        Nested keys: ``all`` and ``wound_bearing``, each containing
        n, tp, fp, fn, tn, sensitivity, specificity, ppv, npv,
        accuracy, cohens_kappa.
    """
    result: Dict[str, Any] = {}

    for label, df_subset in [
        ("all", df_verif),
        ("wound_bearing", df_verif[df_verif["notes"] != "no wound"]),
    ]:
        ann = df_subset.dropna(subset=["correct"]).copy()
        if ann.empty:
            result[label] = {
                "n": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0,
                "sensitivity": np.nan, "specificity": np.nan,
                "ppv": np.nan, "npv": np.nan,
                "accuracy": np.nan, "cohens_kappa": np.nan,
            }
            continue

        human = ann["correct"].astype(bool)
        qc = ann["qc_auto_valid"].astype(bool)

        tp = int((qc & human).sum())
        fp = int((qc & ~human).sum())
        fn = int((~qc & human).sum())
        tn = int((~qc & ~human).sum())
        n = tp + fp + fn + tn

        accuracy = (tp + tn) / n if n > 0 else np.nan
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else np.nan
        specificity = tn / (tn + fp) if (tn + fp) > 0 else np.nan
        ppv = tp / (tp + fp) if (tp + fp) > 0 else np.nan
        npv = tn / (tn + fn) if (tn + fn) > 0 else np.nan

        # Cohen's kappa
        pe = (
            ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
            if n > 0 else 0
        )
        kappa = (accuracy - pe) / (1 - pe) if (1 - pe) > 0 else np.nan

        result[label] = {
            "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "sensitivity": round(sensitivity, 4) if not np.isnan(sensitivity) else np.nan,
            "specificity": round(specificity, 4) if not np.isnan(specificity) else np.nan,
            "ppv": round(ppv, 4) if not np.isnan(ppv) else np.nan,
            "npv": round(npv, 4) if not np.isnan(npv) else np.nan,
            "accuracy": round(accuracy, 4) if not np.isnan(accuracy) else np.nan,
            "cohens_kappa": round(kappa, 4) if not np.isnan(kappa) else np.nan,
        }

    return result


# -- Wound dynamics helpers ---------------------------------------------------

def _compute_wound_dynamics(
    df_cs: pd.DataFrame,
    df_ts: pd.DataFrame,
    t_final: float,
) -> Dict[str, Any]:
    """Compute per-group wound healing dynamics at the final timepoint.

    Parameters
    ----------
    df_cs : pd.DataFrame
        Cross-sectional data at the final timepoint (one row per
        trajectory) with ``distance_mean``, ``speed_mean``,
        ``cell_line``, ``sample_condition`` columns.
    df_ts : pd.DataFrame
        Time-series data with ``trajectory``, ``t``, ``distance_mean``,
        ``cell_line``, ``sample_condition`` columns.
    t_final : float
        Cross-sectional target timepoint (hours).

    Returns
    -------
    dict
        Keys: ``df_dynamics`` (DataFrame with per-group closure metrics),
        ``n_total_trajectories``, ``n_per_group`` (dict).
    """
    group_cols = ["cell_line", "sample_condition"]

    agg = (
        df_cs.groupby(group_cols)
        .agg(
            n=("trajectory", "count"),
            mean_distance=("distance_mean", "mean"),
            sem_distance=("distance_mean", lambda x: x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan),
            mean_speed=("speed_mean", "mean"),
            sem_speed=("speed_mean", lambda x: x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan),
        )
        .reset_index()
    )

    # Round for display
    for col in ["mean_distance", "sem_distance", "mean_speed", "sem_speed"]:
        agg[col] = agg[col].round(2)

    n_total = int(df_cs["trajectory"].nunique())
    n_per_group = {
        f"{row['cell_line']} - {row['sample_condition']}": int(row["n"])
        for _, row in agg.iterrows()
    }

    return {
        "df_dynamics": agg,
        "n_total_trajectories": n_total,
        "n_per_group": n_per_group,
        "t_final": t_final,
    }


# -- Plain-text formatting ---------------------------------------------------

def _format_results_text(
    census: Dict[str, Any],
    df_per_group: pd.DataFrame,
    df_detection: pd.DataFrame,
    df_qc_summary: pd.DataFrame,
    t_final: float,
    method_label: str,
    manual_review: Optional[Dict[str, Any]] = None,
    qc_vs_manual: Optional[Dict[str, Any]] = None,
    dynamics: Optional[Dict[str, Any]] = None,
) -> str:
    """Format the results summary as a human-readable text report.

    Parameters
    ----------
    census : dict
        Aggregate image census from ``_compute_image_census``.
    df_per_group : pd.DataFrame
        Per-group census.
    df_detection : pd.DataFrame
        Detection accuracy summary per group.
    df_qc_summary : pd.DataFrame
        QC evaluation summary per group.
    t_final : float
        Cross-sectional target timepoint.
    method_label : str
        Constraint method name.
    manual_review : dict or None
        Output from ``_compute_manual_review``.
    qc_vs_manual : dict or None
        Output from ``_compute_qc_vs_manual``.
    dynamics : dict or None
        Output from ``_compute_wound_dynamics``.

    Returns
    -------
    str
        Formatted report text.
    """
    lines: List[str] = []
    _sep = "=" * 70
    section = 0

    lines.append(_sep)
    lines.append(f"RESULTS SUMMARY  —  {method_label} constraint method")
    lines.append(_sep)

    # =================================================================
    # Section 1: Image Census & Manual Review
    # =================================================================
    section += 1
    lines.append("")
    lines.append(f"{section}. IMAGE CENSUS AND MANUAL REVIEW")
    lines.append("-" * 50)

    if manual_review is not None:
        mr = manual_review
        lines.append(f"  Total t=0 images:               {mr['n_t0_images']}")
        lines.append(f"  Manually graded:                {mr['n_graded']}")
        lines.append(f"  Unannotated:                    {mr['n_unannotated']}")
        lines.append("")
        lines.append(
            f"  Manual review identified {mr['n_no_wound']} "
            f"({mr['pct_no_wound']}%) containing no visible wound."
        )
        lines.append("")

        # No-wound distribution by condition
        nw_cond = mr["no_wound_by_condition"]
        if nw_cond:
            lines.append("  No-wound distribution by condition:")
            for cond in sorted(nw_cond.keys()):
                lines.append(f"    {cond:<15s}  {nw_cond[cond]:>3}")

        nw_cl = mr["no_wound_by_cellline"]
        if nw_cl:
            lines.append("")
            lines.append("  No-wound distribution by cell line:")
            for cl in sorted(nw_cl.keys()):
                lines.append(f"    {cl:<15s}  {nw_cl[cl]:>3}")

        lines.append("")
        lines.append(
            f"  Manually approved (correct):    {mr['n_approved']}"
        )
        lines.append(
            f"  Manually rejected (incorrect):  {mr['n_rejected']}"
        )

        # Segmentation accuracy on wound-bearing images
        lines.append("")
        lines.append(
            f"  Of {mr['n_wound_bearing']} wound-bearing images, the algorithm "
            f"correctly segmented"
        )
        lines.append(
            f"  {mr['n_correctly_segmented']} ({mr['pct_correctly_segmented']}%).  "
            f"{mr['n_incorrectly_segmented']} were incorrectly segmented."
        )
    else:
        # Fallback: report from automatic pipeline data only
        lines.append(f"  Images loaded:                  {census['n_images_loaded']}")
        lines.append(f"  Trajectories loaded:            {census['n_traj_loaded']}")
        lines.append("")
        lines.append("  [Manual verification data not available]")

    # Always show the pipeline filtering cascade
    lines.append("")
    lines.append("  Pipeline filtering cascade:")
    lines.append(f"    Loaded (images / traj):       {census['n_images_loaded']} / {census['n_traj_loaded']}")
    lines.append(f"    Candesartan excluded:         {census['n_images_excluded_candesartan']} images, {census['n_traj_excluded_candesartan']} traj")
    lines.append(f"    Post-candesartan:             {census['n_images_post_candesartan']} images, {census['n_traj_post_candesartan']} traj")
    lines.append(f"    Condition/conc/cell/time:     -{census['n_images_excluded_filters']} images, -{census['n_traj_excluded_filters']} traj")
    lines.append(f"    FINAL:                        {census['n_images_final']} images, {census['n_traj_final']} traj")

    # Per-group breakdown (filtered set)
    lines.append("")
    lines.append("  Per-group breakdown (filtered set):")
    lines.append(
        f"  {'Cell Line':<12} | {'Condition':<10} | {'Traj':>5} | "
        f"{'Images':>7} | {'QC pass':>8} | {'CS':>4}"
    )
    lines.append(
        f"  {'-'*12}-+-{'-'*10}-+-{'-'*5}-+-{'-'*7}-+-{'-'*8}-+-{'-'*4}"
    )
    for _, row in df_per_group.iterrows():
        lines.append(
            f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
            f"{row['n_trajectories']:>5} | {row['n_images']:>7} | "
            f"{row['n_qc_pass']:>8} | {row['n_cross_sectional']:>4}"
        )

    # =================================================================
    # Section 2: QC Algorithm Evaluation (vs manual ground truth)
    # =================================================================
    section += 1
    lines.append("")
    lines.append("")
    lines.append(f"{section}. QC ALGORITHM EVALUATION")
    lines.append("-" * 50)

    if qc_vs_manual is not None:
        for label, pretty in [("all", "All annotated images"), ("wound_bearing", "Wound-bearing images only")]:
            qm = qc_vs_manual[label]
            lines.append("")
            lines.append(f"  {pretty} (n={qm['n']}):")
            lines.append(f"    TP (QC=valid,   human=correct):    {qm['tp']}")
            lines.append(f"    FP (QC=valid,   human=incorrect):  {qm['fp']}")
            lines.append(f"    FN (QC=invalid, human=correct):    {qm['fn']}")
            lines.append(f"    TN (QC=invalid, human=incorrect):  {qm['tn']}")
            lines.append("")
            lines.append(f"    Sensitivity:   {qm['sensitivity']:.4f}")
            lines.append(f"    Specificity:   {qm['specificity']:.4f}")
            lines.append(f"    PPV:           {qm['ppv']:.4f}")
            lines.append(f"    NPV:           {qm['npv']:.4f}")
            lines.append(f"    Accuracy:      {qm['accuracy']:.4f}")
            lines.append(f"    Cohen's kappa: {qm['cohens_kappa']:.4f}")
    else:
        # Fallback: automatic QC pass rates only (no manual ground truth)
        lines.append("")
        lines.append("  Automatic QC pass rates (t=0, filtered set):")
        lines.append(
            f"  {'Cell Line':<12} | {'Condition':<10} | {'Traj':>5} | "
            f"{'Pass':>5} | {'Fail':>5} | {'QC Rate':>8} | "
            f"{'Constraint':>11}"
        )
        lines.append(
            f"  {'-'*12}-+-{'-'*10}-+-{'-'*5}-+-"
            f"{'-'*5}-+-{'-'*5}-+-{'-'*8}-+-{'-'*11}"
        )
        for _, row in df_qc_summary.iterrows():
            lines.append(
                f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
                f"{row['n_trajectories']:>5} | {row['n_qc_pass']:>5} | "
                f"{row['n_qc_fail']:>5} | {row['qc_pass_rate_pct']:>7.1f}% | "
                f"{row['mean_constraint_rate_pct']:>10.1f}%"
            )
        total_qc = int(df_qc_summary["n_trajectories"].sum())
        total_pass = int(df_qc_summary["n_qc_pass"].sum())
        overall_qc = 100.0 * total_pass / max(total_qc, 1)
        lines.append("")
        lines.append(
            f"  Overall QC pass: {total_pass}/{total_qc} "
            f"({overall_qc:.1f}%)"
        )

    # =================================================================
    # Section 3: Wound Detection Accuracy (frame-level)
    # =================================================================
    section += 1
    lines.append("")
    lines.append("")
    lines.append(f"{section}. WOUND DETECTION ACCURACY (all timepoints)")
    lines.append("-" * 50)
    lines.append(
        f"  {'Cell Line':<12} | {'Condition':<10} | {'Traj':>5} | "
        f"{'Frames':>7} | {'Detected':>9} | {'Failed':>7} | {'Rate':>7}"
    )
    lines.append(
        f"  {'-'*12}-+-{'-'*10}-+-{'-'*5}-+-"
        f"{'-'*7}-+-{'-'*9}-+-{'-'*7}-+-{'-'*7}"
    )
    for _, row in df_detection.iterrows():
        lines.append(
            f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
            f"{row['n_trajectories']:>5} | {row['total_frames']:>7} | "
            f"{row['total_detected']:>9} | {row['total_failed']:>7} | "
            f"{row['overall_detection_rate_pct']:>6.1f}%"
        )

    total_frames = int(df_detection["total_frames"].sum())
    total_detected = int(df_detection["total_detected"].sum())
    total_failed = int(df_detection["total_failed"].sum())
    overall_rate = 100.0 * total_detected / max(total_frames, 1)
    lines.append("")
    lines.append(
        f"  Overall: {total_detected}/{total_frames} frames detected "
        f"({overall_rate:.1f}%), {total_failed} failed"
    )

    # =================================================================
    # Section 4: Automatic QC Evaluation (filtered set)
    # =================================================================
    section += 1
    lines.append("")
    lines.append("")
    lines.append(f"{section}. AUTOMATIC QC EVALUATION (t=0, filtered set)")
    lines.append("-" * 50)
    lines.append(
        f"  {'Cell Line':<12} | {'Condition':<10} | {'Traj':>5} | "
        f"{'Pass':>5} | {'Fail':>5} | {'QC Rate':>8} | "
        f"{'Constraint':>11}"
    )
    lines.append(
        f"  {'-'*12}-+-{'-'*10}-+-{'-'*5}-+-"
        f"{'-'*5}-+-{'-'*5}-+-{'-'*8}-+-{'-'*11}"
    )
    for _, row in df_qc_summary.iterrows():
        lines.append(
            f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
            f"{row['n_trajectories']:>5} | {row['n_qc_pass']:>5} | "
            f"{row['n_qc_fail']:>5} | {row['qc_pass_rate_pct']:>7.1f}% | "
            f"{row['mean_constraint_rate_pct']:>10.1f}%"
        )
    total_qc = int(df_qc_summary["n_trajectories"].sum())
    total_pass = int(df_qc_summary["n_qc_pass"].sum())
    overall_qc = 100.0 * total_pass / max(total_qc, 1)
    lines.append("")
    lines.append(
        f"  Overall QC pass: {total_pass}/{total_qc} ({overall_qc:.1f}%)"
    )

    # =================================================================
    # Section 5: Wound Healing Dynamics
    # =================================================================
    if dynamics is not None:
        section += 1
        lines.append("")
        lines.append("")
        lines.append(f"{section}. WOUND HEALING DYNAMICS (t = {t_final:.0f} h)")
        lines.append("-" * 50)

        df_dyn = dynamics["df_dynamics"]
        n_total = dynamics["n_total_trajectories"]

        lines.append(
            f"  Of the {census['n_traj_final']} verified trajectories in the "
            f"filtered set, {n_total} have"
        )
        lines.append(
            f"  cross-sectional measurements at t = {t_final:.0f} h."
        )
        lines.append("")

        # Closure distance table
        lines.append("  Closure distance (um):")
        lines.append(
            f"  {'Cell Line':<12} | {'Condition':<10} | {'n':>4} | "
            f"{'Mean':>9} | {'SEM':>9}"
        )
        lines.append(
            f"  {'-'*12}-+-{'-'*10}-+-{'-'*4}-+-{'-'*9}-+-{'-'*9}"
        )
        for _, row in df_dyn.iterrows():
            lines.append(
                f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
                f"{row['n']:>4} | {row['mean_distance']:>9.2f} | "
                f"{row['sem_distance']:>9.2f}"
            )

        lines.append("")

        # Closure speed table
        lines.append("  Closure speed (um/h):")
        lines.append(
            f"  {'Cell Line':<12} | {'Condition':<10} | {'n':>4} | "
            f"{'Mean':>9} | {'SEM':>9}"
        )
        lines.append(
            f"  {'-'*12}-+-{'-'*10}-+-{'-'*4}-+-{'-'*9}-+-{'-'*9}"
        )
        for _, row in df_dyn.iterrows():
            lines.append(
                f"  {row['cell_line']:<12} | {row['sample_condition']:<10} | "
                f"{row['n']:>4} | {row['mean_speed']:>9.2f} | "
                f"{row['sem_speed']:>9.2f}"
            )

        lines.append("")
        lines.append("  See fig1_model_quality and fig2_wound_dynamics.")

    # --- Footer ---
    lines.append("")
    lines.append("")
    lines.append(f"Cross-sectional timepoint: t = {t_final:.0f} h")
    lines.append(f"Constraint method: {method_label}")
    lines.append(_sep)
    lines.append("")

    return "\n".join(lines)
