"""
Utility Functions for Wound Analysis
=====================================

Profile computation, envelope detection, and quality-control
verification helpers shared across standard-model modules.
"""

from typing import Dict, Tuple

import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.stats import skew


def compute_xy_profiles(
    wound_mask: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute normalized row-wise and column-wise wound projections.

    Parameters
    ----------
    wound_mask : np.ndarray
        Binary wound mask, shape ``(H, W)``.

    Returns
    -------
    y_profile : np.ndarray
        Row-wise wound fraction, shape ``(H,)``, range [0, 1].
    x_profile : np.ndarray
        Column-wise wound fraction, shape ``(W,)``, range [0, 1].
    """
    H, W = wound_mask.shape
    y_profile = wound_mask.sum(axis=1) / W
    x_profile = wound_mask.sum(axis=0) / H
    return y_profile, x_profile


def envelope_1d(
    y: np.ndarray,
    distance: int = 10,
    kind: str = "linear",
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute upper and lower signal envelopes via peak interpolation.

    Parameters
    ----------
    y : np.ndarray
        1-D signal.
    distance : int
        Minimum distance between detected peaks.
    kind : str
        Interpolation kind passed to :func:`scipy.interpolate.interp1d`.

    Returns
    -------
    upper : np.ndarray
        Upper envelope, same length as *y*.
    lower : np.ndarray
        Lower envelope, same length as *y*.
    """
    x = np.arange(len(y))

    p_max, _ = find_peaks(y, distance=distance)
    p_max = np.r_[0, p_max, len(y) - 1]
    f_max = interp1d(x[p_max], y[p_max], kind=kind, fill_value="extrapolate")
    upper = f_max(x)

    p_min, _ = find_peaks(-y, distance=distance)
    p_min = np.r_[0, p_min, len(y) - 1]
    f_min = interp1d(x[p_min], y[p_min], kind=kind, fill_value="extrapolate")
    lower = f_min(x)

    return upper, lower


def verify_wound_by_distribution(
    wound_mask: np.ndarray,
    gaussian_sigma_y: float = 15,
    peak_prominence: float = 0.15,
    max_center_offset_frac: float = 0.15,
    max_x_skew: float = 0.8,
) -> Dict:
    """Verify wound-mask quality using X/Y profile analysis.

    Checks performed:

    * **Y-axis** -- The smoothed row-sum profile should have exactly one
      prominent peak located near the wound centre.
    * **X-axis** -- The column-sum profile should be roughly flat
      (low skewness, low central-band variance).

    Parameters
    ----------
    wound_mask : np.ndarray
        Binary wound mask, shape ``(H, W)``.
    gaussian_sigma_y : float
        Smoothing sigma for the Y-profile.
    peak_prominence : float
        Minimum prominence for peak detection.
    max_center_offset_frac : float
        Maximum allowed fractional offset between the detected peak
        and the mask centroid.
    max_x_skew : float
        Maximum absolute skewness of the X-profile.

    Returns
    -------
    qc : dict
        ``valid`` (bool), ``y_num_peaks``, ``y_peak_positions``,
        ``y_center_offset_frac``, ``x_skewness``, ``x_flatness``,
        ``y_profile``, ``x_profile``.
    """
    H, W = wound_mask.shape
    mask = wound_mask.astype(bool)

    # Y-axis
    y_profile = mask.sum(axis=1).astype(float)
    y_profile /= y_profile.max() + 1e-6
    y_profile_s = gaussian_filter1d(y_profile, gaussian_sigma_y)

    peaks, _ = find_peaks(
        y_profile_s, prominence=peak_prominence, distance=H // 6,
    )

    wound_center = (
        np.average(np.where(mask)[0]) if mask.any() else np.nan
    )
    center_offsets = (
        np.abs(peaks - wound_center) / H
        if not np.isnan(wound_center)
        else np.array([np.inf])
    )

    y_ok = len(peaks) == 1 and center_offsets[0] < max_center_offset_frac

    # X-axis
    x_profile = mask.sum(axis=0).astype(float)
    x_profile /= x_profile.max() + 1e-6
    x_skew = skew(x_profile)
    central_band = x_profile[int(0.25 * W) : int(0.75 * W)]
    flatness = np.std(central_band)
    x_ok = abs(x_skew) < max_x_skew and flatness < 0.15

    is_valid = y_ok and x_ok

    return {
        "valid": bool(is_valid),
        "y_num_peaks": int(len(peaks)),
        "y_peak_positions": peaks.tolist(),
        "y_center_offset_frac": (
            float(center_offsets[0]) if len(center_offsets) > 0 else None
        ),
        "x_skewness": float(x_skew),
        "x_flatness": float(flatness),
        "y_profile": y_profile_s,
        "x_profile": x_profile,
    }
