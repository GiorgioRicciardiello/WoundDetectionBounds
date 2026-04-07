"""
Segmentation Quality Metrics
=============================

Pure-numpy implementations of pixel-level and aggregate metrics for
comparing a model-predicted wound mask against a manually drawn
ground-truth mask.

All per-image functions expect two binary masks of identical shape with
values in {0, 1}.  Division-by-zero cases are handled explicitly
(returning 0.0) to avoid NaN propagation.

Metrics
-------
Per-image:
    Dice coefficient, IoU (Jaccard), pixel accuracy, precision, recall,
    F1 score, 95th-percentile Hausdorff distance.

Aggregate:
    Counts (correct / incorrect / polygon-drawn), mean and std of all
    per-image metrics, QC-vs-human agreement, Cohen's kappa.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from scipy.ndimage import distance_transform_edt


# ===================================================================
# Per-image metrics
# ===================================================================

def compute_pixel_metrics(
    model_mask: np.ndarray,
    manual_mask: np.ndarray,
) -> Dict[str, Any]:
    """Compute pixel-level segmentation metrics.

    Parameters
    ----------
    model_mask : np.ndarray
        Binary wound mask from the model, shape (H, W), values {0, 1}.
    manual_mask : np.ndarray
        Binary ground-truth mask from user polygon, same shape.

    Returns
    -------
    dict
        Keys: tp, fp, fn, tn (int), dice, iou, precision, recall, f1,
        accuracy, hausdorff_95 (float).

    Raises
    ------
    ValueError
        If masks have different shapes.

    Notes
    -----
    The 95th-percentile Hausdorff distance is more robust to outlier
    boundary pixels than the standard (max) Hausdorff.  It is computed
    via Euclidean distance transforms of each mask's complement.
    """
    if model_mask.shape != manual_mask.shape:
        raise ValueError(
            f"Shape mismatch: model {model_mask.shape} vs manual {manual_mask.shape}"
        )

    # Binarise to bool for set operations
    m = model_mask.astype(bool)
    g = manual_mask.astype(bool)

    tp = int(np.sum(m & g))
    fp = int(np.sum(m & ~g))
    fn = int(np.sum(~m & g))
    tn = int(np.sum(~m & ~g))

    total = tp + fp + fn + tn

    # Dice = 2·|A∩B| / (|A| + |B|)
    dice_denom = 2 * tp + fp + fn
    dice = (2.0 * tp / dice_denom) if dice_denom > 0 else 0.0

    # IoU = |A∩B| / |A∪B|
    iou_denom = tp + fp + fn
    iou = (float(tp) / iou_denom) if iou_denom > 0 else 0.0

    # Precision = TP / (TP + FP)
    prec_denom = tp + fp
    precision = (float(tp) / prec_denom) if prec_denom > 0 else 0.0

    # Recall = TP / (TP + FN)
    rec_denom = tp + fn
    recall = (float(tp) / rec_denom) if rec_denom > 0 else 0.0

    # F1 = harmonic mean of precision and recall
    f1_denom = precision + recall
    f1 = (2.0 * precision * recall / f1_denom) if f1_denom > 0 else 0.0

    # Pixel accuracy
    accuracy = (float(tp + tn) / total) if total > 0 else 0.0

    # 95th-percentile Hausdorff distance
    hausdorff_95 = _hausdorff_percentile(m, g, percentile=95)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "dice": round(dice, 6),
        "iou": round(iou, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "accuracy": round(accuracy, 6),
        "hausdorff_95": round(hausdorff_95, 4),
    }


def _hausdorff_percentile(
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    percentile: float = 95,
) -> float:
    """Compute percentile-based Hausdorff distance between two binary masks.

    Uses the Euclidean distance transform approach:
    d(A→B) = distances from each foreground pixel of A to the nearest
    foreground pixel of B.  The percentile Hausdorff is
    max(percentile(d(A→B)), percentile(d(B→A))).

    Parameters
    ----------
    mask_a, mask_b : np.ndarray
        Boolean masks of identical shape.
    percentile : float
        Percentile to use (default 95).

    Returns
    -------
    float
        Distance in pixels.  Returns 0.0 if either mask is empty.
    """
    if not np.any(mask_a) or not np.any(mask_b):
        return 0.0

    # Distance from every pixel to nearest foreground pixel of B
    dt_b = distance_transform_edt(~mask_b)
    # Distances at foreground pixels of A
    d_a_to_b = dt_b[mask_a]

    dt_a = distance_transform_edt(~mask_a)
    d_b_to_a = dt_a[mask_b]

    h_ab = float(np.percentile(d_a_to_b, percentile))
    h_ba = float(np.percentile(d_b_to_a, percentile))

    return max(h_ab, h_ba)


# ===================================================================
# Aggregate metrics
# ===================================================================

def compute_aggregate_metrics(
    annotations: Dict[str, Dict[str, Any]],
    records_qc: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Compute summary statistics across all annotated images.

    Parameters
    ----------
    annotations : dict
        Mapping ``{trajectory_key: {correct, polygons, metrics, notes}}``.
    records_qc : dict or None
        Mapping ``{trajectory_key: qc_valid (bool)}`` for computing
        agreement between automatic QC and human verdict.

    Returns
    -------
    dict
        Aggregate statistics including counts, mean/std of each metric,
        QC agreement rate, and Cohen's kappa.

    Notes
    -----
    Cohen's kappa measures inter-rater reliability correcting for chance:

    .. math::
        \\kappa = \\frac{p_o - p_e}{1 - p_e}

    where :math:`p_o` is observed agreement and :math:`p_e` is expected
    agreement by chance.  A value of 1 means perfect agreement, 0 means
    no better than random, and negative means worse than random.
    """
    if records_qc is None:
        records_qc = {}

    total_images = len(annotations)
    annotated = {k: v for k, v in annotations.items() if v.get("correct") is not None}
    annotated_count = len(annotated)
    correct_count = sum(1 for v in annotated.values() if v["correct"] is True)
    incorrect_count = sum(1 for v in annotated.values() if v["correct"] is False)

    # Polygon-based metrics
    polygon_annotations = {
        k: v for k, v in annotated.items()
        if v.get("metrics") and v["metrics"].get("dice") is not None
    }
    polygon_count = len(polygon_annotations)

    metric_keys = ["dice", "iou", "precision", "recall", "f1", "accuracy", "hausdorff_95"]
    metric_stats: Dict[str, Any] = {}

    for mk in metric_keys:
        values = [
            v["metrics"][mk]
            for v in polygon_annotations.values()
            if mk in v.get("metrics", {})
        ]
        if values:
            arr = np.array(values, dtype=np.float64)
            metric_stats[f"mean_{mk}"] = round(float(np.mean(arr)), 4)
            metric_stats[f"std_{mk}"] = round(float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0, 4)
        else:
            metric_stats[f"mean_{mk}"] = None
            metric_stats[f"std_{mk}"] = None

    # QC vs human agreement
    qc_agreement, confusion, kappa = _compute_qc_agreement(annotated, records_qc)

    return {
        "total_images": total_images,
        "annotated_count": annotated_count,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "polygon_count": polygon_count,
        **metric_stats,
        "qc_agreement": qc_agreement,
        "confusion_matrix": confusion,
        "cohens_kappa": kappa,
    }


def _compute_qc_agreement(
    annotated: Dict[str, Dict[str, Any]],
    records_qc: Dict[str, bool],
) -> tuple:
    """Compare automatic QC verdicts with human annotations.

    Parameters
    ----------
    annotated : dict
        Human annotations with ``correct`` bool.
    records_qc : dict
        Automatic QC ``{key: valid_bool}``.

    Returns
    -------
    agreement : float or None
        Fraction of cases where QC and human agree.
    confusion : dict
        ``{tp, fp, fn, tn}`` treating QC as "prediction" and human as "truth".
    kappa : float or None
        Cohen's kappa statistic.
    """
    if not records_qc:
        return None, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}, None

    tp = fp = fn = tn = 0
    for key, ann in annotated.items():
        if key not in records_qc:
            continue
        human = ann["correct"]
        qc = records_qc[key]
        if qc and human:
            tp += 1
        elif qc and not human:
            fp += 1
        elif not qc and human:
            fn += 1
        else:
            tn += 1

    total = tp + fp + fn + tn
    if total == 0:
        return None, {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, None

    p_o = (tp + tn) / total
    p_qc_pos = (tp + fp) / total
    p_human_pos = (tp + fn) / total
    p_e = p_qc_pos * p_human_pos + (1 - p_qc_pos) * (1 - p_human_pos)

    kappa = ((p_o - p_e) / (1 - p_e)) if (1 - p_e) > 0 else 0.0

    return (
        round(p_o, 4),
        {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        round(kappa, 4),
    )
