"""
woundtrack.constants
====================

Shared thresholds and default values used across the woundtrack library.
All constants are grouped by their usage domain.
"""

from typing import Final

__all__ = [
    # QC thresholds
    "DEFAULT_GAUSSIAN_SIGMA_Y",
    "DEFAULT_PEAK_PROMINENCE",
    "DEFAULT_MAX_CENTER_OFFSET_FRAC",
    "DEFAULT_MAX_X_SKEW",
    "DEFAULT_FLATNESS_THRESHOLD",
    # Edge/closure thresholds
    "DEFAULT_MIN_CLOSING_FRAC_COLUMNS",
    # Metrics defaults
    "DEFAULT_T_TARGET",
    # Dataset defaults
    "DEFAULT_TIME",
]

# =============================================================================
# QC thresholds (verify_wound_by_distribution)
# =============================================================================

DEFAULT_GAUSSIAN_SIGMA_Y: Final[float] = 15.0
"""Sigma for Gaussian smoothing on Y profile during wound verification."""

DEFAULT_PEAK_PROMINENCE: Final[float] = 0.15
"""Minimum prominence for peak detection in Y profile."""

DEFAULT_MAX_CENTER_OFFSET_FRAC: Final[float] = 0.15
"""Maximum allowed offset of peak from wound center as fraction of height."""

DEFAULT_MAX_X_SKEW: Final[float] = 0.8
"""Maximum allowed skewness of X profile for valid wound."""

DEFAULT_FLATNESS_THRESHOLD: Final[float] = 0.15
"""Maximum standard deviation of central X band for flatness check."""

# =============================================================================
# Edge/closure thresholds
# =============================================================================

DEFAULT_MIN_CLOSING_FRAC_COLUMNS: Final[float] = 0.6
"""Minimum fraction of columns that must show closing motion."""

# =============================================================================
# Metrics defaults
# =============================================================================

DEFAULT_T_TARGET: Final[float] = 12.0
"""Default target time for speed calculations."""

# =============================================================================
# Dataset defaults
# =============================================================================

DEFAULT_TIME: Final[int] = 0
"""Default timepoint for dataset extraction (baseline)."""
