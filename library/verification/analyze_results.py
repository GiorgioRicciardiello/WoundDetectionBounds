"""
Verification Results Analysis
==============================

Reads the exported verification Excel workbook and computes publication-ready
statistics summarising algorithm performance.

Key analyses
------------
1. **Exclusions**: images annotated as "no wound" are excluded from accuracy
   metrics but counted separately.
2. **Detection accuracy**: fraction of wound-bearing images correctly
   segmented, broken down by exposure and experiment.
3. **QC algorithm evaluation**: sensitivity, specificity, PPV, NPV of the
   automatic QC flag versus human verdict — computed on all images and on
   wound-bearing images only.
4. **Pixel-level metrics**: Dice, IoU, precision, recall for images with
   manual edge corrections or polygon annotations.
5. **Summary tables**: DataFrames suitable for direct inclusion in a paper.

All results are saved to ``{output_dir}/verification_analysis/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


# ===================================================================
# Public API
# ===================================================================

def run_analysis(
    excel_path: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """Run the full verification analysis pipeline.

    Parameters
    ----------
    excel_path : Path
        Path to the exported ``verification_results_*.xlsx`` workbook
        (sheet "Per-Image Annotations").
    output_dir : Path
        Directory where analysis outputs (CSV tables) are written.

    Returns
    -------
    dict
        Nested dictionary with all computed statistics, suitable for
        programmatic access or rendering into a results section.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(excel_path, sheet_name="Per-Image Annotations")

    results: Dict[str, Any] = {}

    # ---- 1. Exclusions ----
    results["exclusions"] = _compute_exclusions(df)

    # ---- 2. Valid subset (wound present) ----
    df_valid = df[df["notes"] != "no wound"].copy()
    df_valid_annotated = df_valid.dropna(subset=["correct"]).copy()
    df_valid_annotated["correct_bool"] = df_valid_annotated["correct"].astype(bool)

    # ---- 3. Detection accuracy ----
    results["detection"] = _compute_detection_accuracy(df_valid_annotated)

    # ---- 4. QC evaluation (all images) ----
    df_all_annotated = df.dropna(subset=["correct"]).copy()
    df_all_annotated["correct_bool"] = df_all_annotated["correct"].astype(bool)
    results["qc_all"] = _compute_qc_metrics(df_all_annotated, label="all_images")

    # ---- 5. QC evaluation (wound-bearing only) ----
    results["qc_valid"] = _compute_qc_metrics(df_valid_annotated, label="wound_bearing")

    # ---- 6. Per-exposure × experiment breakdown ----
    results["breakdown"] = _compute_breakdown(df_valid_annotated)

    # ---- 7. Pixel-level metrics (where available) ----
    results["pixel_metrics"] = _compute_pixel_summary(df_valid_annotated)

    # ---- 8. Save tables ----
    _save_tables(results, output_dir)

    return results


# ===================================================================
# Internal analysis functions
# ===================================================================

def _compute_exclusions(df: pd.DataFrame) -> Dict[str, Any]:
    """Count and characterise excluded (no-wound) images.

    Parameters
    ----------
    df : DataFrame
        Full per-image annotations table.

    Returns
    -------
    dict
        Counts of no-wound images by exposure and experiment.
    """
    total = len(df)
    no_wound = df[df["notes"] == "no wound"]
    n_no_wound = len(no_wound)
    n_unannotated = df["correct"].isna().sum()

    no_wound_by_exposure = no_wound["exposure"].value_counts().to_dict()
    no_wound_by_experiment = no_wound["experiment"].value_counts().to_dict()
    no_wound_cross = pd.crosstab(
        no_wound["exposure"], no_wound["experiment"], margins=True
    )

    return {
        "total_images": total,
        "no_wound_count": n_no_wound,
        "unannotated_count": int(n_unannotated),
        "valid_count": total - n_no_wound,
        "no_wound_by_exposure": no_wound_by_exposure,
        "no_wound_by_experiment": no_wound_by_experiment,
        "no_wound_crosstab": no_wound_cross,
    }


def _compute_detection_accuracy(
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute detection accuracy on wound-bearing images.

    Parameters
    ----------
    df : DataFrame
        Annotated wound-bearing images only.

    Returns
    -------
    dict
        Overall and per-group accuracy.
    """
    n_total = len(df)
    n_correct = int(df["correct_bool"].sum())
    n_incorrect = n_total - n_correct
    accuracy = n_correct / n_total if n_total > 0 else np.nan

    return {
        "n_total": n_total,
        "n_correct": n_correct,
        "n_incorrect": n_incorrect,
        "accuracy": accuracy,
    }


def _compute_qc_metrics(
    df: pd.DataFrame,
    label: str,
) -> Dict[str, Any]:
    """Evaluate automatic QC against human verdicts.

    Parameters
    ----------
    df : DataFrame
        Must have ``qc_auto_valid`` (bool) and ``correct_bool`` (bool).
    label : str
        Description label for this subset.

    Returns
    -------
    dict
        Confusion matrix, sensitivity, specificity, PPV, NPV, accuracy, kappa.
    """
    tp = int(((df["qc_auto_valid"]) & (df["correct_bool"])).sum())
    fp = int(((df["qc_auto_valid"]) & (~df["correct_bool"])).sum())
    fn = int((~df["qc_auto_valid"] & (df["correct_bool"])).sum())
    tn = int((~df["qc_auto_valid"] & ~df["correct_bool"]).sum())

    n = tp + fp + fn + tn
    accuracy = (tp + tn) / n if n > 0 else np.nan
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else np.nan
    specificity = tn / (tn + fp) if (tn + fp) > 0 else np.nan
    ppv = tp / (tp + fp) if (tp + fp) > 0 else np.nan
    npv = tn / (tn + fn) if (tn + fn) > 0 else np.nan

    # Cohen's kappa
    pe = (
        ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
        if n > 0
        else 0
    )
    kappa = (accuracy - pe) / (1 - pe) if (1 - pe) > 0 else np.nan

    return {
        "label": label,
        "n": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "accuracy": accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "ppv": ppv,
        "npv": npv,
        "cohens_kappa": kappa,
    }


def _compute_breakdown(
    df: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """Compute detection counts by exposure, experiment, and their cross.

    Parameters
    ----------
    df : DataFrame
        Annotated wound-bearing images.

    Returns
    -------
    dict
        DataFrames for by_exposure, by_experiment, and cross-tab.
    """
    by_exposure = (
        df.groupby("exposure")["correct_bool"]
        .agg(["count", "sum"])
        .rename(columns={"count": "total", "sum": "correct"})
    )
    by_exposure["incorrect"] = by_exposure["total"] - by_exposure["correct"]
    by_exposure["accuracy"] = by_exposure["correct"] / by_exposure["total"]
    by_exposure = by_exposure.astype({"correct": int, "incorrect": int})

    by_experiment = (
        df.groupby("experiment")["correct_bool"]
        .agg(["count", "sum"])
        .rename(columns={"count": "total", "sum": "correct"})
    )
    by_experiment["incorrect"] = by_experiment["total"] - by_experiment["correct"]
    by_experiment["accuracy"] = by_experiment["correct"] / by_experiment["total"]
    by_experiment = by_experiment.astype({"correct": int, "incorrect": int})

    # Cross-tabulation: correct counts
    cross_correct = pd.crosstab(
        df["exposure"],
        df["experiment"],
        values=df["correct_bool"],
        aggfunc="sum",
        margins=True,
    ).astype(int)

    cross_total = pd.crosstab(
        df["exposure"],
        df["experiment"],
        margins=True,
    )

    cross_accuracy = cross_correct / cross_total

    return {
        "by_exposure": by_exposure,
        "by_experiment": by_experiment,
        "cross_correct": cross_correct,
        "cross_total": cross_total,
        "cross_accuracy": cross_accuracy,
    }


def _compute_pixel_summary(
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """Summarise pixel-level metrics for images with corrections.

    Parameters
    ----------
    df : DataFrame
        Annotated wound-bearing images.

    Returns
    -------
    dict
        Per-metric mean, std, min, max, and count.
    """
    metric_cols = ["dice", "iou", "precision", "recall", "f1", "accuracy", "hausdorff_95"]
    with_metrics = df.dropna(subset=["dice"])
    n = len(with_metrics)

    summary: Dict[str, Any] = {"n_with_metrics": n}
    for col in metric_cols:
        vals = with_metrics[col].dropna()
        if len(vals) > 0:
            summary[col] = {
                "mean": float(vals.mean()),
                "std": float(vals.std()),
                "min": float(vals.min()),
                "max": float(vals.max()),
                "n": int(len(vals)),
            }
        else:
            summary[col] = {"mean": np.nan, "std": np.nan, "min": np.nan, "max": np.nan, "n": 0}

    return summary


# ===================================================================
# Output
# ===================================================================

def _save_tables(
    results: Dict[str, Any],
    output_dir: Path,
) -> None:
    """Write analysis tables to CSV files.

    Parameters
    ----------
    results : dict
        Output from :func:`run_analysis`.
    output_dir : Path
        Destination directory.
    """
    # Exclusions summary
    exc = results["exclusions"]
    exc_rows = [
        ["Total images", exc["total_images"]],
        ["No-wound (excluded)", exc["no_wound_count"]],
        ["Unannotated", exc["unannotated_count"]],
        ["Valid (wound present)", exc["valid_count"]],
    ]
    for exp, count in sorted(exc["no_wound_by_exposure"].items()):
        exc_rows.append([f"  No-wound — {exp}", count])
    for exp, count in sorted(exc["no_wound_by_experiment"].items()):
        exc_rows.append([f"  No-wound — {exp}", count])
    pd.DataFrame(exc_rows, columns=["metric", "value"]).to_csv(
        output_dir / "exclusions.csv", index=False
    )

    # Detection accuracy
    det = results["detection"]
    det_rows = [
        ["Total wound-bearing", det["n_total"]],
        ["Correctly detected", det["n_correct"]],
        ["Incorrectly detected", det["n_incorrect"]],
        ["Detection accuracy", f"{det['accuracy']:.4f}"],
    ]
    pd.DataFrame(det_rows, columns=["metric", "value"]).to_csv(
        output_dir / "detection_accuracy.csv", index=False
    )

    # QC evaluation
    for key in ["qc_all", "qc_valid"]:
        qc = results[key]
        qc_rows = [
            ["Subset", qc["label"]],
            ["N", qc["n"]],
            ["TP (QC=valid, human=correct)", qc["tp"]],
            ["FP (QC=valid, human=incorrect)", qc["fp"]],
            ["FN (QC=invalid, human=correct)", qc["fn"]],
            ["TN (QC=invalid, human=incorrect)", qc["tn"]],
            ["Accuracy", f"{qc['accuracy']:.4f}"],
            ["Sensitivity", f"{qc['sensitivity']:.4f}"],
            ["Specificity", f"{qc['specificity']:.4f}"],
            ["PPV", f"{qc['ppv']:.4f}"],
            ["NPV", f"{qc['npv']:.4f}"],
            ["Cohen's kappa", f"{qc['cohens_kappa']:.4f}"],
        ]
        pd.DataFrame(qc_rows, columns=["metric", "value"]).to_csv(
            output_dir / f"qc_evaluation_{qc['label']}.csv", index=False
        )

    # Breakdown tables
    bd = results["breakdown"]
    bd["by_exposure"].to_csv(output_dir / "breakdown_by_exposure.csv")
    bd["by_experiment"].to_csv(output_dir / "breakdown_by_experiment.csv")
    bd["cross_total"].to_csv(output_dir / "breakdown_cross_total.csv")
    bd["cross_correct"].to_csv(output_dir / "breakdown_cross_correct.csv")
    bd["cross_accuracy"].to_csv(output_dir / "breakdown_cross_accuracy.csv")

    # Pixel metrics
    pm = results["pixel_metrics"]
    pm_rows = [["n_with_metrics", pm["n_with_metrics"]]]
    for col in ["dice", "iou", "precision", "recall", "f1", "accuracy", "hausdorff_95"]:
        m = pm[col]
        pm_rows.append([f"{col}_mean", f"{m['mean']:.4f}"])
        pm_rows.append([f"{col}_std", f"{m['std']:.4f}"])
        pm_rows.append([f"{col}_min", f"{m['min']:.4f}"])
        pm_rows.append([f"{col}_max", f"{m['max']:.4f}"])
    pd.DataFrame(pm_rows, columns=["metric", "value"]).to_csv(
        output_dir / "pixel_metrics.csv", index=False
    )


# ===================================================================
# Pretty-print for interactive use
# ===================================================================

def print_summary(results: Dict[str, Any]) -> None:
    """Print a human-readable summary of the analysis.

    Parameters
    ----------
    results : dict
        Output from :func:`run_analysis`.
    """
    exc = results["exclusions"]
    det = results["detection"]
    qc_all = results["qc_all"]
    qc_valid = results["qc_valid"]
    bd = results["breakdown"]
    pm = results["pixel_metrics"]

    print("=" * 70)
    print("VERIFICATION RESULTS ANALYSIS")
    print("=" * 70)

    print(f"\n{'--- Image Census ---':^70}")
    print(f"  Total images:              {exc['total_images']}")
    print(f"  No-wound (excluded):       {exc['no_wound_count']}")
    print(f"  Unannotated:               {exc['unannotated_count']}")
    print(f"  Valid (wound present):      {exc['valid_count']}")
    for exp, count in sorted(exc["no_wound_by_exposure"].items()):
        print(f"    No-wound in {exp:>15s}: {count}")

    print(f"\n{'--- Detection Accuracy (wound-bearing images) ---':^70}")
    print(f"  Total:      {det['n_total']}")
    print(f"  Correct:    {det['n_correct']}  ({det['accuracy']:.1%})")
    print(f"  Incorrect:  {det['n_incorrect']}")

    print(f"\n{'--- By Exposure ---':^70}")
    print(bd["by_exposure"].to_string())

    print(f"\n{'--- By Experiment ---':^70}")
    print(bd["by_experiment"].to_string())

    print(f"\n{'--- Cross-tab: Correct / Total ---':^70}")
    cross_str = bd["cross_correct"].astype(str) + " / " + bd["cross_total"].astype(str)
    print(cross_str.to_string())

    print(f"\n{'--- QC Evaluation (all images) ---':^70}")
    _print_qc(qc_all)

    print(f"\n{'--- QC Evaluation (wound-bearing only) ---':^70}")
    _print_qc(qc_valid)

    if pm["n_with_metrics"] > 0:
        print(f"\n{'--- Pixel-Level Metrics (n=' + str(pm['n_with_metrics']) + ') ---':^70}")
        for col in ["dice", "iou", "precision", "recall", "f1", "accuracy", "hausdorff_95"]:
            m = pm[col]
            print(f"  {col:<15s}  {m['mean']:.4f} +/- {m['std']:.4f}  "
                  f"[{m['min']:.4f}, {m['max']:.4f}]")
    else:
        print("\n  No pixel-level metrics available (no polygon/edge corrections).")

    print("\n" + "=" * 70)


def _print_qc(qc: Dict[str, Any]) -> None:
    """Print QC evaluation metrics.

    Parameters
    ----------
    qc : dict
        Output from :func:`_compute_qc_metrics`.
    """
    print(f"  N = {qc['n']}")
    print(f"  TP={qc['tp']}  FP={qc['fp']}  FN={qc['fn']}  TN={qc['tn']}")
    print(f"  Sensitivity:    {qc['sensitivity']:.4f}")
    print(f"  Specificity:    {qc['specificity']:.4f}")
    print(f"  PPV:            {qc['ppv']:.4f}")
    print(f"  NPV:            {qc['npv']:.4f}")
    print(f"  Accuracy:       {qc['accuracy']:.4f}")
    print(f"  Cohen's kappa:  {qc['cohens_kappa']:.4f}")
