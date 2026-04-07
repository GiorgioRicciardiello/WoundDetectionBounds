"""
Kalman-Filtered Monotonic Edge Constraint
==========================================

Replaces the hard ``max``/``min`` monotonic constraint with a 1-D
per-column Kalman filter that fuses the detector observation with a
monotonic prediction, weighted by per-frame confidence.

Key advantage over the hard constraint: a spurious inward edge (debris,
bubble, focus artifact) receives high observation noise R, so the filter
relies on the monotonic prediction instead.  Once the artifact clears,
the next clean frame is trusted again.  The hard constraint permanently
locks spurious edges; this filter attenuates them.

A hard safety net is still applied *after* the Kalman blend to guarantee
the biological invariant (wound area can only decrease).

Q/R Parameter Resolution
-------------------------
Both Q and R can be supplied explicitly via ``WoundDetectorConfig``.
When set to ``None`` they are estimated from data:

* **Q** — estimated from frame-to-frame edge variance across clean
  trajectories (cached results).  Falls back to a conservative default
  (``DEFAULT_Q = 400.0 px²``) on first run when no cache exists.
* **R_base** — estimated per-frame from the residuals between raw and
  smoothed edges (RANSAC + Savgol pipeline).

Clean trajectories for Q estimation are selected by one of:
1. QC flag (``qc["valid"] == True`` at t=0) — default
2. Verification library results
3. Explicit list of trajectory keys provided by the user
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter1d


# Conservative default when no cached data is available.
# Derived from biology: cell migration ~10-30 µm/h × 1.24 px/µm × ~2 h
# interval ≈ 16-48 px displacement → variance ≈ (20 px)² = 400 px².
DEFAULT_Q: float = 400.0

# Minimum observation noise to prevent division by zero and avoid
# over-trusting any single detector output.
_MIN_R: float = 1.0


# ---------------------------------------------------------------------------
# Q estimation from cached trajectories
# ---------------------------------------------------------------------------

def estimate_Q_from_trajectories(
    trajectories: Dict,
    clean_keys: Optional[List[str]] = None,
    use_qc_filter: bool = True,
) -> float:
    """Estimate process noise Q from frame-to-frame edge differences.

    Q is the variance of the per-column edge displacement between
    consecutive frames, averaged across all clean trajectories.  This
    captures the expected biological edge movement per frame.

    Parameters
    ----------
    trajectories : dict
        Trajectory dictionary (same format as the pipeline output).
        Each value must contain ``"results"`` with per-frame ``upper_edge``
        and ``lower_edge`` arrays.
    clean_keys : list of str or None
        Explicit list of trajectory keys to use.  When provided,
        ``use_qc_filter`` is ignored.
    use_qc_filter : bool
        When ``clean_keys`` is None and this is True, only trajectories
        whose t=0 frame has ``qc["valid"] == True`` are used.

    Returns
    -------
    float
        Estimated Q (variance in px²).  Returns ``DEFAULT_Q`` if
        insufficient data is available (fewer than 2 clean frame pairs).
    """
    keys = _resolve_clean_keys(trajectories, clean_keys, use_qc_filter)
    if not keys:
        return DEFAULT_Q

    all_deltas: List[np.ndarray] = []

    for key in keys:
        traj = trajectories.get(key)
        if traj is None:
            continue
        results = traj.get("results", [])
        results_sorted = sorted(
            [r for r in results if r.get("t") is not None],
            key=lambda r: r["t"],
        )
        if len(results_sorted) < 2:
            continue

        for i in range(len(results_sorted) - 1):
            upper_cur = results_sorted[i].get("upper_edge")
            upper_nxt = results_sorted[i + 1].get("upper_edge")
            lower_cur = results_sorted[i].get("lower_edge")
            lower_nxt = results_sorted[i + 1].get("lower_edge")

            if any(e is None for e in (upper_cur, upper_nxt, lower_cur, lower_nxt)):
                continue

            upper_cur = np.asarray(upper_cur, dtype=np.float64)
            upper_nxt = np.asarray(upper_nxt, dtype=np.float64)
            lower_cur = np.asarray(lower_cur, dtype=np.float64)
            lower_nxt = np.asarray(lower_nxt, dtype=np.float64)

            # Per-column differences for both edges
            valid_u = np.isfinite(upper_cur) & np.isfinite(upper_nxt)
            valid_l = np.isfinite(lower_cur) & np.isfinite(lower_nxt)

            if valid_u.any():
                all_deltas.append(upper_nxt[valid_u] - upper_cur[valid_u])
            if valid_l.any():
                all_deltas.append(lower_nxt[valid_l] - lower_cur[valid_l])

    if not all_deltas:
        return DEFAULT_Q

    concatenated = np.concatenate(all_deltas)
    if len(concatenated) < 10:
        return DEFAULT_Q

    return float(np.var(concatenated))


def _resolve_clean_keys(
    trajectories: Dict,
    clean_keys: Optional[List[str]],
    use_qc_filter: bool,
) -> List[str]:
    """Resolve the set of trajectory keys to use for Q estimation.

    Parameters
    ----------
    trajectories : dict
        Full trajectory dictionary.
    clean_keys : list of str or None
        User-provided explicit list.  Takes priority when not None.
    use_qc_filter : bool
        When True and clean_keys is None, filter by t=0 QC validity.

    Returns
    -------
    list of str
        Trajectory keys to use.
    """
    if clean_keys is not None:
        return [k for k in clean_keys if k in trajectories]

    if not use_qc_filter:
        return list(trajectories.keys())

    # Filter by t=0 QC validity
    valid_keys: List[str] = []
    for key, traj in trajectories.items():
        results = traj.get("results", [])
        t0 = next((r for r in results if r.get("t") == 0), None)
        if t0 is not None and t0.get("qc", {}).get("valid", False):
            valid_keys.append(key)

    return valid_keys


# ---------------------------------------------------------------------------
# Per-frame R estimation
# ---------------------------------------------------------------------------

def estimate_R_per_column(
    edge_residuals: Optional[np.ndarray],
    variance_map: Optional[np.ndarray],
    upper_edge: np.ndarray,
    lower_edge: np.ndarray,
    y_band: Tuple[int, int],
    method: str,
    prev_edge: np.ndarray,
    detected_edge: np.ndarray,
    R_base_override: Optional[float] = None,
    fallback_multiplier: float = 3.0,
) -> np.ndarray:
    """Compute per-column observation noise R for the Kalman update.

    R is composed of three multiplicative signals:

    1. **R_base** — baseline detector noise, estimated from the variance
       of edge residuals (raw - smoothed).  Overridden by
       ``R_base_override`` when not None.
    2. **Contrast factor** — inverse of local cell/wound variance
       contrast.  Low contrast → high R (ambiguous boundary).
    3. **Jump factor** — large deviations from the predicted edge
       receive higher R (likely artifact).

    A method multiplier is applied for fallback detections.

    Parameters
    ----------
    edge_residuals : np.ndarray or None
        Per-column residuals (raw_edge - smoothed_edge), shape ``(W,)``.
    variance_map : np.ndarray or None
        2-D smoothed variance map, shape ``(H, W)``.
    upper_edge : np.ndarray
        Upper wound edge, shape ``(W,)``.
    lower_edge : np.ndarray
        Lower wound edge, shape ``(W,)``.
    y_band : tuple of (int, int)
        ``(y_min, y_max)`` of the detected wound band.
    method : str
        ``"primary"`` or ``"fallback"``.
    prev_edge : np.ndarray
        Previous frame's constrained edge, shape ``(W,)``.
    detected_edge : np.ndarray
        Current frame's raw detected edge, shape ``(W,)``.
    R_base_override : float or None
        If provided, used as R_base instead of estimating from residuals.
    fallback_multiplier : float
        Multiplier applied to R when method is ``"fallback"``.

    Returns
    -------
    np.ndarray
        Per-column R values, shape ``(W,)``, clipped to ``>= _MIN_R``.
    """
    W = len(detected_edge)

    # --- R_base: from edge residuals or override ---
    if R_base_override is not None:
        R_base = R_base_override
    elif edge_residuals is not None:
        finite = edge_residuals[np.isfinite(edge_residuals)]
        R_base = float(np.var(finite)) if len(finite) > 5 else DEFAULT_Q * 0.1
    else:
        R_base = DEFAULT_Q * 0.1

    R_base = max(R_base, _MIN_R)
    R = np.full(W, R_base, dtype=np.float64)

    # --- Contrast factor: low contrast → high R ---
    if variance_map is not None:
        H = variance_map.shape[0]
        y_min, y_max = y_band

        # Cell region variance (above and below wound band)
        cell_top = variance_map[:max(1, y_min), :]
        cell_bot = variance_map[min(H - 1, y_max):, :]

        cell_var = np.nanmean(
            np.concatenate([cell_top, cell_bot], axis=0), axis=0
        )

        # Wound region variance
        wound_var = np.nanmean(
            variance_map[y_min:y_max + 1, :], axis=0
        )

        contrast = (cell_var - wound_var) / (cell_var + 1e-12)
        contrast = np.clip(contrast, 0.01, 1.0)

        # Inverse square: low contrast → large multiplier
        R = R / (contrast ** 2)

    # --- Jump factor: large deviation from prediction → high R ---
    jump = np.abs(detected_edge - prev_edge)
    finite_jump = jump[np.isfinite(jump)]
    median_jump = float(np.median(finite_jump)) if len(finite_jump) > 0 else 1.0
    median_jump = max(median_jump, 1.0)

    # NaN guard: NaN entries in jump (caused by NaN prev_edge or detected_edge)
    # are treated as zero-displacement — neutral, no additional penalty.
    jump_safe = np.where(np.isfinite(jump), jump, 0.0)
    jump_factor = 1.0 + (jump_safe / median_jump) ** 2
    R = R * jump_factor

    # --- Method multiplier ---
    if method == "fallback":
        R = R * fallback_multiplier

    # NaN/Inf guard: any remaining non-finite R (e.g. from NaN contrast map)
    # falls back to the conservative DEFAULT_Q value.
    R = np.where(np.isfinite(R), R, DEFAULT_Q)
    return np.clip(R, _MIN_R, None)


# ---------------------------------------------------------------------------
# Kalman Edge Filter
# ---------------------------------------------------------------------------

class KalmanEdgeFilter:
    """Per-column 1-D Kalman filter for wound edge tracking.

    Maintains state (filtered edge position and uncertainty) for each
    column across frames.  At each frame, fuses the detector observation
    with a monotonic prediction (wound can only close), weighted by the
    observation noise R.

    A hard safety net is applied after the Kalman update to guarantee
    the biological invariant.

    Parameters
    ----------
    W : int
        Image width (number of columns).
    Q : float
        Process noise (edge movement variance per frame).
    spatial_sigma : float
        Gaussian sigma for spatial smoothing of detected edges before
        the Kalman update, in columns.  Removes column-level artifacts
        (debris, bubbles) that would otherwise be locked.
    """

    def __init__(
        self,
        W: int,
        Q: float,
        spatial_sigma: float = 5.0,
    ) -> None:
        self._W = W
        self._Q = Q
        self._spatial_sigma = spatial_sigma

        # Per-column state (initialised on first call)
        self._upper: Optional[np.ndarray] = None
        self._lower: Optional[np.ndarray] = None
        self._P_upper: Optional[np.ndarray] = None
        self._P_lower: Optional[np.ndarray] = None

    @property
    def is_initialised(self) -> bool:
        """True after the first frame (t=0) has been processed."""
        return self._upper is not None

    def initialise(
        self,
        upper: np.ndarray,
        lower: np.ndarray,
        R_base: float,
    ) -> None:
        """Set initial state from the t=0 detector output.

        Parameters
        ----------
        upper, lower : np.ndarray
            Detected edges at t=0, shape ``(W,)``.
        R_base : float
            Baseline observation noise, used as initial uncertainty P₀.
        """
        self._upper = upper.astype(np.float64).copy()
        self._lower = lower.astype(np.float64).copy()
        self._P_upper = np.full(self._W, max(R_base, _MIN_R), dtype=np.float64)
        self._P_lower = np.full(self._W, max(R_base, _MIN_R), dtype=np.float64)

    def update(
        self,
        detected_upper: np.ndarray,
        detected_lower: np.ndarray,
        R_upper: np.ndarray,
        R_lower: np.ndarray,
        img_shape: Tuple[int, int],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
        """Run one Kalman update step for both edges.

        Steps per edge:
        1. Spatial smoothing of detected edges.
        2. Prediction: monotonic prior (upper can only go down, lower up).
        3. Kalman gain and state update.
        4. Hard safety net: enforce monotonicity on filtered result.
        5. Rebuild binary mask from constrained edges.

        Parameters
        ----------
        detected_upper, detected_lower : np.ndarray
            Raw detector edges for the current frame, shape ``(W,)``.
        R_upper, R_lower : np.ndarray
            Per-column observation noise, shape ``(W,)``.
        img_shape : tuple of (int, int)
            ``(H, W)`` for mask reconstruction.

        Returns
        -------
        upper_out : np.ndarray
            Filtered + constrained upper edge, shape ``(W,)``.
        lower_out : np.ndarray
            Filtered + constrained lower edge, shape ``(W,)``.
        mask : np.ndarray
            Binary wound mask, shape ``(H, W)``, dtype ``uint8``.
        constrained : bool
            True if the hard safety net modified any column.
        """
        if not self.is_initialised:
            raise RuntimeError(
                "KalmanEdgeFilter.initialise() must be called before update()."
            )

        H, W = img_shape

        # --- NaN guard: replace NaN detector outputs with previous state ---
        det_upper = np.where(
            np.isfinite(detected_upper), detected_upper, self._upper
        ).astype(np.float64)
        det_lower = np.where(
            np.isfinite(detected_lower), detected_lower, self._lower
        ).astype(np.float64)

        # --- Spatial smoothing to remove column-level artifacts ---
        if self._spatial_sigma > 0:
            det_upper = gaussian_filter1d(det_upper, sigma=self._spatial_sigma)
            det_lower = gaussian_filter1d(det_lower, sigma=self._spatial_sigma)

        # --- Kalman update for upper edge ---
        upper_filtered, P_upper_new, P_predicted_upper = self._kalman_step(
            state=self._upper,
            P=self._P_upper,
            observation=det_upper,
            R=R_upper,
        )

        # --- Kalman update for lower edge ---
        lower_filtered, P_lower_new, P_predicted_lower = self._kalman_step(
            state=self._lower,
            P=self._P_lower,
            observation=det_lower,
            R=R_lower,
        )

        # --- NaN guard on Kalman outputs ---
        # If NaN propagates from a corrupt state or R value, fall back to the
        # previous constrained edge so the safety net can still operate.
        upper_filtered = np.where(
            np.isfinite(upper_filtered), upper_filtered, self._upper
        )
        lower_filtered = np.where(
            np.isfinite(lower_filtered), lower_filtered, self._lower
        )

        # --- Hard safety net (monotonic invariant) ---
        # Upper edge can only move down (increase in image coords)
        upper_constrained = np.maximum(upper_filtered, self._upper)
        # Lower edge can only move up (decrease in image coords)
        lower_constrained = np.minimum(lower_filtered, self._lower)

        constrained = bool(
            np.any(upper_constrained != upper_filtered)
            or np.any(lower_constrained != lower_filtered)
        )

        # --- P correction after safety net ---
        # When the safety net overrides the Kalman estimate, the contracted
        # P_new no longer reflects the true state uncertainty — the constraint
        # gives us no additional information about the edge position.  Reset P
        # to P_predicted for those columns so the filter does not become
        # overconfident on subsequent frames after a clamped step.
        P_upper_corrected = np.where(
            upper_constrained != upper_filtered, P_predicted_upper, P_upper_new
        )
        P_lower_corrected = np.where(
            lower_constrained != lower_filtered, P_predicted_lower, P_lower_new
        )

        # --- Update internal state ---
        self._upper = upper_constrained.copy()
        self._lower = lower_constrained.copy()
        self._P_upper = P_upper_corrected
        self._P_lower = P_lower_corrected

        # --- Rebuild mask ---
        mask = _edges_to_mask(upper_constrained, lower_constrained, H, W)

        return upper_constrained, lower_constrained, mask, constrained

    def _kalman_step(
        self,
        state: np.ndarray,
        P: np.ndarray,
        observation: np.ndarray,
        R: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Single Kalman predict-update cycle (per-column, vectorized).

        Parameters
        ----------
        state : np.ndarray
            Previous filtered edge, shape ``(W,)``.
        P : np.ndarray
            Previous uncertainty, shape ``(W,)``.
        observation : np.ndarray
            Current detector edge, shape ``(W,)``.
        R : np.ndarray
            Per-column observation noise, shape ``(W,)``.

        Returns
        -------
        state_new : np.ndarray
            Updated edge estimate, shape ``(W,)``.
        P_new : np.ndarray
            Updated uncertainty, shape ``(W,)``.
        P_predicted : np.ndarray
            Pre-update predicted uncertainty, shape ``(W,)``.  Returned so
            the caller can reset P to P_predicted for columns where the hard
            safety net overrides the Kalman estimate.
        """
        # Prediction step: state prediction is just previous state
        # (monotonic model: edge doesn't move unless observed)
        P_predicted = P + self._Q

        # Kalman gain: K = P_predicted / (P_predicted + R)
        K = P_predicted / (P_predicted + R)

        # Update step: blend prediction with observation
        innovation = observation - state
        state_new = state + K * innovation

        # Updated uncertainty
        P_new = (1.0 - K) * P_predicted

        return state_new, np.clip(P_new, _MIN_R, None), P_predicted

    def reset(self) -> None:
        """Clear all internal state for a new trajectory."""
        self._upper = None
        self._lower = None
        self._P_upper = None
        self._P_lower = None


# ---------------------------------------------------------------------------
# Utility: mask from edges (shared with segmenter)
# ---------------------------------------------------------------------------

def _edges_to_mask(
    upper: np.ndarray,
    lower: np.ndarray,
    H: int,
    W: int,
) -> np.ndarray:
    """Build a binary wound mask from upper and lower edge arrays.

    Vectorized implementation using NumPy broadcasting.  Columns where
    the upper edge meets or exceeds the lower edge are treated as fully
    closed (zero wound width).

    Parameters
    ----------
    upper, lower : np.ndarray
        Per-column edge positions, shape ``(W,)``.
    H, W : int
        Image dimensions.

    Returns
    -------
    np.ndarray
        Binary mask, shape ``(H, W)``, dtype ``uint8``.
    """
    y_up = np.clip(upper, 0, H - 1).astype(int)
    y_lo = np.clip(lower, 0, H - 1).astype(int)
    rows = np.arange(H)[:, None]

    open_cols = y_up < y_lo
    mask = (
        (rows >= y_up[None, :])
        & (rows <= y_lo[None, :])
        & open_cols[None, :]
    ).astype(np.uint8)

    return mask
