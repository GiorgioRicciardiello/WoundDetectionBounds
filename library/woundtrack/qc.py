"""
woundtrack.qc
=============

Baseline quality control (t=0 only).
Verifies wound mask validity using X/Y projections.

No plotting, no ML dependencies.
"""

from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np

from .types import TrajectoriesDict

__all__ = [
    "verify_wound_by_distribution",
    "filter_trajectories_by_t0_wound_distribution",
]

def verify_wound_by_distribution(
    wound_mask: np.ndarray,
    gaussian_sigma_y: float = 15,
    peak_prominence: float = 0.15,
    max_center_offset_frac: float = 0.15,
    max_x_skew: float = 0.8,
) -> Dict[str, Any]:
    """
    Verify wound mask quality using X/Y projections.

    This function is identical in behavior to your provided version:
    - Y-axis: Gaussian-smoothed row-sum profile should have exactly one prominent peak,
      and the peak should be near the wound center.
    - X-axis: column-sum profile should be roughly rectangular (low skew, flat mid band).

    Parameters
    ----------
    wound_mask:
        2D binary/float mask (H, W). Nonzero treated as wound.
    gaussian_sigma_y:
        Sigma for gaussian smoothing on y profile.
    peak_prominence:
        Peak prominence threshold for find_peaks.
    max_center_offset_frac:
        Peak center offset tolerance (fraction of height).
    max_x_skew:
        Max allowed skewness of x profile.

    Returns
    -------
    dict
        Includes 'valid' key plus diagnostics and profiles.

    Notes
    -----
    Requires:
    - scipy.ndimage.gaussian_filter1d
    - scipy.signal.find_peaks
    - scipy.stats.skew
    """
    from scipy.ndimage import gaussian_filter1d
    from scipy.signal import find_peaks
    from scipy.stats import skew

    H, W = wound_mask.shape
    mask = wound_mask.astype(bool)

    # Y profile
    y_profile = mask.sum(axis=1).astype(float)
    y_profile /= y_profile.max() + 1e-6
    y_profile_s = gaussian_filter1d(y_profile, gaussian_sigma_y)

    peaks, props = find_peaks(
        y_profile_s,
        prominence=peak_prominence,
        distance=H // 6,
    )

    wound_center = np.average(np.where(mask)[0]) if mask.any() else np.nan
    peak_centers = peaks
    center_offsets = (
        np.abs(peak_centers - wound_center) / H
        if not np.isnan(wound_center)
        else np.array([np.inf])
    )

    y_ok = (len(peaks) == 1) and (center_offsets[0] < max_center_offset_frac)

    # X profile
    x_profile = mask.sum(axis=0).astype(float)
    x_profile /= x_profile.max() + 1e-6

    x_skew = skew(x_profile)

    central_band = x_profile[int(0.25 * W): int(0.75 * W)]
    flatness = np.std(central_band)

    x_ok = (abs(x_skew) < max_x_skew) and (flatness < 0.15)

    is_valid = y_ok and x_ok

    return {
        "valid": bool(is_valid),

        "y_num_peaks": int(len(peaks)),
        "y_peak_positions": peak_centers.tolist(),
        "y_center_offset_frac": float(center_offsets[0]) if len(center_offsets) > 0 else None,

        "x_skewness": float(x_skew),
        "x_flatness": float(flatness),

        "y_profile": y_profile_s,
        "x_profile": x_profile,
    }



def filter_trajectories_by_t0_wound_distribution(
    trajectories: TrajectoriesDict,
    verify_kwargs: Optional[Dict[str, Any]] = None,
    use_tqdm: bool = True,
) -> Tuple[TrajectoriesDict, Dict[str, bool]]:
    """
    Filter trajectories using ONLY the t=0 mask and verify_wound_by_distribution.

    Parameters
    ----------
    trajectories:
        Raw trajectories dict.
    verify_kwargs:
        Extra kwargs for verify_wound_by_distribution (thresholds, sigma, etc).
    use_tqdm:
        If True, show a tqdm progress bar (if tqdm installed).

    Returns
    -------
    filtered_trajectories:
        Subset of trajectories that pass QC at t=0.
    keep_table:
        Dict mapping trajectory_key -> bool (True=keep, False=remove).
    """
    if verify_kwargs is None:
        verify_kwargs = {}

    iterator: Iterable[Tuple[str, Dict[str, Any]]] = trajectories.items()
    if use_tqdm:
        try:
            from tqdm import tqdm
            iterator = tqdm(iterator, total=len(trajectories), desc="QC trajectories (t=0)")
        except Exception:
            pass

    filtered: TrajectoriesDict = {}
    keep_table: Dict[str, bool] = {}

    for traj_key, traj_data in iterator:
        results = traj_data.get("results", [])
        t0_entry = next((r for r in results if r.get("t", None) == 0), None)

        if t0_entry is None or "mask" not in t0_entry:
            keep_table[traj_key] = False
            continue

        qc = verify_wound_by_distribution(t0_entry["mask"], **verify_kwargs)
        keep = bool(qc["valid"])
        keep_table[traj_key] = keep
        if keep:
            filtered[traj_key] = traj_data

    return filtered, keep_table
