"""
Quantification Wound Segmenter
===============================

Stateful wound segmenter with monotonic closure constraint.

Biological axiom
----------------
In a properly conducted scratch-wound assay the wound can only heal
(close) over time.  Therefore:

    ``wound_area(t + 1) <= wound_area(t)``

This module enforces that constraint at the per-column edge level.
Two enforcement strategies are available:

* **Kalman filter** (default, ``use_kalman=True``): fuses the detector
  observation with a monotonic prediction, weighted by per-frame
  confidence.  A hard safety net is applied after the blend.
* **Hard constraint** (``use_kalman=False``): deterministic
  ``max``/``min`` clamping — the original behaviour.
"""

from typing import Optional, Dict, Tuple
from pathlib import Path

import cv2
import numpy as np

from library.core.types import (
    WoundDetectorConfig,
    WoundResult,
    SegmentationResult,
)
from library.wound_standard.detector import WoundDetector
from library.wound_quantification.kalman_constraint import (
    KalmanEdgeFilter,
    estimate_R_per_column,
    DEFAULT_Q,
    _edges_to_mask,
)


class QuantificationSegmenter:
    """Stateful wound segmenter with monotonic closure constraint.

    Key axiom: ``wound_area(t+1) <= wound_area(t)``.
    The wound can only shrink or stay the same, never grow.

    The constraint is enforced per-column:

    * Upper edge: ``upper(t+1) >= upper(t)``  (can only move down)
    * Lower edge: ``lower(t+1) <= lower(t)``  (can only move up)

    When ``config.use_kalman`` is True (default), a per-column Kalman
    filter blends the detector observation with the monotonic prediction
    before applying the hard safety net.  This attenuates spurious
    inward edges from debris or focus artifacts.

    Usage
    -----
    segmenter = QuantificationSegmenter()
     for t, img_path in enumerate(image_paths):
         result = segmenter.segment(img_path, t=t)
         print(f"t={t}, area={result.area}")
     segmenter.reset()

    Parameters
    ----------
    config : WoundDetectorConfig | None
        Configuration for the underlying variance-based detector and
        the Kalman filter parameters.
    detector : WoundDetector | None
        Pre-configured detector instance.  If provided, *config* is
        ignored for detector construction (but Kalman settings are still
        read from ``detector.config``).
    """

    def __init__(
        self,
        config: Optional[WoundDetectorConfig] = None,
        detector: Optional[WoundDetector] = None,
    ) -> None:
        self.detector = detector or WoundDetector(config)
        self._config = self.detector.config
        self._kalman: Optional[KalmanEdgeFilter] = None
        self.reset()

    def reset(self) -> None:
        """Reset all internal state for a new trajectory.

        Clears the reference frame (t=0) edges, the previous-frame
        edges, the Kalman filter state, and the internal time counter.
        Call this before processing a new sample.
        """
        self.t0_mask: Optional[np.ndarray] = None
        self.t0_upper: Optional[np.ndarray] = None
        self.t0_lower: Optional[np.ndarray] = None
        self.t0_area: int = 0
        self.prev_mask: Optional[np.ndarray] = None
        self.prev_upper: Optional[np.ndarray] = None
        self.prev_lower: Optional[np.ndarray] = None
        self._wound_closed: bool = False
        self._t: int = -1
        self._kalman = None

    def segment(
        self,
        img: np.ndarray | Path | str,
        t: Optional[int] = None,
        file_name: Optional[Path] = None,
        debug: bool = False,
        save_path: Optional[Path] = None,
    ) -> SegmentationResult:
        """Segment wound with monotonic constraint.

        Parameters
        ----------
        img : np.ndarray | Path | str
            Grayscale image or path to image file.
        t : int | None
            Time-point index.  Auto-increments when ``None``.
        file_name : Path | None
            Original file name for metadata.
        debug : bool
            If ``True``, the underlying detector produces a debug figure.
        save_path : Path | None
            Destination for the debug figure.

        Returns
        -------
        SegmentationResult
            Segmentation output including constrained mask, edges, area,
            and quality-control metrics.

        Raises
        ------
        ValueError
            If image cannot be loaded from the given path.

        Notes
        -----
        * At ``t = 0`` the raw detector output is used as-is and stored
          as the reference.
        * At ``t > 0`` the constraint (Kalman or hard) is applied.
        """
        # Auto-increment time
        if t is None:
            t = self._t + 1
        self._t = t

        # Load image if path
        if isinstance(img, (str, Path)):
            file_name = file_name or Path(img)
            img_bgr = cv2.imread(str(img), cv2.IMREAD_COLOR)
            if img_bgr is None:
                raise ValueError(f"Failed to load image: {file_name}")
            img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        elif img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        img_raw = img.copy()

        # Detect wound (single-frame, no temporal info)
        result = self.detector.detect(img, debug=debug, save_path=save_path)

        constrained = False

        if t == 0:
            # First frame: establish reference
            self.t0_mask = result.mask.copy()
            self.t0_upper = result.upper_edge.copy()
            self.t0_lower = result.lower_edge.copy()
            self.t0_area = int(result.mask.sum())
            self.prev_mask = result.mask.copy()
            self.prev_upper = result.upper_edge.copy()
            self.prev_lower = result.lower_edge.copy()

            # Initialise Kalman filter if enabled
            if self._config.use_kalman:
                self._init_kalman(result)
        else:
            # --- Wound closure freeze ---
            # Once the wound is declared closed, lock edges permanently.
            if self._wound_closed:
                upper = self.prev_upper.copy()
                lower = self.prev_lower.copy()
                mask = self.prev_mask.copy()
                constrained = True
            else:
                # Check closure: prev area < threshold * t0 area
                prev_area = int(self.prev_mask.sum()) if self.prev_mask is not None else 0
                if (
                    self.t0_area > 0
                    and prev_area / self.t0_area < self._config.closure_threshold
                ):
                    self._wound_closed = True
                    upper = self.prev_upper.copy()
                    lower = self.prev_lower.copy()
                    mask = self.prev_mask.copy()
                    constrained = True
                elif self._config.use_kalman and self._kalman is not None:
                    upper, lower, mask, constrained = self._enforce_kalman(
                        result, img.shape
                    )
                else:
                    upper, lower, mask, constrained = self._enforce_monotonic(
                        result.upper_edge,
                        result.lower_edge,
                        img.shape,
                    )

            # --- Last-resort monotonic backstop ---
            # If any upstream bug allows area to increase despite all constraint
            # paths, clamp back to the previous frame.  This is a safety net for
            # correctness; it should never fire in normal operation.  A warning
            # is emitted so regressions are immediately visible.
            if self.prev_mask is not None:
                new_area = int(mask.sum())
                prev_area_check = int(self.prev_mask.sum())
                if new_area > prev_area_check:
                    import warnings
                    warnings.warn(
                        f"[QuantificationSegmenter] Monotonic invariant violated at t={t}: "
                        f"area={new_area} > prev_area={prev_area_check}. "
                        f"Reverting to previous frame edges. "
                        f"Investigate Kalman/NaN state for this trajectory.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    mask = self.prev_mask.copy()
                    upper = self.prev_upper.copy()
                    lower = self.prev_lower.copy()
                    constrained = True

            result = WoundResult(
                mask=mask,
                upper_edge=upper,
                lower_edge=lower,
                y_center=result.y_center,
                y_band=result.y_band,
                qc=result.qc,
                method=result.method,
            )

            # Update previous state
            self.prev_mask = mask.copy()
            self.prev_upper = upper.copy()
            self.prev_lower = lower.copy()

        return SegmentationResult(
            t=t,
            file_name=file_name,
            img_raw=img_raw,
            mask=result.mask,
            upper_edge=result.upper_edge,
            lower_edge=result.lower_edge,
            area=int(result.mask.sum()),
            qc=result.qc,
            method=result.method,
            constrained=constrained,
        )

    # -----------------------------------------------------------------
    # Kalman filter integration
    # -----------------------------------------------------------------

    def _init_kalman(self, result: WoundResult) -> None:
        """Initialise the Kalman edge filter from the t=0 frame.

        Parameters
        ----------
        result : WoundResult
            Detection result for the first frame.
        """
        cfg = self._config
        W = len(result.upper_edge)

        Q = cfg.kalman_Q if cfg.kalman_Q is not None else DEFAULT_Q

        # R_base: from config, or from edge residuals, or default
        if cfg.kalman_R_base is not None:
            R_base = cfg.kalman_R_base
        elif result.edge_residuals_upper is not None:
            finite = result.edge_residuals_upper[
                np.isfinite(result.edge_residuals_upper)
            ]
            R_base = float(np.var(finite)) if len(finite) > 5 else Q * 0.1
        else:
            R_base = Q * 0.1

        self._kalman = KalmanEdgeFilter(
            W=W,
            Q=Q,
            spatial_sigma=cfg.kalman_spatial_sigma,
        )
        self._kalman.initialise(
            upper=result.upper_edge,
            lower=result.lower_edge,
            R_base=max(R_base, 1.0),
        )

    def _enforce_kalman(
        self,
        result: WoundResult,
        img_shape: Tuple[int, int],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
        """Apply Kalman-filtered monotonic constraint.

        Parameters
        ----------
        result : WoundResult
            Detection result for the current frame (includes optional
            variance_map and edge_residuals for R estimation).
        img_shape : tuple of (int, int)
            ``(H, W)`` for mask reconstruction.

        Returns
        -------
        upper, lower : np.ndarray
            Constrained edges.
        mask : np.ndarray
            Binary wound mask.
        constrained : bool
            Whether the hard safety net modified any edge.
        """
        cfg = self._config

        # Compute per-column R for upper edge
        R_upper = estimate_R_per_column(
            edge_residuals=result.edge_residuals_upper,
            variance_map=result.variance_map,
            upper_edge=result.upper_edge,
            lower_edge=result.lower_edge,
            y_band=result.y_band,
            method=result.method,
            prev_edge=self.prev_upper,
            detected_edge=result.upper_edge,
            R_base_override=cfg.kalman_R_base,
            fallback_multiplier=cfg.kalman_fallback_multiplier,
        )

        # Compute per-column R for lower edge
        R_lower = estimate_R_per_column(
            edge_residuals=result.edge_residuals_lower,
            variance_map=result.variance_map,
            upper_edge=result.upper_edge,
            lower_edge=result.lower_edge,
            y_band=result.y_band,
            method=result.method,
            prev_edge=self.prev_lower,
            detected_edge=result.lower_edge,
            R_base_override=cfg.kalman_R_base,
            fallback_multiplier=cfg.kalman_fallback_multiplier,
        )

        return self._kalman.update(
            detected_upper=result.upper_edge,
            detected_lower=result.lower_edge,
            R_upper=R_upper,
            R_lower=R_lower,
            img_shape=img_shape,
        )

    # -----------------------------------------------------------------
    # Hard monotonic constraint (fallback when Kalman is disabled)
    # -----------------------------------------------------------------

    def _enforce_monotonic(
        self,
        upper: np.ndarray,
        lower: np.ndarray,
        img_shape: Tuple[int, int],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
        """Enforce hard monotonic constraint: wound can only shrink.

        Formal constraint per column *x*:

        .. math::

            \\text{upper}_{t+1}(x) = \\max\\bigl(\\text{upper}_t(x),\\;
            \\text{upper}_{\\text{det}}(x)\\bigr)

            \\text{lower}_{t+1}(x) = \\min\\bigl(\\text{lower}_t(x),\\;
            \\text{lower}_{\\text{det}}(x)\\bigr)

        Parameters
        ----------
        upper, lower : np.ndarray
            Raw detector edges for the current frame, shape ``(W,)``.
        img_shape : tuple of int
            ``(H, W)`` of the image.

        Returns
        -------
        upper_constrained, lower_constrained : np.ndarray
        mask : np.ndarray
            Binary wound mask rebuilt from constrained edges.
        constrained : bool
            True if the constraint modified any edge value.

        Notes
        -----
        Columns where the upper edge meets or exceeds the lower edge
        are treated as fully closed (zero wound width) rather than
        forcing a 1-pixel minimum gap.  This eliminates the systematic
        area bias that a forced gap would introduce at late timepoints.
        """
        H, W = img_shape
        max_jump = self._config.max_edge_jump

        # NaN guard: replace NaN detector outputs with previous state
        upper_safe = np.where(np.isfinite(upper), upper, self.prev_upper)
        lower_safe = np.where(np.isfinite(lower), lower, self.prev_lower)

        # Jump guard: clamp detected edges to prev ± max_jump.
        # Prevents spatially implausible detections (e.g. wound ROI
        # relocating to image border after full closure) from being
        # accepted by the directional min/max constraint.
        upper_safe = np.clip(
            upper_safe,
            self.prev_upper - max_jump,
            self.prev_upper + max_jump,
        )
        lower_safe = np.clip(
            lower_safe,
            self.prev_lower - max_jump,
            self.prev_lower + max_jump,
        )

        # Upper edge: max(current, previous) - can only move down
        upper_constrained = np.maximum(upper_safe, self.prev_upper)

        # Lower edge: min(current, previous) - can only move up
        lower_constrained = np.minimum(lower_safe, self.prev_lower)

        constrained = bool(
            np.any(upper_constrained != upper_safe)
            or np.any(lower_constrained != lower_safe)
        )

        mask = _edges_to_mask(upper_constrained, lower_constrained, H, W)

        return upper_constrained, lower_constrained, mask, constrained
