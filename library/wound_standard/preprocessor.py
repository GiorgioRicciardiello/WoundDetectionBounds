"""
Preprocessing Pipeline for Standard Wound Detection
====================================================

Converts raw grayscale microscopy images into binary wound masks via
gradient-based cell-body extraction and morphological filtering.

Pipeline
--------
1. Normalize intensity to [0, 1]
2. Gaussian smoothing (sigma=1.2) to reduce sensor noise
3. Sobel gradient to highlight cell edges (high gradient = cells)
4. Percentile thresholding on gradient to create cell-body mask
5. Morphological cleanup (close/open) to fill gaps in cell regions
6. Connected-component filtering (keep largest N components)
7. Hole filling and boundary smoothing
8. Contour scoring to select the most rectangle-like wound region
"""

from typing import Union, Tuple, Optional

from skimage.filters import gaussian, sobel
from skimage.morphology import remove_small_objects, remove_small_holes, closing, disk
from skimage.measure import label, regionprops
import numpy as np
import cv2
from pathlib import Path


def pre_processing(
    img: Union[np.ndarray, Path],
    verbose: Optional[bool] = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Preprocess a microscopy image into a binary wound mask.

    Parameters
    ----------
    img : np.ndarray | Path
        Grayscale image as a 2-D ``uint8`` array or a file path.
    verbose : bool, optional
        Reserved for future debug output.  Currently unused after
        removing inline visualization coupling.

    Returns
    -------
    img_raw : np.ndarray
        Original grayscale image (loaded from disk if *img* was a path).
    wound_mask : np.ndarray
        Binary wound mask, shape ``(H, W)``, dtype ``uint8``.
        ``1`` = wound, ``0`` = cell / background.

    Notes
    -----
    The wound is identified *indirectly*: cells have high Sobel gradient
    (many edges), so we first find the cell-body regions, then invert to
    get the wound.
    """
    if isinstance(img, Path):
        img = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE)

    img_f = img.astype(np.float32) / 255.0
    img_s = gaussian(img_f, sigma=1.2)
    grad = sobel(img_s)
    grad_n = (grad - grad.min()) / (grad.max() - grad.min() + 1e-6)

    cell_body = _get_cell_body_mask(grad_n=grad_n, thresh_quantile=70)
    img_cell_mask = _pp_clean_cell_body(cell_mask=cell_body, keep_components=2)

    return img, img_cell_mask


def _get_cell_body_mask(
    grad_n: np.ndarray,
    thresh_quantile: int = 70,
) -> np.ndarray:
    """Create a binary mask of dense cell-body regions.

    High-gradient pixels (cell edges) are thresholded and cleaned
    with morphological close/open to produce solid cell regions.

    Parameters
    ----------
    grad_n : np.ndarray
        Normalized Sobel gradient, shape ``(H, W)``, range [0, 1].
    thresh_quantile : int
        Percentile of the gradient distribution above which pixels
        are classified as cell body.

    Returns
    -------
    mask : np.ndarray
        Binary cell-body mask, dtype ``uint8``.
    """
    thresh = np.percentile(grad_n, thresh_quantile)
    cell_mask = grad_n > thresh

    cell_mask = cell_mask.astype(np.uint8)
    cell_mask = cv2.morphologyEx(
        cell_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)
    )
    cell_mask = cv2.morphologyEx(
        cell_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)
    )

    return cell_mask


def _pp_clean_cell_body(
    cell_mask: np.ndarray,
    keep_components: int = 2,
) -> np.ndarray:
    """Clean the cell-body mask and extract wound contour.

    Steps:
    1. Remove small objects (< 800 px)
    2. Keep the *keep_components* largest connected components
    3. Fill internal holes (< 5000 px)
    4. Morphological closing with disk(7)
    5. Invert and score contours for rectangle-likeness

    Parameters
    ----------
    cell_mask : np.ndarray
        Raw binary cell-body mask.
    keep_components : int
        Number of largest connected components to retain.

    Returns
    -------
    wound_mask : np.ndarray
        Binary wound mask, dtype ``uint8``.
    """
    mask = cell_mask.astype(bool)
    mask = remove_small_objects(mask, min_size=800)

    labeled = label(mask)
    if isinstance(labeled, tuple):
        labeled = labeled[0]
    props = regionprops(labeled)

    if len(props) == 0:
        raise ValueError("No connected components found in cell mask!")

    props_sorted = sorted(props, key=lambda r: r.area, reverse=True)
    allowed_labels = {p.label for p in props_sorted[:keep_components]}
    largest_only = np.isin(labeled, list(allowed_labels))

    largest_only = remove_small_holes(largest_only, area_threshold=5000)
    largest_only = closing(largest_only, disk(7))
    largest_only = largest_only.astype(np.uint8)

    clean_wound_mask = _pp_contour_filtering(mask_closed=largest_only)

    return clean_wound_mask


def _pp_contour_filtering(mask_closed: np.ndarray) -> np.ndarray:
    """Select the most rectangle-like horizontal contour from the inverted cell mask.

    Scoring formula per contour::

        score = horizontal_extent / W * fill_ratio * 1 / (1 + vertex_penalty)

    where *horizontal_extent* is normalized by image width to prevent
    it from dominating the other terms.

    Parameters
    ----------
    mask_closed : np.ndarray
        Cleaned cell-body mask (cells = 1, background = 0).

    Returns
    -------
    wound_mask : np.ndarray
        Binary wound mask, dtype ``uint8``.
    """
    mask_closed = 1 - mask_closed
    H, W = mask_closed.shape
    mask_u8 = mask_closed.astype(np.uint8)

    contours, _ = cv2.findContours(
        mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return mask_u8

    best_cnt = None
    best_score = -np.inf

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area == 0:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        bbox_area = w * h
        fill_ratio = area / bbox_area

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        vertex_penalty = abs(len(approx) - 4)

        # Normalized horizontal extent to prevent width-dominance
        horizontal_extent_norm = w / W

        score = (
            horizontal_extent_norm
            * fill_ratio
            * (1 / (1 + vertex_penalty))
        )

        if score > best_score:
            best_score = score
            best_cnt = cnt

    clean = np.zeros_like(mask_u8)
    if best_cnt is not None:
        cv2.drawContours(clean, [best_cnt], -1, 1, thickness=-1)

    return clean.astype(np.uint8)


def _pp_constrains_horizontal_centered_wounds(
    clean_wound_mask: np.ndarray,
    max_recursions: int = 2,
    thickness_jump_factor: float = 2.5,
    smooth_window: int = 31,
) -> np.ndarray:
    """Remove divergent tails by enforcing envelope continuity.

    Iteratively prunes wound-mask pixels that violate the local
    smoothed envelope.  Boundaries are derived solely from the mask
    (no external priors).

    Parameters
    ----------
    clean_wound_mask : np.ndarray
        Binary wound mask, dtype ``uint8``.
    max_recursions : int
        Maximum prune-and-recompute iterations.
    thickness_jump_factor : float
        Columns thicker than ``factor * median_thickness`` are pruned.
    smooth_window : int
        Moving-average kernel width for envelope smoothing.

    Returns
    -------
    mask : np.ndarray
        Refined wound mask, dtype ``uint8``.
    """
    mask = clean_wound_mask.astype(bool)
    H, W = mask.shape

    for _ in range(max_recursions):
        xs = np.arange(W)

        top = np.full(W, np.nan)
        bottom = np.full(W, np.nan)

        for x in xs:
            ys = np.where(mask[:, x])[0]
            if len(ys) > 0:
                top[x] = ys.min()
                bottom[x] = ys.max()

        valid = ~np.isnan(top)
        if valid.sum() < W * 0.3:
            break

        thickness = bottom - top

        def smooth(arr: np.ndarray) -> np.ndarray:
            out = arr.copy()
            idx = np.where(~np.isnan(arr))[0]
            out[idx] = np.convolve(
                arr[idx],
                np.ones(smooth_window) / smooth_window,
                mode="same",
            )
            return out

        top_s = smooth(top)
        bottom_s = smooth(bottom)
        thickness_s = bottom_s - top_s

        ref_thickness = np.nanmedian(thickness_s)
        if ref_thickness <= 0:
            break

        new_mask = mask.copy()
        ys, xs_pix = np.where(mask)

        for y, x in zip(ys, xs_pix):
            if not valid[x]:
                continue
            if (
                y < top_s[x] - 0.15 * ref_thickness
                or y > bottom_s[x] + 0.15 * ref_thickness
                or thickness[x] > thickness_jump_factor * ref_thickness
            ):
                new_mask[y, x] = False

        if np.array_equal(mask, new_mask):
            break

        mask = new_mask

    return mask.astype(np.uint8)
