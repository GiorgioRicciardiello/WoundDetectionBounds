"""
Results Export
==============

Build an Excel workbook with two sheets from the verification session:

Sheet 1 — **Per-Image Annotations**
    One row per trajectory with the human verdict, optional polygon-based
    metrics, automatic QC flag, and free-text notes.

Sheet 2 — **Aggregate Summary**
    Overall counts, mean/std of each metric across polygon-annotated
    images, QC-vs-human agreement, and Cohen's kappa.

The per-image sheet is designed to be compatible with the existing
``load_annotations()`` function in ``library/filtering/manual_check.py``
so downstream filtering pipelines continue to work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from library.verification.metrics import compute_aggregate_metrics


def export_results(
    annotations: Dict[str, Dict[str, Any]],
    records_metadata: List[Dict[str, Any]],
    records_qc: Dict[str, bool],
    output_path: Path,
) -> Path:
    """Write verification results to a two-sheet Excel workbook.

    Parameters
    ----------
    annotations : dict
        ``{trajectory_key: {correct, polygons, metrics, notes}}``.
    records_metadata : list of dict
        Metadata for each trajectory (exposure, experiment, sample_name,
        original_filename).  Used to enrich the per-image table.
    records_qc : dict
        ``{trajectory_key: qc_valid (bool)}``.
    output_path : Path
        Destination ``.xlsx`` file path.

    Returns
    -------
    Path
        The written file path (same as *output_path*).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- Sheet 1: per-image annotations ----
    meta_lookup = {r["trajectory_key"]: r for r in records_metadata}
    rows: List[Dict[str, Any]] = []

    for key, meta in meta_lookup.items():
        ann = annotations.get(key, {})
        metrics = ann.get("metrics", {})

        rows.append({
            "trajectory_key": key,
            "original_filename": meta.get("original_filename", ""),
            "exposure": meta.get("exposure", ""),
            "experiment": meta.get("experiment", ""),
            "sample_name": meta.get("sample_name", ""),
            "qc_auto_valid": records_qc.get(key),
            "correct": ann.get("correct"),
            "polygon_drawn": bool(ann.get("polygons")),
            "dice": metrics.get("dice"),
            "iou": metrics.get("iou"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1": metrics.get("f1"),
            "accuracy": metrics.get("accuracy"),
            "hausdorff_95": metrics.get("hausdorff_95"),
            "notes": ann.get("notes", ""),
            # Backward-compatible column for load_annotations()
            "keep": ann.get("correct"),
        })

    df_per_image = pd.DataFrame(rows)
    df_per_image.sort_values("trajectory_key", inplace=True)

    # ---- Sheet 2: aggregate summary ----
    agg = compute_aggregate_metrics(annotations, records_qc)
    summary_rows = _flatten_aggregate(agg)
    df_summary = pd.DataFrame(summary_rows, columns=["metric", "value"])

    # ---- Write workbook ----
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_per_image.to_excel(writer, sheet_name="Per-Image Annotations", index=False)
        df_summary.to_excel(writer, sheet_name="Aggregate Summary", index=False)

    return output_path


def _flatten_aggregate(agg: Dict[str, Any]) -> List[List[Any]]:
    """Convert the aggregate metrics dict into a list of [metric, value] rows.

    Parameters
    ----------
    agg : dict
        Output of :func:`compute_aggregate_metrics`.

    Returns
    -------
    list of [str, Any]
        Rows suitable for a two-column DataFrame.
    """
    rows = [
        ["total_images", agg.get("total_images")],
        ["annotated_count", agg.get("annotated_count")],
        ["correct_count", agg.get("correct_count")],
        ["incorrect_count", agg.get("incorrect_count")],
        ["polygon_count", agg.get("polygon_count")],
        ["", ""],
        ["--- Polygon Metrics (mean ± std) ---", ""],
        ["mean_dice", agg.get("mean_dice")],
        ["std_dice", agg.get("std_dice")],
        ["mean_iou", agg.get("mean_iou")],
        ["std_iou", agg.get("std_iou")],
        ["mean_precision", agg.get("mean_precision")],
        ["std_precision", agg.get("std_precision")],
        ["mean_recall", agg.get("mean_recall")],
        ["std_recall", agg.get("std_recall")],
        ["mean_f1", agg.get("mean_f1")],
        ["std_f1", agg.get("std_f1")],
        ["mean_accuracy", agg.get("mean_accuracy")],
        ["std_accuracy", agg.get("std_accuracy")],
        ["mean_hausdorff_95", agg.get("mean_hausdorff_95")],
        ["std_hausdorff_95", agg.get("std_hausdorff_95")],
        ["", ""],
        ["--- QC vs Human Agreement ---", ""],
        ["qc_agreement_rate", agg.get("qc_agreement")],
        ["cohens_kappa", agg.get("cohens_kappa")],
    ]

    # Confusion matrix
    cm = agg.get("confusion_matrix", {})
    rows.extend([
        ["confusion_tp (QC=valid, human=correct)", cm.get("tp")],
        ["confusion_fp (QC=valid, human=incorrect)", cm.get("fp")],
        ["confusion_fn (QC=invalid, human=correct)", cm.get("fn")],
        ["confusion_tn (QC=invalid, human=incorrect)", cm.get("tn")],
    ])

    return rows
