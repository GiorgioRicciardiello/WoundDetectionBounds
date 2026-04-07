"""
core - Shared types and interfaces for wound detection models.

Provides model-agnostic dataclasses used by both the standard
(variance-based) and Quantification (monotonic-constrained) wound detectors.
"""

from .types import WoundDetectorConfig, WoundResult, SegmentationResult

__all__ = ["WoundDetectorConfig", "WoundResult", "SegmentationResult"]
