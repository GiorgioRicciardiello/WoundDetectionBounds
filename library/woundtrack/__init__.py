"""
woundtrack
==========

A modular Python library for time-resolved wound-healing experiments
and preparing data for training ML segmentation models.

Design Goals
------------
- Keep your existing `trajectories: Dict[str, Dict]` structure as the raw store
- Provide a thin, typed layer (dataclasses) + utility functions for QC/metrics
- Support optional debug visualization for edge displacement
- Provide clean ML dataset interface (WoundSegmentationDataset)
- Exports for (image, mask) pairs for training segmentation models

Core Concepts
-------------
- A *trajectory* is one experiment (one well/condition), identified by a string key
- Each trajectory contains a list of *results* over time (t = 0, 1, ...)
- Each result includes at minimum a 2D `mask` (binary wound mask) and often `img_raw`

Typical Workflow
----------------
1) Baseline QC (t=0) -> decide which trajectories to keep
2) Compute closure speeds using masks at t=0 and nearest available time to target T
3) Optional debugging plots showing edge displacement
4) Export (img_raw, mask) pairs for ML training via WoundSegmentationDataset

Dependencies
------------
Required:
- numpy

Optional:
- scipy (for verify_wound_by_distribution)
- pandas (for tables)
- matplotlib (for debug plots)
- tqdm (for progress bars)

Note
----
This library assumes wounds are horizontal band-like regions spanning most of the width.
"""

# Core types
from .types import Trajectory, TrajectoryResult

# QC
from .qc import filter_trajectories_by_t0_wound_distribution

# Metrics
from .metrics import distance_calculator

# ML Dataset
from .dataset import WoundSegmentationDataset

# I/O
from .io import export_pairs_t0

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Types
    "Trajectory",
    "TrajectoryResult",
    # QC
    "filter_trajectories_by_t0_wound_distribution",
    # Metrics
    "distance_calculator",
    # ML Dataset (CRITICAL)
    "WoundSegmentationDataset",
    # I/O
    "export_pairs_t0",
]
