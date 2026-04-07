"""
Robust Wound Detection Pipeline
================================

Multi-stage wound detection using local variance analysis and
geometric constraints for scratch wound healing assays.

Key insight: Wound is ALWAYS a horizontal band spanning full image width.
Cells have high texture (variance), wound is smooth (low variance).

This module provides the :class:`WoundDetector` class which implements a
six-stage pipeline (local variance, Y-band detection, column-wise edge
extraction, RANSAC outlier rejection, Savitzky-Golay smoothing, and
geometric validation) together with a fallback region-growing strategy.

Configuration and result data classes are defined in
:mod:`library.core.types` and imported here.
"""

from typing import Tuple, Optional, Dict
import numpy as np
import cv2
from scipy.ndimage import uniform_filter, gaussian_filter1d
from scipy.signal import savgol_filter
from skimage.morphology import remove_small_objects, remove_small_holes, disk, closing
from skimage.measure import label, regionprops
import matplotlib.pyplot as plt
from pathlib import Path

from library.core.types import WoundDetectorConfig, WoundResult


class WoundDetector:
    """
    Robust wound detector for scratch wound healing assays.

    Pipeline
    --------
    1. Local variance map (texture analysis)
    2. Y-profile band detection
    3. Column-wise edge extraction (vectorized)
    4. RANSAC outlier rejection
    5. Savitzky-Golay smoothing
    6. Geometric validation
    7. Fallback region-growing if validation fails

    Parameters
    ----------
    config : WoundDetectorConfig or None
        Configuration object controlling every stage of the pipeline.
        When *None*, default values from :class:`WoundDetectorConfig` are
        used.

    Attributes
    ----------
    config : WoundDetectorConfig
        Active configuration for all pipeline stages.

    Examples
    --------
    >>> from library.wound_standard.detector import WoundDetector
    >>> detector = WoundDetector()
    >>> result = detector.detect(grayscale_image)
    >>> result.qc['valid']
    True
    """

    def __init__(self, config: Optional[WoundDetectorConfig] = None):
        """
        Initialise the wound detector.

        Parameters
        ----------
        config : WoundDetectorConfig or None, optional
            Pipeline configuration.  Defaults to ``WoundDetectorConfig()``
            which uses sensible defaults tuned for typical scratch-wound
            assay images.
        """
        self.config = config or WoundDetectorConfig()

    def detect(
        self,
        img: np.ndarray,
        debug: bool = False,
        save_path: Optional[Path] = None,
    ) -> WoundResult:
        """
        Detect the wound region in a grayscale image.

        Runs the full six-stage pipeline and, if validation fails, an
        optional fallback region-growing strategy.

        Parameters
        ----------
        img : np.ndarray
            Input image.  Expected to be 2-D grayscale (H, W) with dtype
            ``uint8`` or ``float``.  If a 3-D colour image is passed it is
            automatically converted to grayscale via
            ``cv2.cvtColor(..., cv2.COLOR_BGR2GRAY)``.
        debug : bool, optional
            When *True*, a six-panel debug figure is created showing every
            intermediate stage of the pipeline.  Default is *False*.
        save_path : pathlib.Path or None, optional
            If provided (and *debug* is *True*), the debug figure is saved
            to this path instead of being displayed with ``plt.show()``.

        Returns
        -------
        WoundResult
            A dataclass containing the binary wound mask, upper/lower edge
            arrays, Y-centre, Y-band limits, quality-control metrics, and
            the detection method used (``'primary'`` or ``'fallback'``).

        Raises
        ------
        ValueError
            If *img* is not 2-D or 3-D.
        """
        cfg = self.config

        # Defensive check: ensure image is 2D grayscale
        if img.ndim == 3:
            # Convert 3D (color) to 2D (grayscale)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif img.ndim != 2:
            raise ValueError(f"Expected 2D grayscale image, got shape {img.shape}")

        H, W = img.shape

        # Normalize
        img_f = img.astype(np.float32)
        if img_f.max() > 1.0:
            img_f = img_f / 255.0

        # === STAGE 1: Local Variance Map ===
        variance_map = self._compute_local_variance(img_f, cfg.variance_window)
        variance_smooth = gaussian_filter1d(
            gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
            cfg.variance_sigma, axis=1
        )

        # === STAGE 2: Y-Profile Band Detection ===
        y_min, y_max, y_center = self._detect_y_band(variance_smooth)

        # === STAGE 3: Column-wise Edge Extraction ===
        upper_raw, lower_raw = self._extract_edges_per_column(
            variance_smooth, y_min, y_max, y_center
        )

        # === STAGE 4: RANSAC Outlier Rejection ===
        upper_ransac, lower_ransac = self._ransac_smooth_edges(
            upper_raw, lower_raw
        )

        # === STAGE 5: Savgol Smoothing ===
        upper_smooth = self._savgol_smooth(upper_ransac)
        lower_smooth = self._savgol_smooth(lower_ransac)

        # === STAGE 6: Create Mask ===
        mask = self._edges_to_mask(upper_smooth, lower_smooth, H, W)

        # === STAGE 7: Validation ===
        qc = self._validate_wound_geometry(mask)

        # Optional: compute Kalman R estimation signals
        kalman_kwargs: Dict = {}
        if cfg.use_kalman:
            kalman_kwargs["variance_map"] = variance_smooth
            kalman_kwargs["edge_residuals_upper"] = upper_ransac - upper_smooth
            kalman_kwargs["edge_residuals_lower"] = lower_ransac - lower_smooth

        result = WoundResult(
            mask=mask,
            upper_edge=upper_smooth,
            lower_edge=lower_smooth,
            y_center=y_center,
            y_band=(y_min, y_max),
            qc=qc,
            method="primary",
            **kalman_kwargs,
        )

        # === FALLBACK if validation fails ===
        if not qc["valid"] and cfg.fallback_enabled:
            result = self._fallback_detection(
                img_f, variance_smooth, y_center, result
            )

        # === DEBUG VISUALIZATION ===
        if debug:
            self._debug_plot(
                img_f, variance_smooth,
                upper_raw, lower_raw,
                upper_smooth, lower_smooth,
                mask, result, save_path
            )

        return result

    # =========================================================================
    # STAGE 1: Local Variance
    # =========================================================================

    def _compute_local_variance(
        self,
        img: np.ndarray,
        window: int
    ) -> np.ndarray:
        """
        Compute a local-variance texture map.

        Cells produce high variance (textured), whereas the wound channel
        is smooth (low variance).  The variance is computed efficiently
        using uniform-filter means of the image and its square:

        .. math::
            \\sigma^2(x,y) = \\langle I^2 \\rangle - \\langle I \\rangle^2

        Parameters
        ----------
        img : np.ndarray
            2-D float image, typically normalised to [0, 1].
        window : int
            Side length of the square averaging kernel used by
            ``scipy.ndimage.uniform_filter``.

        Returns
        -------
        np.ndarray
            2-D array of the same shape as *img* containing the local
            variance at every pixel.  Values are clipped to >= 0.
        """
        img_f = img.astype(np.float64)
        mean = uniform_filter(img_f, size=window)
        sqr_mean = uniform_filter(img_f ** 2, size=window)
        variance = np.maximum(sqr_mean - mean ** 2, 0)
        return variance

    # =========================================================================
    # STAGE 2: Y-Profile Band Detection
    # =========================================================================

    def _detect_y_band(
        self,
        variance_map: np.ndarray
    ) -> Tuple[int, int, int]:
        """
        Identify the vertical (Y) range that contains the wound.

        Collapses the 2-D variance map to a 1-D row-average profile,
        smooths it, and finds the valley (minimum-variance region).  A
        contiguous band of rows falling below a percentile threshold is
        then expanded by a configurable margin.

        Parameters
        ----------
        variance_map : np.ndarray
            2-D smoothed variance map of shape ``(H, W)``.

        Returns
        -------
        y_min : int
            Top row of the detected Y-band (inclusive, after margin).
        y_max : int
            Bottom row of the detected Y-band (inclusive, after margin).
        y_center : int
            Row index of the global minimum in the smoothed Y-profile,
            taken as the approximate wound centre.
        """
        cfg = self.config
        H, W = variance_map.shape

        # Average variance per row
        y_profile = variance_map.mean(axis=1)

        # Smooth profile
        y_smooth = gaussian_filter1d(y_profile, sigma=cfg.y_profile_sigma)

        # Find valley (minimum variance = wound band center)
        y_center = int(np.argmin(y_smooth))

        # Threshold for low-variance region
        threshold = np.percentile(y_smooth, cfg.y_band_percentile)
        below_thresh = y_smooth < threshold

        # Find contiguous region around center
        y_indices = np.where(below_thresh)[0]
        if len(y_indices) == 0:
            # Fallback: middle third
            return H // 3, 2 * H // 3, H // 2

        # Find contiguous segment containing y_center
        y_min, y_max = self._find_contiguous_around(y_indices, y_center, H)

        # Expand by margin
        band_height = y_max - y_min
        margin = int(band_height * cfg.y_margin)
        y_min = max(0, y_min - margin)
        y_max = min(H - 1, y_max + margin)

        return y_min, y_max, y_center

    def _find_contiguous_around(
        self,
        indices: np.ndarray,
        center: int,
        max_val: int
    ) -> Tuple[int, int]:
        """
        Find the contiguous segment of sorted *indices* that contains
        *center*.

        Splits *indices* at gaps (differences > 1) into contiguous
        segments, then returns the one that encloses *center*.  If no
        segment contains *center*, the closest segment is returned.

        Parameters
        ----------
        indices : np.ndarray
            1-D sorted array of integer row indices that satisfy some
            threshold condition.
        center : int
            The target row index (wound centre) that should lie inside the
            returned segment.
        max_val : int
            Image height, used as fallback upper bound when *indices* is
            empty.

        Returns
        -------
        seg_min : int
            First row index of the selected contiguous segment.
        seg_max : int
            Last row index of the selected contiguous segment.
        """
        if len(indices) == 0:
            return 0, max_val - 1

        # Find which segment contains center
        diffs = np.diff(indices)
        breaks = np.where(diffs > 1)[0]

        segments = []
        start = 0
        for b in breaks:
            segments.append((indices[start], indices[b]))
            start = b + 1
        segments.append((indices[start], indices[-1]))

        # Find segment containing center
        for seg_min, seg_max in segments:
            if seg_min <= center <= seg_max:
                return seg_min, seg_max

        # Fallback: closest segment
        dists = [min(abs(center - s[0]), abs(center - s[1])) for s in segments]
        best_idx = np.argmin(dists)
        return segments[best_idx]

    # =========================================================================
    # STAGE 3: Column-wise Edge Extraction (vectorized)
    # =========================================================================

    def _extract_edges_per_column(
        self,
        variance_map: np.ndarray,
        y_min: int,
        y_max: int,
        y_center: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract upper and lower wound edges for every image column.

        The strategy searches from the Y-band boundaries **inward** toward
        the wound centre, looking for the first row where the variance
        drops below a threshold derived from the cell regions (the areas
        above ``y_min`` and below ``y_max``).

        This implementation is fully vectorized using NumPy broadcasting
        and avoids any Python-level ``for`` loop over columns.

        Parameters
        ----------
        variance_map : np.ndarray
            Smoothed 2-D variance map of shape ``(H, W)``.
        y_min : int
            Top of the detected Y-band.
        y_max : int
            Bottom of the detected Y-band.
        y_center : int
            Approximate wound centre row.

        Returns
        -------
        upper_edge : np.ndarray
            1-D float64 array of length *W* giving the upper (top) wound
            edge row for each column.  Columns where no transition is
            found default to *y_center*.
        lower_edge : np.ndarray
            1-D float64 array of length *W* giving the lower (bottom)
            wound edge row for each column.  Columns where no transition
            is found default to *y_center*.
        """
        cfg = self.config
        H, W = variance_map.shape

        # Compute threshold from cell regions
        cell_region_top = variance_map[:max(1, y_min), :]
        cell_region_bot = variance_map[min(H - 1, y_max):, :]
        cell_variance = np.concatenate([cell_region_top.ravel(), cell_region_bot.ravel()])

        if len(cell_variance) > 0:
            cell_median = np.median(cell_variance)
            threshold = cell_median * 0.5
        else:
            threshold = np.percentile(variance_map, cfg.edge_threshold_percentile)

        # Vectorized upper edge: search downward from y_min toward y_center
        region_upper = variance_map[y_min:y_center + 1, :]  # shape (y_center-y_min+1, W)
        below_thresh_upper = region_upper < threshold
        has_transition_upper = below_thresh_upper.any(axis=0)  # shape (W,)
        first_below_upper = np.argmax(below_thresh_upper, axis=0)  # first True per column
        upper_edge = np.where(has_transition_upper, y_min + first_below_upper, y_center).astype(np.float64)

        # Vectorized lower edge: search upward from y_max toward y_center
        region_lower = variance_map[y_center:y_max + 1, :]  # shape (y_max-y_center+1, W)
        below_thresh_lower = region_lower < threshold
        # Flip vertically to find LAST below-threshold row (searching from bottom)
        below_thresh_lower_flipped = below_thresh_lower[::-1, :]
        has_transition_lower = below_thresh_lower_flipped.any(axis=0)
        last_below_lower = np.argmax(below_thresh_lower_flipped, axis=0)
        lower_edge = np.where(has_transition_lower, y_max - last_below_lower, y_center).astype(np.float64)

        return upper_edge, lower_edge

    # =========================================================================
    # STAGE 4: RANSAC Outlier Rejection
    # =========================================================================

    def _ransac_smooth_edges(
        self,
        upper_raw: np.ndarray,
        lower_raw: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply RANSAC-style outlier rejection to both wound edges.

        Each edge is processed independently by
        :meth:`_ransac_single_edge`, which iteratively fits a polynomial
        and replaces outlier points that deviate more than
        ``config.ransac_max_deviation`` pixels from the fit.

        Parameters
        ----------
        upper_raw : np.ndarray
            1-D array of raw upper-edge row positions (length *W*).
        lower_raw : np.ndarray
            1-D array of raw lower-edge row positions (length *W*).

        Returns
        -------
        upper_clean : np.ndarray
            Outlier-cleaned upper edge.
        lower_clean : np.ndarray
            Outlier-cleaned lower edge.
        """
        cfg = self.config

        upper_clean = self._ransac_single_edge(upper_raw)
        lower_clean = self._ransac_single_edge(lower_raw)

        return upper_clean, lower_clean

    def _ransac_single_edge(self, edge: np.ndarray) -> np.ndarray:
        """
        RANSAC-style iterative outlier rejection for a single edge.

        At each iteration a polynomial of degree
        ``config.ransac_poly_degree`` is fitted to the valid edge points.
        Points deviating from the fit by more than
        ``config.ransac_max_deviation`` pixels are replaced with fitted
        values.  The process repeats for
        ``config.ransac_iterations`` rounds.

        Parameters
        ----------
        edge : np.ndarray
            1-D float array of per-column edge positions (may contain
            ``NaN`` for invalid columns).

        Returns
        -------
        np.ndarray
            Copy of *edge* with outlier values replaced by polynomial
            predictions.  Unchanged if fewer than 10 valid points exist.
        """
        cfg = self.config
        x = np.arange(len(edge))
        valid = ~np.isnan(edge)

        if valid.sum() < 10:
            return edge.copy()

        edge_clean = edge.copy()

        for _ in range(cfg.ransac_iterations):
            x_valid = x[valid & ~np.isnan(edge_clean)]
            y_valid = edge_clean[valid & ~np.isnan(edge_clean)]

            if len(x_valid) < 5:
                break

            # Fit polynomial
            try:
                poly = np.polyfit(x_valid, y_valid, deg=cfg.ransac_poly_degree)
                fitted = np.polyval(poly, x)

                # Find outliers
                residuals = np.abs(edge_clean - fitted)
                outliers = residuals > cfg.ransac_max_deviation

                # Replace outliers with fitted values
                edge_clean[outliers & valid] = fitted[outliers & valid]
            except (np.linalg.LinAlgError, ValueError):
                break

        return edge_clean

    # =========================================================================
    # STAGE 5: Savgol Smoothing
    # =========================================================================

    def _savgol_smooth(self, edge: np.ndarray) -> np.ndarray:
        """
        Apply Savitzky-Golay smoothing to an edge array.

        ``NaN`` values are first filled by linear interpolation so that
        the Savgol filter receives a contiguous signal.  The filter
        window is clamped to the array length and forced to be odd.

        Parameters
        ----------
        edge : np.ndarray
            1-D float array of per-column edge positions (may contain
            ``NaN`` entries).

        Returns
        -------
        np.ndarray
            Smoothed edge array of the same length.  If too few valid
            points exist (fewer than ``config.smoothing_window``), the
            input is returned unchanged.
        """
        cfg = self.config

        # Handle NaNs by interpolation first
        x = np.arange(len(edge))
        valid = ~np.isnan(edge)

        if valid.sum() < cfg.smoothing_window:
            return edge

        edge_interp = np.interp(x, x[valid], edge[valid])

        # Apply savgol filter
        window = min(cfg.smoothing_window, len(edge_interp))
        if window % 2 == 0:
            window -= 1

        edge_smooth = savgol_filter(
            edge_interp,
            window,
            cfg.smoothing_polyorder
        )

        return edge_smooth

    # =========================================================================
    # STAGE 6: Create Mask (vectorized)
    # =========================================================================

    def _edges_to_mask(
        self,
        upper: np.ndarray,
        lower: np.ndarray,
        H: int,
        W: int,
    ) -> np.ndarray:
        """
        Convert upper and lower edge arrays into a 2-D binary mask.

        Uses NumPy broadcasting to create the mask in a single vectorized
        operation, avoiding any Python-level loop over columns.

        Parameters
        ----------
        upper : np.ndarray
            1-D float array of length *W* with upper-edge row positions.
        lower : np.ndarray
            1-D float array of length *W* with lower-edge row positions.
        H : int
            Image height (number of rows).
        W : int
            Image width (number of columns).

        Returns
        -------
        np.ndarray
            Binary mask of shape ``(H, W)`` with dtype ``uint8``.
            Pixels between ``upper[x]`` and ``lower[x]`` (inclusive) are
            set to 1; all others are 0.
        """
        y_up = np.clip(upper.astype(int), 0, H - 1)
        y_lo = np.clip(lower.astype(int), 0, H - 1)
        rows = np.arange(H)[:, None]  # (H, 1)
        mask = ((rows >= y_up[None, :]) & (rows <= y_lo[None, :])).astype(np.uint8)
        return mask

    # =========================================================================
    # STAGE 7: Geometric Validation
    # =========================================================================

    def _validate_wound_geometry(self, mask: np.ndarray) -> Dict:
        """
        Validate that the detected wound has the expected horizontal-band
        geometry.

        Four criteria are checked:

        1. **Width coverage** -- the wound must span at least
           ``config.min_width_coverage`` of the image width.
        2. **Aspect ratio** -- bounding-box width / height must exceed
           ``config.min_aspect_ratio``.
        3. **Y-position** -- the mean Y of wound pixels must lie within
           ``config.y_center_range``.
        4. **Thickness consistency** -- the coefficient of variation of
           per-column wound thickness must be below
           ``config.max_thickness_cv``.

        Parameters
        ----------
        mask : np.ndarray
            Binary wound mask of shape ``(H, W)`` with dtype ``uint8``.

        Returns
        -------
        dict
            Dictionary with keys:

            - ``'valid'`` (bool): *True* if all four criteria pass.
            - ``'reason'`` (str): ``'valid'`` or a concatenation of failure
              tags.
            - ``'width_ratio'`` (float): fraction of columns with wound.
            - ``'aspect_ratio'`` (float): bounding-box aspect ratio.
            - ``'y_center_ratio'`` (float): mean wound Y normalised to
              [0, 1].
            - ``'thickness_cv'`` (float): coefficient of variation of
              per-column thickness.
        """
        cfg = self.config
        H, W = mask.shape

        y_indices, x_indices = np.where(mask)

        if len(y_indices) == 0:
            return {
                "valid": False,
                "reason": "empty_mask",
                "width_ratio": 0,
                "aspect_ratio": 0,
                "y_center_ratio": 0.5,
                "thickness_cv": 1.0,
            }

        # 1. Width coverage
        x_coverage = mask.sum(axis=0) > 0
        width_ratio = x_coverage.sum() / W

        # 2. Aspect ratio
        bbox_height = y_indices.max() - y_indices.min() + 1
        bbox_width = x_indices.max() - x_indices.min() + 1
        aspect = bbox_width / (bbox_height + 1e-6)

        # 3. Y-position
        y_center = y_indices.mean() / H
        in_middle = cfg.y_center_range[0] < y_center < cfg.y_center_range[1]

        # 4. Thickness consistency
        thickness_per_col = mask.sum(axis=0)
        thickness_per_col = thickness_per_col[thickness_per_col > 0]
        if len(thickness_per_col) > 0:
            thickness_cv = thickness_per_col.std() / (thickness_per_col.mean() + 1e-6)
        else:
            thickness_cv = 1.0

        # Combined validation
        valid = (
            width_ratio > cfg.min_width_coverage and
            aspect > cfg.min_aspect_ratio and
            in_middle and
            thickness_cv < cfg.max_thickness_cv
        )

        reason = "valid" if valid else self._get_failure_reason(
            width_ratio, aspect, y_center, thickness_cv
        )

        return {
            "valid": valid,
            "reason": reason,
            "width_ratio": float(width_ratio),
            "aspect_ratio": float(aspect),
            "y_center_ratio": float(y_center),
            "thickness_cv": float(thickness_cv),
        }

    def _get_failure_reason(
        self,
        width_ratio: float,
        aspect: float,
        y_center: float,
        thickness_cv: float
    ) -> str:
        """
        Determine the primary reason(s) why geometric validation failed.

        Compares each metric against its configured threshold and returns
        a human-readable tag string (underscore-separated if multiple
        criteria fail).

        Parameters
        ----------
        width_ratio : float
            Fraction of image columns covered by the wound mask.
        aspect : float
            Bounding-box width-to-height aspect ratio of the wound.
        y_center : float
            Normalised vertical centre of the wound (0 = top, 1 = bottom).
        thickness_cv : float
            Coefficient of variation of per-column wound thickness.

        Returns
        -------
        str
            Underscore-joined failure tags, e.g.
            ``'width_0.45_thickness_cv_0.72'``, or ``'unknown'`` if no
            specific reason could be identified.
        """
        cfg = self.config
        reasons = []
        if width_ratio < cfg.min_width_coverage:
            reasons.append(f"width_{width_ratio:.2f}")
        if aspect < cfg.min_aspect_ratio:
            reasons.append(f"aspect_{aspect:.2f}")
        if not (cfg.y_center_range[0] < y_center < cfg.y_center_range[1]):
            reasons.append(f"y_pos_{y_center:.2f}")
        if thickness_cv > cfg.max_thickness_cv:
            reasons.append(f"thickness_cv_{thickness_cv:.2f}")
        return "_".join(reasons) if reasons else "unknown"

    # =========================================================================
    # FALLBACK: Constrained Region Growing
    # =========================================================================

    def _fallback_detection(
        self,
        img: np.ndarray,
        variance_map: np.ndarray,
        y_center: int,
        primary_result: WoundResult,
    ) -> WoundResult:
        """
        Fallback detection using constrained region growing.

        Activated when the primary pipeline's geometric validation fails.
        A thin horizontal seed is placed at *y_center* and expanded only
        into low-variance pixels (below the 25th percentile of the
        variance map).  Morphological cleaning, hole filling, and
        connected-component analysis are applied to produce a clean mask.

        Parameters
        ----------
        img : np.ndarray
            2-D float image (normalised to [0, 1]).
        variance_map : np.ndarray
            Smoothed 2-D variance map of the same shape as *img*.
        y_center : int
            Row index of the estimated wound centre.
        primary_result : WoundResult
            Result from the primary pipeline, used to carry over the
            ``y_band`` field.

        Returns
        -------
        WoundResult
            New result with ``method='fallback'``, containing the
            region-grown mask and edges extracted from it.
        """
        H, W = img.shape

        # Use a more conservative approach:
        # Start with a thin horizontal line at y_center and expand

        # Threshold map (low variance = wound)
        threshold = np.percentile(variance_map, 25)
        low_var_mask = variance_map < threshold

        # Seed: horizontal band around y_center
        seed_half = 5
        seed_mask = np.zeros((H, W), dtype=bool)
        seed_mask[max(0, y_center - seed_half):min(H, y_center + seed_half + 1), :] = True

        # Grow only where low variance
        grown = seed_mask & low_var_mask

        # Fill holes and clean
        grown = remove_small_holes(grown, area_threshold=500)
        grown = remove_small_objects(grown, min_size=1000)
        grown = closing(grown, disk(5))

        # Keep only largest connected component
        labeled = label(grown)  # Returns 2D array directly, not tuple
        props = regionprops(labeled)
        if props:
            largest = max(props, key=lambda r: r.area)
            grown = (labeled == largest.label)

        mask = grown.astype(np.uint8)

        # Extract edges from mask
        upper_edge, lower_edge = self._mask_to_edges(mask)

        # Validate
        qc = self._validate_wound_geometry(mask)

        return WoundResult(
            mask=mask,
            upper_edge=upper_edge,
            lower_edge=lower_edge,
            y_center=y_center,
            y_band=primary_result.y_band,
            qc=qc,
            method="fallback",
        )

    def _mask_to_edges(self, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract upper and lower wound edges from a binary mask.

        For each column the first and last nonzero row are identified
        using vectorized ``np.argmax`` on the boolean mask and its
        vertical flip, avoiding any Python-level loop.

        Parameters
        ----------
        mask : np.ndarray
            Binary wound mask of shape ``(H, W)`` with dtype ``uint8``
            or ``bool``.

        Returns
        -------
        upper : np.ndarray
            1-D float array of length *W*.  ``upper[x]`` is the topmost
            wound row in column *x*, or ``NaN`` if the column has no
            wound pixels.
        lower : np.ndarray
            1-D float array of length *W*.  ``lower[x]`` is the
            bottommost wound row in column *x*, or ``NaN`` if the column
            has no wound pixels.
        """
        H, W = mask.shape
        has_wound = mask.any(axis=0)  # (W,)
        upper = np.full(W, np.nan)
        lower = np.full(W, np.nan)
        # argmax on bool gives first True; for last, flip and subtract
        upper[has_wound] = np.argmax(mask[:, has_wound], axis=0)
        lower[has_wound] = H - 1 - np.argmax(mask[::-1, has_wound], axis=0)
        return upper, lower

    # =========================================================================
    # DEBUG VISUALIZATION
    # =========================================================================

    def _debug_plot(
        self,
        img: np.ndarray,
        variance_map: np.ndarray,
        upper_raw: np.ndarray,
        lower_raw: np.ndarray,
        upper_smooth: np.ndarray,
        lower_smooth: np.ndarray,
        mask: np.ndarray,
        result: WoundResult,
        save_path: Optional[Path],
    ):
        """
        Create a six-panel debug visualisation of the detection pipeline.

        Panels
        ------
        1. Original grayscale image.
        2. Variance map with Y-band and centre overlaid.
        3. Row-averaged variance profile with band/centre annotations.
        4. Raw per-column edges overlaid on the image.
        5. Smoothed (RANSAC + Savgol) edges with filled wound region.
        6. Final mask overlay with QC pass/fail status.

        Parameters
        ----------
        img : np.ndarray
            Normalised 2-D grayscale image.
        variance_map : np.ndarray
            Smoothed variance map.
        upper_raw : np.ndarray
            Raw upper-edge positions.
        lower_raw : np.ndarray
            Raw lower-edge positions.
        upper_smooth : np.ndarray
            Smoothed upper-edge positions.
        lower_smooth : np.ndarray
            Smoothed lower-edge positions.
        mask : np.ndarray
            Final binary wound mask.
        result : WoundResult
            Detection result (used for QC info and method tag).
        save_path : pathlib.Path or None
            If not *None*, the figure is saved here and closed;
            otherwise ``plt.show()`` is called.
        """
        H, W = img.shape

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))

        # 1. Original image
        ax = axes[0, 0]
        ax.imshow(img, cmap="gray")
        ax.set_title("Original Image")
        ax.axis("off")

        # 2. Variance map
        ax = axes[0, 1]
        ax.imshow(variance_map, cmap="viridis")
        ax.axhline(result.y_band[0], color="r", linestyle="--", linewidth=1)
        ax.axhline(result.y_band[1], color="r", linestyle="--", linewidth=1)
        ax.axhline(result.y_center, color="cyan", linewidth=2)
        ax.set_title(f"Variance Map (Y-band: {result.y_band[0]}-{result.y_band[1]})")
        ax.axis("off")

        # 3. Y-profile
        ax = axes[0, 2]
        y_profile = variance_map.mean(axis=1)
        ax.plot(y_profile, np.arange(len(y_profile)), "b-", linewidth=1.5)
        ax.axhline(result.y_center, color="cyan", linewidth=2, label="Y center")
        ax.axhspan(result.y_band[0], result.y_band[1], alpha=0.2, color="red", label="Y band")
        ax.invert_yaxis()
        ax.set_xlabel("Mean Variance")
        ax.set_ylabel("Y (row)")
        ax.set_title("Y-Profile")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

        # 4. Raw edges
        ax = axes[1, 0]
        ax.imshow(img, cmap="gray", alpha=0.7)
        x = np.arange(W)
        ax.plot(x, upper_raw, "r.", markersize=1, label="Upper (raw)")
        ax.plot(x, lower_raw, "b.", markersize=1, label="Lower (raw)")
        ax.set_title("Raw Edges (per column)")
        ax.legend(fontsize=8)
        ax.axis("off")

        # 5. Smoothed edges
        ax = axes[1, 1]
        ax.imshow(img, cmap="gray", alpha=0.7)
        ax.plot(x, upper_smooth, "r-", linewidth=2, label="Upper (smooth)")
        ax.plot(x, lower_smooth, "b-", linewidth=2, label="Lower (smooth)")
        ax.fill_between(x, upper_smooth, lower_smooth, color="orange", alpha=0.3)
        ax.set_title("Smoothed Edges (RANSAC + Savgol)")
        ax.legend(fontsize=8)
        ax.axis("off")

        # 6. Final mask overlay
        ax = axes[1, 2]
        overlay = np.stack([img, img, img], axis=-1)
        overlay[mask > 0, 0] = np.minimum(overlay[mask > 0, 0] + 0.3, 1.0)
        overlay[mask > 0, 1] = overlay[mask > 0, 1] * 0.7
        overlay[mask > 0, 2] = overlay[mask > 0, 2] * 0.7
        ax.imshow(overlay)
        qc = result.qc
        status = "PASS" if qc["valid"] else f"FAIL: {qc['reason']}"
        ax.set_title(f"Final Mask ({result.method}) - {status}")
        ax.axis("off")

        # QC metrics
        fig.text(
            0.5, 0.02,
            f"QC: width={qc['width_ratio']:.2f} | aspect={qc['aspect_ratio']:.1f} | "
            f"y_pos={qc['y_center_ratio']:.2f} | thick_cv={qc['thickness_cv']:.2f}",
            ha="center", fontsize=10, style="italic"
        )

        plt.tight_layout(rect=[0, 0.04, 1, 1])

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()


# =============================================================================
# Main entry point
# =============================================================================

def detect_wound(
    img: np.ndarray,
    config: Optional[WoundDetectorConfig] = None,
    debug: bool = False,
    save_path: Optional[Path] = None,
) -> WoundResult:
    """
    Convenience function for wound detection.

    Creates a :class:`WoundDetector` instance and runs
    :meth:`WoundDetector.detect` in a single call.

    Parameters
    ----------
    img : np.ndarray
        Grayscale image (H, W), ``uint8`` or ``float``.
    config : WoundDetectorConfig or None, optional
        Optional custom configuration.  When *None*, defaults are used.
    debug : bool, optional
        Show debug visualisation.  Default is *False*.
    save_path : pathlib.Path or None, optional
        Save debug figure to this path instead of displaying.

    Returns
    -------
    WoundResult
        Detection result with mask, edges, and QC metrics.

    Examples
    --------
    >>> from library.wound_standard.detector import detect_wound
    >>> import cv2
    >>> img = cv2.imread("sample.jpg", cv2.IMREAD_GRAYSCALE)
    >>> result = detect_wound(img, debug=True)
    >>> print(result.qc)
    """
    detector = WoundDetector(config)
    return detector.detect(img, debug=debug, save_path=save_path)


if __name__ == "__main__":
    from config.config import sample_img
    import cv2

    # Load sample image
    img = cv2.imread(sample_img, cv2.IMREAD_GRAYSCALE)

    # Detect wound
    result = detect_wound(img, debug=True)

    print(f"Method: {result.method}")
    print(f"QC: {result.qc}")
    print(f"Wound area: {result.mask.sum()} pixels")
