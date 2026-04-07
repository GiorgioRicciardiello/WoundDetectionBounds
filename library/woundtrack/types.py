"""
woundtrack.types
================

Typed dataclasses for wound-healing trajectory data.
No computation, no plotting, no scipy/torch dependencies.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import numpy as np

__all__ = [
    "TimeT",
    "TrajectoriesDict",
    "TrajectoryResult",
    "Trajectory",
]

# Type aliases
TimeT = Union[int, float]
"""Time type: can be int or float."""

TrajectoriesDict = Dict[str, Dict[str, Any]]
"""Raw trajectories dictionary structure."""


@dataclass(frozen=True)

class TrajectoryResult:
    """
    One timepoint in a wound-healing trajectory.

    Attributes
    ----------
    t:
        Time index (e.g., hours). Typically includes t=0 baseline.
    img_raw:
        Raw grayscale image (H, W). Optional but recommended for debugging/export.
    mask:
        Binary wound mask (H, W). True/1 indicates wound region.
    area:
        Optional cached wound area (pixels). If missing, can be computed from mask.
    y_upper, y_lower:
        Optional cached wound boundaries per x column. If missing, can be derived.
    overlay:
        Optional visualization image.
    file_name:
        Original filename for this timepoint.
    """
    t: TimeT
    img_raw: Optional[np.ndarray] = None
    mask: Optional[np.ndarray] = None
    area: Optional[Union[int, float]] = None
    y_upper: Optional[np.ndarray] = None
    y_lower: Optional[np.ndarray] = None
    overlay: Optional[np.ndarray] = None
    file_name: Optional[str] = None

@dataclass(frozen=True)
class Trajectory:
    """
    One experimental trajectory with time series results.

    Attributes
    ----------
    results:
        Ordered list of timepoints (TrajectoryResult).
    sample_out_dir, exposure, experiment, sample_name:
        Optional metadata.
    """
    results: List[TrajectoryResult]
    sample_out_dir: Optional[str] = None
    exposure: Optional[Any] = None
    experiment: Optional[Any] = None
    sample_name: Optional[str] = None

    def available_times(self) -> List[TimeT]:
        """Return sorted list of available times."""
        return sorted([r.t for r in self.results if r.t is not None])

    def get_by_time(self, t: TimeT) -> Optional[TrajectoryResult]:
        """Return the result matching exact time t, or None."""
        return next((r for r in self.results if r.t == t), None)

    def get_t0(self) -> Optional[TrajectoryResult]:
        """Return the baseline result (t=0), or None."""
        return self.get_by_time(0)
