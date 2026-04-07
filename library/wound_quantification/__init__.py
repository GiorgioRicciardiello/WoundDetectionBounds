"""
Quantification Wound Detection Library
=======================================

Modular wound detection and tracking for scratch wound healing assays.

Uses robust variance-based detection with monotonic closure constraint.
The constraint ensures ``wound_area(t+1) <= wound_area(t)`` at the
per-column edge level.

Modules
-------
segmenter
    :class:`QuantificationSegmenter` -- stateful per-frame segmentation.
trajectory
    :func:`process_trajectory` -- batch time-series processing.
"""

from library.core.types import WoundDetectorConfig, WoundResult, SegmentationResult
from library.wound_quantification.segmenter import QuantificationSegmenter
from library.wound_quantification.trajectory import process_trajectory
from library.wound_quantification.kalman_constraint import (
    KalmanEdgeFilter,
    estimate_Q_from_trajectories,
)

__all__ = [
    "WoundDetectorConfig",
    "WoundResult",
    "SegmentationResult",
    "QuantificationSegmenter",
    "process_trajectory",
    "KalmanEdgeFilter",
    "estimate_Q_from_trajectories",
]
