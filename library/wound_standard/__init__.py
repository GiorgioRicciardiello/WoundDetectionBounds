"""
wound_standard - Standard multi-stage variance-based wound detection.

Provides the classic wound detection pipeline using local variance analysis,
RANSAC edge smoothing, and geometric validation for scratch wound healing assays.

Modules
-------
detector
    Multi-stage wound detector (``WoundDetector``).
preprocessor
    Gradient-based image preprocessing pipeline.
segmenter
    Stateful wound tracker with temporal constraints (``WoundSegmenter``).
sequence
    Batch time-series processing.
reader
    Filename parsing and image grouping utilities.
utils
    Profile computation and quality-control helpers.
"""

from library.core.types import WoundDetectorConfig, WoundResult
from .detector import WoundDetector, detect_wound
from .segmenter import WoundSegmenter

__all__ = [
    "WoundDetectorConfig",
    "WoundResult",
    "WoundDetector",
    "detect_wound",
    "WoundSegmenter",
]
