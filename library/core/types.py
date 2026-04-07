"""
Shared Type Definitions for Wound Detection
============================================

Canonical dataclasses consumed by both the *standard* (variance-based)
and *Quantification* (monotonic-constrained) wound detection pipelines.

Keeping these definitions in a single module eliminates cross-library
imports between ``wound_standard`` and ``wound_quantification``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Detector configuration
# ---------------------------------------------------------------------------

@dataclass
class WoundDetectorConfig:
    """Configuration for the multi-stage wound detection pipeline.

    Each group of parameters controls one pipeline stage.  Sensible
    defaults are provided for 10x-magnification scratch-wound images
    of approximately 1024 x 1280 pixels.

    Attributes
    ----------
    variance_window : int
        Side length (pixels) of the square uniform filter used to
        compute the local-variance texture map.  Larger values smooth
        out cell-scale detail.  Stage 1.
    variance_sigma : float
        Gaussian post-smoothing sigma applied to the variance map
        before downstream processing.  Stage 1.
    y_profile_sigma : float
        Gaussian sigma for 1-D smoothing of the row-wise mean variance
        profile used to locate the wound Y-band.  Stage 2.
    y_band_percentile : float
        Percentile threshold (0-100) on the smoothed Y-profile; rows
        below this value are considered candidate wound rows.  Stage 2.
    y_margin : float
        Fractional expansion of the detected Y-band in both directions.
        ``0.15`` means 15 % of the band height is added above and below.
        Stage 2.
    edge_threshold_percentile : float
        Percentile of column-wise variance within the Y-band used to
        distinguish wound (below) from cell (above) pixels.  Stage 3.
    ransac_poly_degree : int
        Degree of the polynomial fitted during RANSAC edge smoothing.
        Stage 4.
    ransac_max_deviation : float
        Maximum pixel deviation from the polynomial fit before a point
        is classified as an outlier in RANSAC.  Stage 4.
    ransac_iterations : int
        Number of fit-reject-refit cycles in RANSAC.  Stage 4.
    smoothing_window : int
        Window length for the Savitzky-Golay final edge smoother.
        Must be odd.  Stage 5.
    smoothing_polyorder : int
        Polynomial order for the Savitzky-Golay filter.  Stage 5.
    min_width_coverage : float
        Minimum fraction of image columns that must contain wound pixels
        for the detection to be considered valid.  Stage 6.
    min_aspect_ratio : float
        Minimum width / mean-thickness ratio.  Stage 6.
    max_thickness_cv : float
        Maximum coefficient of variation of wound thickness across
        columns.  Stage 6.
    y_center_range : Tuple[float, float]
        Acceptable fractional range ``(lo, hi)`` for the wound center
        along the Y axis.  Stage 6.
    fallback_enabled : bool
        If ``True``, a region-growing fallback is attempted when the
        primary pipeline fails validation.
    closure_threshold : float
        Fraction of t=0 wound area below which the wound is considered
        fully closed.  Once triggered, edges are frozen at their current
        positions for all subsequent frames.  Applies to both Kalman and
        hard constraint paths.  Default ``0.01`` (1 %).
    max_edge_jump : float
        Maximum pixel displacement allowed per edge per frame in the
        hard monotonic constraint.  Detected edges that deviate more
        than this from the previous frame are clamped before the
        ``max``/``min`` constraint is applied.  Prevents spatially
        implausible detections from being accepted.  Default ``50.0``.
    """

    # Stage 1: Local variance
    variance_window: int = 15
    variance_sigma: float = 2.0

    # Stage 2: Y-profile band detection
    y_profile_sigma: float = 10.0
    y_band_percentile: float = 35.0
    y_margin: float = 0.15

    # Stage 3: Edge detection
    edge_threshold_percentile: float = 40.0

    # Stage 4: RANSAC smoothing
    ransac_poly_degree: int = 2
    ransac_max_deviation: float = 25.0
    ransac_iterations: int = 3

    # Stage 5: Smoothing
    smoothing_window: int = 51
    smoothing_polyorder: int = 3

    # Stage 6: Validation
    min_width_coverage: float = 0.75
    min_aspect_ratio: float = 1.5
    max_thickness_cv: float = 0.6
    y_center_range: Tuple[float, float] = (0.15, 0.85)

    # Fallback
    fallback_enabled: bool = True

    # Wound closure detection
    closure_threshold: float = 0.01  # Fraction of t=0 area; below this wound is frozen
    max_edge_jump: float = 50.0      # Max px an edge can jump between frames (hard constraint)

    # Kalman filter constraint (replaces hard monotonic constraint when enabled)
    use_kalman: bool = True
    kalman_Q: Optional[float] = None
    kalman_R_base: Optional[float] = None
    kalman_fallback_multiplier: float = 3.0
    kalman_spatial_sigma: float = 5.0


# ---------------------------------------------------------------------------
# Single-frame detection result
# ---------------------------------------------------------------------------

@dataclass
class WoundResult:
    """Output of a single-frame wound detection.

    Attributes
    ----------
    mask : np.ndarray
        Binary wound mask, shape ``(H, W)``, dtype ``uint8``.
        ``1`` = wound pixel, ``0`` = background / cell.
    upper_edge : np.ndarray
        Per-column Y coordinate of the upper wound boundary,
        shape ``(W,)``, dtype ``float64``.
    lower_edge : np.ndarray
        Per-column Y coordinate of the lower wound boundary,
        shape ``(W,)``, dtype ``float64``.
    y_center : int
        Estimated Y coordinate of the wound centre.
    y_band : Tuple[int, int]
        ``(y_min, y_max)`` bounding the detected wound band.
    qc : Dict
        Quality-control metrics produced by validation.  Keys include
        ``"valid"`` (bool), ``"width_coverage"`` (float),
        ``"aspect_ratio"`` (float), ``"y_center_frac"`` (float),
        ``"thickness_cv"`` (float), and ``"failure_reason"`` (str | None).
    method : str
        ``"primary"`` if the main pipeline succeeded,
        ``"fallback"`` if the region-growing alternative was used.
    """

    mask: np.ndarray
    upper_edge: np.ndarray
    lower_edge: np.ndarray
    y_center: int
    y_band: Tuple[int, int]
    qc: Dict
    method: str = "primary"

    # Optional fields for Kalman R estimation (populated when use_kalman=True)
    variance_map: Optional[np.ndarray] = field(default=None, repr=False)
    edge_residuals_upper: Optional[np.ndarray] = field(default=None, repr=False)
    edge_residuals_lower: Optional[np.ndarray] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Time-series segmentation result (used by QuantificationSegmenter)
# ---------------------------------------------------------------------------

@dataclass
class SegmentationResult:
    """Output of a single time-point segmentation by :class:`QuantificationSegmenter`.

    Extends the information in :class:`WoundResult` with temporal context
    and the monotonic-constraint flag.

    Attributes
    ----------
    t : int
        Zero-based time index within the trajectory.
    file_name : Optional[Path]
        Source image path, if available.
    img_raw : np.ndarray
        Grayscale input image, shape ``(H, W)``, dtype ``uint8``.
    mask : np.ndarray
        Binary wound mask after monotonic constraint, shape ``(H, W)``,
        dtype ``uint8``.
    upper_edge : np.ndarray
        Per-column upper boundary after constraint, shape ``(W,)``.
    lower_edge : np.ndarray
        Per-column lower boundary after constraint, shape ``(W,)``.
    area : int
        Total wound area in pixels (``mask.sum()``).
    qc : Dict
        Quality-control metrics from the underlying detector.
    method : str
        Detection method that produced the raw (pre-constraint) result.
    constrained : bool
        ``True`` if the monotonic constraint was applied (all frames
        after ``t = 0``).
    """

    t: int
    file_name: Optional[Path]
    img_raw: np.ndarray
    mask: np.ndarray
    upper_edge: np.ndarray
    lower_edge: np.ndarray
    area: int
    qc: Dict
    method: str
    constrained: bool
