"""
Stateful Wound Segmenter (Standard Model)
==========================================

Provides :class:`WoundSegmenter`, a frame-by-frame tracker that applies
temporal constraints to ensure monotonic wound closure.

The segmenter stores the previous frame's upper/lower boundary vectors
and intersects them with the current detection so that the wound can
only shrink (or stay the same) over time.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import cv2
import numpy as np

from library.wound_standard.preprocessor import pre_processing


class WoundSegmenter:
    """Stateful wound tracker with monotonic-closure constraint.

    On each call to :meth:`segment`, the raw image is preprocessed into
    a binary mask, then intersected column-wise with the previous frame's
    boundary to enforce ``A(t+1) <= A(t)``.

    Parameters
    ----------
    y_upper_prev : np.ndarray | None
        Initial upper boundary from a prior run (shape ``(W,)``).
    y_lower_prev : np.ndarray | None
        Initial lower boundary from a prior run (shape ``(W,)``).
    constrain : bool
        If ``True`` the temporal constraint is applied from the first
        frame onward.
    """

    def __init__(
        self,
        y_upper_prev: Optional[np.ndarray] = None,
        y_lower_prev: Optional[np.ndarray] = None,
        constrain: bool = False,
    ) -> None:
        self.bounds = (y_upper_prev, y_lower_prev)
        self.constrain = constrain
        self._result_prev: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def segment(
        self,
        img_raw: Union[np.ndarray, Path],
        verbose: bool = True,
        time: Optional[int] = None,
        path_out: Optional[Path] = None,
    ) -> Dict[str, Union[np.ndarray, float]]:
        """Segment wound with shape-preserving temporal constraints.

        Processing steps:
        1. Preprocess raw image into a binary mask.
        2. Apply previous bounds as a hard column-wise constraint.
        3. Extract wound contour and per-column boundaries.
        4. Store new bounds for the next frame.

        Parameters
        ----------
        img_raw : np.ndarray | Path
            Grayscale image or path to image file.
        verbose : bool
            Reserved (previously controlled inline plotting).
        time : int | None
            Frame index, used for metadata only.
        path_out : Path | None
            Reserved for caller-side visualization.

        Returns
        -------
        result : dict
            Keys: ``img_raw``, ``mask``, ``area``, ``y_upper``,
            ``y_lower``, ``overlay``.
        """
        img_raw, img_pp = pre_processing(img=img_raw)

        wound_mask, y_upper, y_lower = self._apply_support_constraint(
            mask=img_pp,
            y_upper_prev=self._y_upper_prev,
            y_lower_prev=self._y_lower_prev,
        )

        try:
            contour, _, _, area = self._extract_wound_contours_and_bounds(
                wound_mask
            )
            self.bounds = (y_upper, y_lower)
            overlay = _draw_wound_overlay(img_raw, contour, area)

            result = {
                "img_raw": img_raw,
                "mask": wound_mask,
                "area": area,
                "y_upper": y_upper,
                "y_lower": y_lower,
                "overlay": overlay,
            }
            self.result = result

        except ValueError:
            if self._result_prev is None:
                raise RuntimeError(
                    "No wound contour found and no previous result available."
                )
            result = self._result_prev

        return result

    def reset(self) -> None:
        """Clear all internal state for a new trajectory."""
        self._y_upper_prev = None
        self._y_lower_prev = None
        self._result_prev = None

    # ------------------------------------------------------------------
    # Constraint logic
    # ------------------------------------------------------------------

    def _apply_support_constraint(
        self,
        mask: np.ndarray,
        y_upper_prev: Optional[np.ndarray] = None,
        y_lower_prev: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Column-wise intersection of current mask with previous bounds.

        For each column *x*:

        .. math::

            S_{\\text{eff}}(x) = S_{\\text{curr}}(x) \\cap
            [y_{\\text{upper\\_prev}}(x),\\; y_{\\text{lower\\_prev}}(x)]

        Parameters
        ----------
        mask : np.ndarray
            Current binary wound mask, shape ``(H, W)``.
        y_upper_prev, y_lower_prev : np.ndarray | None
            Previous frame's boundary vectors, shape ``(W,)``.

        Returns
        -------
        constrained : np.ndarray
            Constrained wound mask.
        y_upper_eff : np.ndarray
            Effective upper boundary.
        y_lower_eff : np.ndarray
            Effective lower boundary.
        """
        H, W = mask.shape
        constrained = np.zeros_like(mask, dtype=np.uint8)
        y_upper_eff = np.full(W, np.nan, dtype=np.float32)
        y_lower_eff = np.full(W, np.nan, dtype=np.float32)

        has_wound = mask.any(axis=0)  # (W,)

        if not has_wound.any():
            return constrained, y_upper_eff, y_lower_eff

        # Current top/bottom per column (vectorized)
        y_curr_top = np.argmax(mask > 0, axis=0).astype(np.float32)
        # For bottom: flip and argmax
        y_curr_bot = (H - 1 - np.argmax((mask > 0)[::-1, :], axis=0)).astype(np.float32)
        # Mark columns with no wound
        y_curr_top[~has_wound] = np.nan
        y_curr_bot[~has_wound] = np.nan

        if y_upper_prev is not None and y_lower_prev is not None:
            prev_valid = ~(np.isnan(y_upper_prev) | np.isnan(y_lower_prev))
            both_valid = has_wound & prev_valid

            y_eff_top = np.full(W, np.nan, dtype=np.float32)
            y_eff_bot = np.full(W, np.nan, dtype=np.float32)

            y_eff_top[both_valid] = np.maximum(
                y_curr_top[both_valid], y_upper_prev[both_valid]
            )
            y_eff_bot[both_valid] = np.minimum(
                y_curr_bot[both_valid], y_lower_prev[both_valid]
            )

            # First-frame-only columns (no previous)
            first_only = has_wound & ~prev_valid
            y_eff_top[first_only] = y_curr_top[first_only]
            y_eff_bot[first_only] = y_curr_bot[first_only]
        else:
            y_eff_top = y_curr_top.copy()
            y_eff_bot = y_curr_bot.copy()

        # Only keep columns where top < bottom
        valid_cols = (~np.isnan(y_eff_top)) & (y_eff_top < y_eff_bot)

        # Build constrained mask (vectorized)
        rows = np.arange(H)[:, None]  # (H, 1)
        in_range = (
            (rows >= y_eff_top[None, :]) & (rows <= y_eff_bot[None, :])
        )
        constrained = ((mask > 0) & in_range & valid_cols[None, :]).astype(np.uint8)

        y_upper_eff[valid_cols] = y_eff_top[valid_cols]
        y_lower_eff[valid_cols] = y_eff_bot[valid_cols]

        return constrained, y_upper_eff, y_lower_eff

    def _extract_wound_contours_and_bounds(
        self,
        wound_mask: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """Extract the largest wound contour and per-column boundaries.

        Parameters
        ----------
        wound_mask : np.ndarray
            Binary wound mask, shape ``(H, W)``.

        Returns
        -------
        contour : np.ndarray
            Largest contour, shape ``(N, 1, 2)``.
        y_top : np.ndarray
            Upper boundary per column, shape ``(W,)``.
        y_bottom : np.ndarray
            Lower boundary per column, shape ``(W,)``.
        area : int
            Wound area in pixels.

        Raises
        ------
        ValueError
            If no contour is found in *wound_mask*.
        """
        wound_u8 = (wound_mask > 0).astype(np.uint8)

        contours, _ = cv2.findContours(
            wound_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            raise ValueError("No wound contour found.")

        contour = max(contours, key=cv2.contourArea)
        area = int(cv2.contourArea(contour))

        # Vectorized per-column top/bottom
        H, W = wound_u8.shape
        has_wound = wound_u8.any(axis=0)
        y_top = np.full(W, np.nan, dtype=np.float32)
        y_bottom = np.full(W, np.nan, dtype=np.float32)
        y_top[has_wound] = np.argmax(wound_u8[:, has_wound], axis=0)
        y_bottom[has_wound] = H - 1 - np.argmax(wound_u8[::-1, has_wound], axis=0)

        return contour, y_top, y_bottom, area

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def bounds(self) -> Dict[str, Optional[np.ndarray]]:
        """Current boundary state: ``{'upper': ..., 'lower': ...}``."""
        return {"upper": self._y_upper_prev, "lower": self._y_lower_prev}

    @bounds.setter
    def bounds(self, value: Tuple[Optional[np.ndarray], Optional[np.ndarray]]) -> None:
        y_upper, y_lower = value
        self._y_upper_prev = y_upper.copy() if y_upper is not None else None
        self._y_lower_prev = y_lower.copy() if y_lower is not None else None

    @property
    def result(self) -> Optional[Dict]:
        """Last valid segmentation result."""
        return self._result_prev

    @result.setter
    def result(self, value: Optional[Dict]) -> None:
        if value is None:
            self._result_prev = None
            return
        self._result_prev = dict(value)


def _draw_wound_overlay(
    img_gray: np.ndarray,
    contour: np.ndarray,
    area: int,
    alpha: float = 0.6,
    color: Tuple[int, int, int] = (0, 150, 255),
) -> np.ndarray:
    """Draw filled wound contour overlay on a grayscale image.

    Parameters
    ----------
    img_gray : np.ndarray
        Grayscale input image.
    contour : np.ndarray
        Wound contour from ``cv2.findContours``.
    area : int
        Wound area in pixels (drawn as text annotation).
    alpha : float
        Blending factor.
    color : tuple
        BGR contour colour.

    Returns
    -------
    overlay : np.ndarray
        BGR image with wound overlay.
    """
    img_rgb = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
    overlay = img_rgb.copy()

    cv2.drawContours(overlay, [contour], contourIdx=-1, color=color, thickness=3)

    out = cv2.addWeighted(overlay, alpha, img_rgb, 1 - alpha, 0)

    text = f"Wound area: {area} px"
    cv2.putText(
        out, text, (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA,
    )

    return out
