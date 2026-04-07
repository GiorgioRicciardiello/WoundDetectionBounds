"""
Publication Figure Panels
=========================

Reusable panel-building functions for wound healing publication figures.
Each function accepts a pre-created Axes object, draws into it, and returns it.

Visual encoding (global, consistent across all figures):
- Color  → cell_line   (CELL_LINE_COLORS)
- Style  → condition   (CONDITION_LINESTYLE)
- Alpha  → condition   (CONDITION_ALPHA)

All functions are side-effect-free with respect to figure-level state.
"""

from typing import Dict, List, Optional, Tuple

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from scipy.ndimage import gaussian_filter, gaussian_filter1d

# ---------------------------------------------------------------------------
# Publication-wide style constants
# ---------------------------------------------------------------------------

PUBLICATION_FONT: str = "Arial"
PUBLICATION_DPI: int = 300

# Colorblind-safe palette (Wong 2011): cell line → hex color
CELL_LINE_COLORS: Dict[str, str] = {
    "Line 1": "#0072B2",   # Blue
    "Line 2": "#E69F00",   # Orange
}

# Ordered list of conditions (candesartan excluded from publication)
CONDITION_ORDER: List[str] = ["DMSO", "Media", "Alk5i"]

CONDITION_LINESTYLE: Dict[str, str] = {
    "DMSO":  "-",
    "Media": "--",
    "Alk5i": "-.",
}

CONDITION_ALPHA: Dict[str, float] = {
    "DMSO":  1.0,
    "Media": 0.75,
    "Alk5i": 0.55,
}


# Utility: blend a color with white for pastel highlights.
def _blend_with_white(
    rgb: Tuple[float, float, float],
    blend: float = 0.45,
) -> Tuple[float, float, float]:
    arr = np.clip(np.array(rgb, dtype=float), 0.0, 1.0)
    return tuple(np.clip(arr * (1.0 - blend) + np.ones_like(arr) * blend, 0.0, 1.0))

# Border overlay colors for timelapse (time progression: early → late)
_TIMELAPSE_CMAP = plt.get_cmap("magma")
_TIMELAPSE_PALETTE = _TIMELAPSE_CMAP(np.linspace(0.25, 0.85, 3))
_TIMELAPSE_BOUNDARY_COLORS: Dict[str, str] = {
    "t0":     mcolors.to_hex(_TIMELAPSE_PALETTE[0]),
    "tmid":   mcolors.to_hex(_TIMELAPSE_PALETTE[1]),
    "tfinal": mcolors.to_hex(_TIMELAPSE_PALETTE[2]),
}
_TIMELAPSE_FILL_COLORS: List[Tuple[float, float, float]] = [
    _blend_with_white(mcolors.to_rgb(_TIMELAPSE_BOUNDARY_COLORS["tmid"]), blend=0.55),
    _blend_with_white(mcolors.to_rgb(_TIMELAPSE_BOUNDARY_COLORS["tfinal"]), blend=0.55),
]
_TIMELAPSE_T0_HIGHLIGHT_COLOR = _blend_with_white(
    mcolors.to_rgb(_TIMELAPSE_BOUNDARY_COLORS["t0"]), blend=0.35
)
_TIMELAPSE_T0_HIGHLIGHT_ALPHA = 0.22

# --- Publication-grade wound overlay style (monochromatic) ---
WOUND_ACCENT_COLOR: str = "#1B3A5C"    # Deep navy for wound region fill
WOUND_BORDER_COLOR: str = "white"       # High-contrast edge border


# ---------------------------------------------------------------------------
# Utility: despine
# ---------------------------------------------------------------------------

def despine(
    ax: Axes,
    top: bool = True,
    right: bool = True,
    bottom: bool = False,
    left: bool = False,
) -> Axes:
    """
    Remove axis spines for a cleaner publication look.

    By default removes top and right spines, matching the convention
    in Nature, Science, and Cell journals.

    Parameters
    ----------
    ax : Axes
        Target axes.
    top, right, bottom, left : bool
        If True, remove the corresponding spine.

    Returns
    -------
    Axes
    """
    for spine, hide in [("top", top), ("right", right),
                        ("bottom", bottom), ("left", left)]:
        ax.spines[spine].set_visible(not hide)
    return ax


# ---------------------------------------------------------------------------
# Utility: significance bracket annotation
# ---------------------------------------------------------------------------

def annotate_significance(
    ax: Axes,
    x1: float,
    x2: float,
    y: float,
    p_value: float,
    height_frac: float = 0.03,
    tick_frac: float = 0.015,
    line_color: str = "black",
    linewidth: float = 1.0,
    fontsize: float = 10.0,
) -> Axes:
    """
    Draw a significance bracket between two bar positions.

    Draws a horizontal line from (x1, y) to (x2, y) with small vertical
    ticks at each end, and the significance symbol centered above.

    Significance mapping:
        p < 0.001 → ***
        p < 0.01  → **
        p < 0.05  → *
        p >= 0.05 → ns

    Parameters
    ----------
    ax : Axes
        Target axes.
    x1, x2 : float
        Horizontal positions of the two bars to compare.
    y : float
        Vertical position of the bracket line (data coordinates).
    p_value : float
        Corrected p-value for the comparison.
    height_frac : float
        Fraction of the y-axis range to place the text above the bracket.
    tick_frac : float
        Fraction of the y-axis range for the vertical tick height.
    line_color : str
        Color for the bracket and text.
    linewidth : float
        Bracket line width.
    fontsize : float
        Font size for the significance symbol.

    Returns
    -------
    Axes
    """
    if p_value < 0.001:
        symbol = "***"
    elif p_value < 0.01:
        symbol = "**"
    elif p_value < 0.05:
        symbol = "*"
    else:
        symbol = "ns"

    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    tick_h = y_range * tick_frac
    text_offset = y_range * height_frac

    # Horizontal bracket
    ax.plot([x1, x1, x2, x2], [y - tick_h, y, y, y - tick_h],
            color=line_color, linewidth=linewidth, clip_on=False)

    # Significance text
    ax.text(
        (x1 + x2) / 2, y + text_offset, symbol,
        ha="center", va="bottom", fontsize=fontsize,
        color=line_color, fontweight="bold",
    )
    return ax


# ---------------------------------------------------------------------------
# Utility: scale bar for microscopy images
# ---------------------------------------------------------------------------

def add_scale_bar(
    ax: Axes,
    img_shape: Tuple[int, int],
    length_um: float = 200.0,
    um_per_pixel: float = 1.24,
    bar_height_px: int = 8,
    color: str = "white",
    fontsize: float = 9.0,
) -> Axes:
    """
    Add a calibrated scale bar to a microscopy image panel.

    Ported from scripts/grant/create_single_figure.py with the Incucyte
    10x calibration default of 1.24 µm/pixel.

    Parameters
    ----------
    ax : Axes
        Target axes (must already have an image displayed).
    img_shape : tuple of (int, int)
        Image dimensions as (height, width) in pixels.
    length_um : float
        Desired scale bar length in microns (default 200).
    um_per_pixel : float
        Microns per pixel calibration (Incucyte 10x ≈ 1.24 µm/px).
    bar_height_px : int
        Height of the scale bar rectangle in pixels.
    color : str
        Color of the bar and label text.
    fontsize : float
        Font size for the label.

    Returns
    -------
    Axes
    """
    h, w = img_shape[:2]
    length_px = length_um / um_per_pixel

    margin_x = int(0.05 * w)
    margin_y = int(0.06 * h)

    x0 = w - length_px - margin_x
    y0 = h - margin_y

    ax.add_patch(
        Rectangle(
            (x0, y0), length_px, bar_height_px,
            color=color, linewidth=0,
        )
    )

    ax.text(
        x0 + length_px / 2, y0 - 10,
        f"{int(length_um)} \u00b5m",
        color=color, ha="center", va="bottom", fontsize=fontsize,
    )
    return ax


# ---------------------------------------------------------------------------
# Utility: error band computation
# ---------------------------------------------------------------------------

def _compute_error_band(
    grouped: "pd.core.groupby.SeriesGroupBy",
    error_type: str,
) -> Tuple[pd.Series, pd.Series]:
    """
    Compute mean and error from a grouped Series.

    Parameters
    ----------
    grouped : SeriesGroupBy
        Grouped pandas Series (e.g. df.groupby(time_col)[value_col]).
    error_type : str
        One of 'sem', 'std', 'ci95'.

    Returns
    -------
    ts_mean : pd.Series
    ts_err : pd.Series
    """
    ts_mean = grouped.mean()
    if error_type == "ci95":
        ts_err = 1.96 * grouped.sem()
    elif error_type == "std":
        ts_err = grouped.std()
    else:  # default: sem
        ts_err = grouped.sem()
    return ts_mean, ts_err


# ---------------------------------------------------------------------------
# Panel: microscopy image with multi-timepoint wound border overlays
# ---------------------------------------------------------------------------

def panel_image_with_borders(
    ax: Axes,
    img_raw: np.ndarray,
    edges: List[Tuple[np.ndarray, np.ndarray, float, str]],
    title: str = "",
    sigma: float = 3.0,
    invert: bool = True,
    contrast: float = 1.2,
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
    show_scale_bar: bool = False,
    um_per_pixel: float = 1.24,
    scale_bar_um: float = 200.0,
    show_legend: bool = False,
    accent_color: str = WOUND_ACCENT_COLOR,
    border_color: str = WOUND_BORDER_COLOR,
) -> Axes:
    """
    Draw a microscopy image with semi-transparent wound region overlays.

    Each entry in *edges* fills the wound region between upper and lower
    boundaries with a semi-transparent overlay whose intensity is
    controlled by an *emphasis* parameter (0--1), enabling cumulative
    temporal overlays where earlier timepoints appear progressively fainter.

    Parameters
    ----------
    ax : Axes
        Target matplotlib axes.
    img_raw : np.ndarray
        Raw grayscale or RGB image array (H, W) or (H, W, C).
    edges : list of (upper_edge, lower_edge, emphasis, label)
        Each tuple contains:
        - upper_edge : 1-D array of y-coordinates (length W).
        - lower_edge : 1-D array of y-coordinates (length W).
        - emphasis : float in [0, 1] controlling overlay intensity.
        - label : legend label (e.g. '0 h', '12 h').
    title : str
        Subplot title (e.g. "t = 0 h").
    sigma : float
        Gaussian smoothing sigma for border lines.
    invert : bool
        Invert grayscale (phase-contrast convention).
    contrast : float
        Contrast multiplier applied after inversion.
    panel_label : str
        Bold panel label (A, B, C...).
    font_scale : float
        Global font scaling factor.
    show_scale_bar : bool
        If True, add a calibrated scale bar in the lower-right corner.
    um_per_pixel : float
        Microns per pixel calibration (default 1.24 for Incucyte 10x).
    scale_bar_um : float
        Scale bar length in microns (default 200).
    show_legend : bool
        If True, display a compact legend mapping emphasis to timepoints.
    accent_color : str
        Fill color for wound region overlay (default deep navy).
    border_color : str
        Color for edge boundary lines (default white).

    Returns
    -------
    Axes
    """
    if img_raw.ndim == 3:
        img = np.mean(img_raw, axis=2).astype(np.float32)
    else:
        img = img_raw.astype(np.float32)

    H, W = img.shape
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)
    if invert:
        img = 1.0 - img
    img = np.clip(img * contrast, 0, 1)

    ax.imshow(img, cmap="gray", vmin=0, vmax=1, aspect="equal")

    x = np.arange(W)
    legend_handles: List[Rectangle] = []

    for upper_edge, lower_edge, emphasis, label in edges:
        upper_smooth = gaussian_filter1d(upper_edge.astype(float), sigma=sigma)
        lower_smooth = gaussian_filter1d(lower_edge.astype(float), sigma=sigma)

        # Semi-transparent wound region fill
        fill_alpha = 0.08 + emphasis * 0.37   # Range: 0.08 (faint) to 0.45
        ax.fill_between(
            x, upper_smooth, lower_smooth,
            color=accent_color, alpha=fill_alpha, zorder=2,
        )

        # Thin high-contrast border at wound edges
        border_lw = 0.4 + emphasis * 0.8      # Range: 0.4 to 1.2
        border_alpha = 0.3 + emphasis * 0.6   # Range: 0.3 to 0.9
        border_ls = "--" if emphasis < 0.4 else "-"

        for edge_arr in (upper_smooth, lower_smooth):
            ax.plot(
                x, edge_arr, color=border_color,
                linewidth=border_lw, alpha=border_alpha,
                linestyle=border_ls, solid_capstyle="round",
                zorder=3,
            )

        if label:
            legend_handles.append(
                Rectangle(
                    (0, 0), 1, 1,
                    facecolor=accent_color, alpha=fill_alpha,
                    edgecolor=border_color, linewidth=0.6,
                    label=label,
                )
            )

    ax.set_xlim(0, W - 1)
    ax.set_ylim(H - 1, 0)
    ax.axis("off")

    if show_scale_bar:
        add_scale_bar(
            ax, img_shape=(H, W),
            length_um=scale_bar_um,
            um_per_pixel=um_per_pixel,
            fontsize=9.0 * font_scale,
        )

    if show_legend and legend_handles:
        legend = ax.legend(
            handles=legend_handles, loc="upper right",
            frameon=True, facecolor="black", edgecolor="gray",
            framealpha=0.6, fontsize=8 * font_scale,
            labelcolor="white",
            title="Time", title_fontsize=8 * font_scale,
        )
        legend.get_title().set_color("white")
        legend.get_frame().set_linewidth(0.5)

    if title:
        ax.set_title(title, fontsize=11 * font_scale, pad=4)

    if panel_label:
        ax.text(
            -0.04, 1.04, panel_label,
            transform=ax.transAxes,
            fontsize=label_fontsize, fontweight="bold",
            va="bottom", ha="right",
        )

    return ax


# ---------------------------------------------------------------------------
# Panel: microscopy image with interval-based closure shading (new timelapse)
# ---------------------------------------------------------------------------

# Boundary colors per timepoint (consistent across panels A–C) are defined above.

# Closure interval fill colors (RGBA components, alpha applied separately)
_CLOSURE_COLOR_DELTA_0_MID: Tuple[float, float, float] = _TIMELAPSE_FILL_COLORS[0]
_CLOSURE_COLOR_DELTA_MID_FIN: Tuple[float, float, float] = _TIMELAPSE_FILL_COLORS[1]


def panel_image_with_closures(
    ax: Axes,
    img_raw: np.ndarray,
    mask_t0: Optional[np.ndarray] = None,
    mask_tmid: Optional[np.ndarray] = None,
    mask_tfinal: Optional[np.ndarray] = None,
    t_labels: Tuple[float, float, float] = (0.0, 12.0, 24.0),
    sigma: float = 2.0,
    invert: bool = True,
    contrast: float = 1.2,
    title: str = "",
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
    show_scale_bar: bool = False,
    um_per_pixel: float = 1.24,
    scale_bar_um: float = 200.0,
    show_legend: bool = False,
    closure_alpha: float = 0.50,
) -> Axes:
    """
    Render a timelapse panel with interval-based closure shading.

    Visualization logic (interval-based, not cumulative edge emphasis):

    Mask boundaries are drawn as contour lines using a magma-inspired palette
    (early → late), and the t=0 wound receives a pastel highlight for emphasis.

    Closure intervals are filled as semi-transparent overlays derived from
    the same palette so progressive contraction remains easy to compare.

    Panel-specific content controlled by which masks are passed:
        Panel A: mask_t0 only (boundary, no fill)
        Panel B: mask_t0 + mask_tmid (two boundaries, blue fill)
        Panel C: all three masks (three boundaries, blue + orange fills)

    Legend is rendered only when show_legend=True (intended for Panel C).

    Parameters
    ----------
    ax : Axes
        Target matplotlib axes.
    img_raw : np.ndarray
        Raw grayscale or RGB image (H, W) or (H, W, C).
    mask_t0 : np.ndarray | None
        Boolean wound mask at t=0.
    mask_tmid : np.ndarray | None
        Boolean wound mask at the mid timepoint. Pass None for Panel A.
    mask_tfinal : np.ndarray | None
        Boolean wound mask at the final timepoint. Pass None for Panels A–B.
    t_labels : tuple of float
        (t0_hours, tmid_hours, tfinal_hours) used in legend text.
    sigma : float
        Gaussian smoothing sigma applied to masks before contouring.
    invert : bool
        Invert grayscale intensities (phase-contrast convention).
    contrast : float
        Contrast multiplier after inversion.
    title : str
        Subplot title.
    panel_label : str
        Bold panel label (A, B, C…).
    label_fontsize : int
        Font size for the panel label.
    font_scale : float
        Global font scaling factor.
    show_scale_bar : bool
        If True, add a calibrated scale bar in the lower-right corner.
    um_per_pixel : float
        Microns per pixel (Incucyte 10x ≈ 1.24 µm/px).
    scale_bar_um : float
        Scale bar length in microns.
    show_legend : bool
        If True, render a legend mapping colors to timepoints and intervals.
    closure_alpha : float
        Alpha for closure region fills (0.4–0.6 recommended).

    Returns
    -------
    Axes
    """
    # ---- Image preprocessing ------------------------------------------------
    if img_raw.ndim == 3:
        img = np.mean(img_raw, axis=2).astype(np.float32)
    else:
        img = img_raw.astype(np.float32)

    H, W = img.shape
    img = (img - img.min()) / (img.max() - img.min() + 1e-8)
    if invert:
        img = 1.0 - img
    img = np.clip(img * contrast, 0, 1)

    def _ensure_bool(mask):
        return np.asarray(mask).astype(bool) if mask is not None else None

    mask_t0 = _ensure_bool(mask_t0)
    mask_tmid = _ensure_bool(mask_tmid)
    mask_tfinal = _ensure_bool(mask_tfinal)

    ax.imshow(img, cmap="gray", vmin=0, vmax=1, aspect="equal")

    # ---- Closure region fills (RGBA overlay, zorder=3) ----------------------
    def _make_rgba_overlay(
        mask: np.ndarray,
        rgb: Tuple[float, float, float],
        alpha: float,
    ) -> np.ndarray:
        """Build an (H, W, 4) RGBA float32 array; non-mask pixels are transparent."""
        overlay = np.zeros((H, W, 4), dtype=np.float32)
        overlay[mask, 0] = rgb[0]
        overlay[mask, 1] = rgb[1]
        overlay[mask, 2] = rgb[2]
        overlay[mask, 3] = alpha
        return overlay

    if mask_t0 is not None:
        ax.imshow(
            _make_rgba_overlay(
                mask_t0,
                _TIMELAPSE_T0_HIGHLIGHT_COLOR,
                _TIMELAPSE_T0_HIGHLIGHT_ALPHA,
            ),
            aspect="equal", zorder=2,
        )

    if mask_t0 is not None and mask_tmid is not None:
        delta_0_mid = mask_t0 & (~mask_tmid)
        if delta_0_mid.any():
            ax.imshow(
                _make_rgba_overlay(delta_0_mid, _CLOSURE_COLOR_DELTA_0_MID, closure_alpha),
                aspect="equal", zorder=3,
            )

    if mask_tmid is not None and mask_tfinal is not None:
        delta_mid_fin = mask_tmid & (~mask_tfinal)
        if delta_mid_fin.any():
            ax.imshow(
                _make_rgba_overlay(delta_mid_fin, _CLOSURE_COLOR_DELTA_MID_FIN, closure_alpha),
                aspect="equal", zorder=3,
            )

    # ---- Mask boundary contours (zorder=4) ----------------------------------
    def _draw_boundary(
        mask: np.ndarray,
        color: str,
        linewidth: float = 1.5,
    ) -> None:
        """Smooth the mask and draw its boundary contour at level 0.5."""
        smoothed = gaussian_filter(mask.astype(np.float32), sigma=sigma)
        # Guard: contour requires at least one transition across the level
        if smoothed.min() < 0.5 < smoothed.max():
            ax.contour(smoothed, levels=[0.5], colors=[color],
                       linewidths=[linewidth], zorder=4)

    if mask_t0 is not None:
        _draw_boundary(mask_t0, _TIMELAPSE_BOUNDARY_COLORS["t0"])
    if mask_tmid is not None:
        _draw_boundary(mask_tmid, _TIMELAPSE_BOUNDARY_COLORS["tmid"])
    if mask_tfinal is not None:
        _draw_boundary(mask_tfinal, _TIMELAPSE_BOUNDARY_COLORS["tfinal"])

    ax.set_xlim(0, W - 1)
    ax.set_ylim(H - 1, 0)
    ax.axis("off")

    # ---- Scale bar ----------------------------------------------------------
    if show_scale_bar:
        add_scale_bar(
            ax, img_shape=(H, W),
            length_um=scale_bar_um,
            um_per_pixel=um_per_pixel,
            fontsize=9.0 * font_scale,
        )

    # ---- Legend (Panel C only) ----------------------------------------------
    if show_legend:
        legend_elements: List = [
            Line2D(
                [0], [0],
                color=_TIMELAPSE_BOUNDARY_COLORS["t0"],
                linewidth=1.5,
                label=f"t = {t_labels[0]:.0f} h boundary",
            ),
        ]
        if mask_tmid is not None:
            legend_elements.append(
                Line2D(
                    [0], [0],
                    color=_TIMELAPSE_BOUNDARY_COLORS["tmid"],
                    linewidth=1.5,
                    label=f"t = {t_labels[1]:.0f} h boundary",
                )
            )
        if mask_tfinal is not None:
            legend_elements.append(
                Line2D(
                    [0], [0],
                    color=_TIMELAPSE_BOUNDARY_COLORS["tfinal"],
                    linewidth=1.5,
                    label=f"t = {t_labels[2]:.0f} h boundary",
                )
            )
        if mask_t0 is not None and mask_tmid is not None:
            legend_elements.append(
                Patch(
                    facecolor=_CLOSURE_COLOR_DELTA_0_MID, alpha=closure_alpha,
                    label=(
                        f"Closure {t_labels[0]:.0f}\u2013{t_labels[1]:.0f} h"
                    ),
                )
            )
        if mask_tmid is not None and mask_tfinal is not None:
            legend_elements.append(
                Patch(
                    facecolor=_CLOSURE_COLOR_DELTA_MID_FIN, alpha=closure_alpha,
                    label=(
                        f"Closure {t_labels[1]:.0f}\u2013{t_labels[2]:.0f} h"
                    ),
                )
            )

        legend = ax.legend(
            handles=legend_elements, loc="upper right",
            frameon=True, facecolor="black", edgecolor="gray",
            framealpha=0.7, fontsize=7.5 * font_scale,
            labelcolor="white",
        )
        legend.get_frame().set_linewidth(0.5)

    # ---- Title and panel label ----------------------------------------------
    if title:
        ax.set_title(title, fontsize=11 * font_scale, pad=4)

    if panel_label:
        ax.text(
            -0.04, 1.04, panel_label,
            transform=ax.transAxes,
            fontsize=label_fontsize, fontweight="bold",
            va="bottom", ha="right",
        )

    return ax


# ---------------------------------------------------------------------------
# Panel: QC pass-rate bar chart
# ---------------------------------------------------------------------------

def panel_qc_pass_rate(
    ax: Axes,
    df_qc: pd.DataFrame,
    color_map: Dict[str, str],
    conditions: Optional[List[str]] = None,
    cell_lines: Optional[List[str]] = None,
    bar_width: float = 0.30,
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
) -> Axes:
    """
    Bar chart of QC pass rates per condition grouped by cell line.

    Parameters
    ----------
    ax : Axes
        Target axes.
    df_qc : pd.DataFrame
        Must contain columns: cell_line, sample_condition, qc_t0_valid (bool).
    color_map : dict
        cell_line -> hex color.
    conditions : list | None
        Ordered subset of conditions to display.
    cell_lines : list | None
        Ordered cell lines.
    bar_width : float
        Width of each bar.
    panel_label : str
        Panel letter for upper-left label.

    Returns
    -------
    Axes
    """
    tick_fs = 9 * font_scale
    label_fs = 10 * font_scale
    title_fs = 11 * font_scale

    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c in df_qc["sample_condition"].unique()]
    if cell_lines is None:
        cell_lines = sorted(df_qc["cell_line"].dropna().unique())

    rate_df = (
        df_qc.groupby(["cell_line", "sample_condition"])["qc_t0_valid"]
        .agg(lambda s: 100.0 * s.sum() / max(len(s), 1))
        .reset_index()
        .rename(columns={"qc_t0_valid": "pass_rate"})
    )

    x = np.arange(len(cell_lines))
    n_cond = len(conditions)

    for i, cond in enumerate(conditions):
        offset = (i - (n_cond - 1) / 2) * bar_width
        alpha = CONDITION_ALPHA.get(cond, 0.8)

        heights = []
        colors_bar = []
        for cl in cell_lines:
            row = rate_df[(rate_df["cell_line"] == cl) & (rate_df["sample_condition"] == cond)]
            heights.append(row["pass_rate"].values[0] if not row.empty else 0.0)
            rgba = list(mcolors.to_rgba(color_map.get(cl, "#999999")))
            rgba[3] = alpha
            colors_bar.append(tuple(rgba))

        ax.bar(x + offset, heights, bar_width, color=colors_bar,
               edgecolor="black", linewidth=0.8, label=cond, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels(cell_lines, fontsize=tick_fs)
    ax.set_ylabel("QC pass rate (%)", fontsize=label_fs)
    ax.set_ylim(0, 110)
    ax.axhline(100, color="gray", linewidth=0.7, linestyle=":", alpha=0.5)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_title("t=0 Detection Quality", fontsize=title_fs)
    ax.tick_params(axis="y", labelsize=tick_fs)
    ax.legend(fontsize=tick_fs * 0.9, frameon=False, title="Condition",
              title_fontsize=tick_fs * 0.9)

    if panel_label:
        ax.text(-0.15, 1.05, panel_label, transform=ax.transAxes,
                fontsize=label_fontsize, fontweight="bold", va="top")

    despine(ax)
    return ax


# ---------------------------------------------------------------------------
# Panel: Monotonic constraint application rate
# ---------------------------------------------------------------------------

def panel_constraint_rate(
    ax: Axes,
    df_qc: pd.DataFrame,
    color_map: Dict[str, str],
    conditions: Optional[List[str]] = None,
    cell_lines: Optional[List[str]] = None,
    bar_width: float = 0.30,
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
) -> Axes:
    """
    Bar chart of monotonic constraint application rate per condition.

    The constraint rate is the fraction of timepoints (t > 0) for which
    the monotonic closure constraint was enforced by the model.
    A lower rate indicates the model's raw prediction already respected
    monotonicity; a higher rate indicates more active enforcement.

    Parameters
    ----------
    ax : Axes
        Target axes.
    df_qc : pd.DataFrame
        Must contain: cell_line, sample_condition, constraint_rate (float 0-1).
    color_map : dict
        cell_line -> hex color.
    panel_label : str
        Panel letter.

    Returns
    -------
    Axes
    """
    tick_fs = 9 * font_scale
    label_fs = 10 * font_scale
    title_fs = 11 * font_scale

    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c in df_qc["sample_condition"].unique()]
    if cell_lines is None:
        cell_lines = sorted(df_qc["cell_line"].dropna().unique())

    agg = (
        df_qc.groupby(["cell_line", "sample_condition"])["constraint_rate"]
        .agg(["mean", "sem"])
        .reset_index()
    )

    x = np.arange(len(cell_lines))
    n_cond = len(conditions)

    for i, cond in enumerate(conditions):
        offset = (i - (n_cond - 1) / 2) * bar_width
        alpha = CONDITION_ALPHA.get(cond, 0.8)

        heights, errs, colors_bar = [], [], []
        for cl in cell_lines:
            row = agg[(agg["cell_line"] == cl) & (agg["sample_condition"] == cond)]
            if row.empty:
                heights.append(0.0)
                errs.append(0.0)
            else:
                heights.append(100.0 * row["mean"].values[0])
                errs.append(100.0 * row["sem"].values[0])
            rgba = list(mcolors.to_rgba(color_map.get(cl, "#999999")))
            rgba[3] = alpha
            colors_bar.append(tuple(rgba))

        ax.bar(x + offset, heights, bar_width, yerr=errs,
               color=colors_bar, edgecolor="black", linewidth=0.8,
               error_kw={"lw": 1.0, "capsize": 2}, label=cond, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels(cell_lines, fontsize=tick_fs)
    ax.set_ylabel("Constrained frames (%)", fontsize=label_fs)
    ax.set_ylim(0, 110)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_title("Monotonic Constraint Rate", fontsize=title_fs)
    ax.tick_params(axis="y", labelsize=tick_fs)

    if panel_label:
        ax.text(-0.15, 1.05, panel_label, transform=ax.transAxes,
                fontsize=label_fontsize, fontweight="bold", va="top")

    despine(ax)
    return ax


# ---------------------------------------------------------------------------
# Panel: Normalized wound area over time
# ---------------------------------------------------------------------------

def panel_normalized_area(
    ax: Axes,
    df_legacy: pd.DataFrame,
    color_map: Dict[str, str],
    conditions: Optional[List[str]] = None,
    cell_lines: Optional[List[str]] = None,
    time_col: str = "t_seg",
    error_type: str = "ci95",
    show_error_band: bool = False,
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
    closure_pct_t12: Optional[float] = None,
    closure_pct_t24: Optional[float] = None,
    t_label_12: float = 12.0,
    t_label_24: float = 24.0,
    min_traj_frac: float = 0.8,
) -> Axes:
    """
    Line plot of normalized wound area over time (area_t / area_t0).

    Normalization relative to t=0 removes between-well variability in
    initial wound size, isolating the closure dynamics.

    Only timepoints where at least ``min_traj_frac`` of the trajectories
    (within each cell-line × condition group) contribute are plotted.
    This prevents the spurious apparent increase that arises when faster-
    closing trajectories finish early and drop out of the mean, leaving
    only the slower subset to determine the group average.

    Parameters
    ----------
    ax : Axes
        Target axes.
    df_legacy : pd.DataFrame
        Must contain: cell_line, sample_condition, t_seg, wound_area,
        identifier, img_area.
    color_map : dict
        cell_line -> hex color.
    conditions : list | None
        Ordered conditions to display.
    error_type : str
        Error band type: 'sem', 'std', or 'ci95' (default).
    min_traj_frac : float
        Minimum fraction of trajectories that must contribute at a given
        timepoint for it to be included in the plot (default 0.8 = 80%).

    Returns
    -------
    Axes
    """
    tick_fs = 9 * font_scale
    label_fs = 10 * font_scale
    title_fs = 11 * font_scale
    lw = 2.5 * font_scale  # increased for readability

    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c in df_legacy["sample_condition"].unique()]
    if cell_lines is None:
        cell_lines = sorted(df_legacy["cell_line"].dropna().unique())

    # Compute normalized area per trajectory
    df = df_legacy.copy()
    t0_areas = (
        df[df[time_col] == 0]
        .groupby("identifier")["wound_area"]
        .first()
        .rename("area_t0")
    )
    df = df.merge(t0_areas, on="identifier", how="left")
    df["norm_area"] = df["wound_area"] / (df["area_t0"] + 1e-8)

    legend_handles: List[Line2D] = []
    legend_labels: List[str] = []

    for cl in cell_lines:
        for cond in conditions:
            sub = df[(df["cell_line"] == cl) & (df["sample_condition"] == cond)]
            if sub.empty:
                continue

            # Count distinct trajectories at each timepoint.
            # Only retain timepoints where ≥ min_traj_frac of the total
            # trajectory count contributes, preventing composition bias
            # when faster-closing trajectories finish early.
            n_total = sub["identifier"].nunique()
            min_n = max(1, int(np.ceil(min_traj_frac * n_total)))
            traj_count_per_t = sub.groupby(time_col)["identifier"].nunique()
            valid_t = traj_count_per_t[traj_count_per_t >= min_n].index
            sub_filtered = sub[sub[time_col].isin(valid_t)]

            if sub_filtered.empty:
                continue

            g = sub_filtered.groupby(time_col)["norm_area"]
            ts_mean, ts_err = _compute_error_band(g, error_type)

            color = color_map.get(cl, "#999999")
            ls = CONDITION_LINESTYLE.get(cond, "-")
            alpha = CONDITION_ALPHA.get(cond, 0.8)

            ax.plot(ts_mean.index, ts_mean.values,
                    color=color, linestyle=ls, linewidth=lw,
                    alpha=alpha)
            if show_error_band:
                fill_alpha = max(alpha * 0.20, 0.10)
                ax.fill_between(
                    ts_mean.index,
                    ts_mean.values - ts_err.values,
                    ts_mean.values + ts_err.values,
                    color=color, alpha=fill_alpha,
                )

            handle = Line2D([], [], color=color, linestyle=ls, linewidth=lw,
                            alpha=alpha)
            legend_handles.append(handle)
            legend_labels.append(f"{cl} \u2013 {cond} (N={n_total})")

    ax.axhline(1.0, color="gray", linewidth=0.7, linestyle=":", alpha=0.5)

    _err_label = {"sem": "\u00b1 SEM", "std": "\u00b1 SD", "ci95": "95% CI"}.get(error_type, "")
    ax.set_xlabel("Time (hours)", fontsize=label_fs)
    ax.set_ylabel("Normalised wound area (A / A0)", fontsize=label_fs)
    ax.tick_params(axis="both", labelsize=tick_fs)
    ax.grid(alpha=0.3)

    # Build title; append closure percentages when available
    title_str = f"Wound Area Closure ({_err_label})"
    if closure_pct_t12 is not None and closure_pct_t24 is not None:
        title_str += (
            f"\n{int(round(t_label_12))}h: {closure_pct_t12:.1f}%"
            f" | {int(round(t_label_24))}h: {closure_pct_t24:.1f}%"
        )
    ax.set_title(title_str, fontsize=title_fs)
    ax.legend(legend_handles, legend_labels, fontsize=tick_fs * 0.85,
              frameon=False, handlelength=2.5)

    if panel_label:
        ax.text(-0.15, 1.05, panel_label, transform=ax.transAxes,
                fontsize=label_fontsize, fontweight="bold", va="top")

    despine(ax)
    return ax


# ---------------------------------------------------------------------------
# Panel: Time series of wound distance
# ---------------------------------------------------------------------------

def panel_timeseries_distance(
    ax: Axes,
    df_ts: pd.DataFrame,
    value_col: str = "distance_mean",
    color_map: Optional[Dict[str, str]] = None,
    conditions: Optional[List[str]] = None,
    cell_lines: Optional[List[str]] = None,
    time_col: str = "t",
    error_type: str = "ci95",
    show_error_band: bool = False,
    show_individual: bool = False,
    ylabel: str = "Distance (pixels)",
    title: str = "Wound Edge Displacement Over Time",
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
    min_traj_frac: float = 0.8,
) -> Axes:
    """
    Line plot of wound edge displacement over time, grouped by condition x cell line.

    Only timepoints where at least ``min_traj_frac`` of the trajectories
    within each group contribute are plotted, preventing the composition
    bias that arises when short trajectories drop out of the mean.

    Parameters
    ----------
    ax : Axes
        Target axes.
    df_ts : pd.DataFrame
        Must contain: cell_line, sample_condition, t (hours), distance_mean,
        trajectory.
    value_col : str
        Column to plot.
    color_map : dict | None
        cell_line -> hex color. Defaults to CELL_LINE_COLORS.
    conditions : list | None
        Ordered conditions to display.
    error_type : str
        Error band type: 'sem', 'std', or 'ci95' (default).
    show_individual : bool
        If True, draw thin semi-transparent lines for each individual
        trajectory behind the group mean.
    min_traj_frac : float
        Minimum fraction of trajectories required at each timepoint
        (default 0.8 = 80%).

    Returns
    -------
    Axes
    """
    if color_map is None:
        color_map = CELL_LINE_COLORS

    tick_fs = 9 * font_scale
    label_fs = 10 * font_scale
    title_fs = 11 * font_scale
    lw = 2.0 * font_scale

    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c in df_ts["sample_condition"].unique()]
    if cell_lines is None:
        cell_lines = sorted(df_ts["cell_line"].dropna().unique())

    legend_handles: List[Line2D] = []
    legend_labels: List[str] = []

    for cl in cell_lines:
        for cond in conditions:
            sub = df_ts[(df_ts["cell_line"] == cl) & (df_ts["sample_condition"] == cond)]
            if sub.empty:
                continue

            # Filter to timepoints where ≥ min_traj_frac of trajectories contribute
            traj_col = "trajectory" if "trajectory" in sub.columns else "identifier"
            n_total = sub[traj_col].nunique()
            min_n = max(1, int(np.ceil(min_traj_frac * n_total)))
            traj_count_per_t = sub.groupby(time_col)[traj_col].nunique()
            valid_t = traj_count_per_t[traj_count_per_t >= min_n].index
            sub_filtered = sub[sub[time_col].isin(valid_t)]

            if sub_filtered.empty:
                continue

            color = color_map.get(cl, "#999999")
            ls = CONDITION_LINESTYLE.get(cond, "-")
            alpha = CONDITION_ALPHA.get(cond, 0.8)

            # Individual trajectories (thin, behind the mean)
            if show_individual and traj_col in sub_filtered.columns:
                for _, traj_df in sub_filtered.groupby(traj_col):
                    traj_sorted = traj_df.sort_values(time_col)
                    ax.plot(
                        traj_sorted[time_col], traj_sorted[value_col],
                        color=color, alpha=0.10, linewidth=0.6, zorder=1,
                    )

            g = sub_filtered.groupby(time_col)[value_col]
            ts_mean, ts_err = _compute_error_band(g, error_type)

            ax.plot(ts_mean.index, ts_mean.values,
                    color=color, linestyle=ls, linewidth=lw,
                    alpha=alpha, zorder=2)
            if show_error_band:
                fill_alpha = max(alpha * 0.08, 0.05)
                ax.fill_between(
                    ts_mean.index,
                    ts_mean.values - ts_err.values,
                    ts_mean.values + ts_err.values,
                    color=color, alpha=fill_alpha, zorder=1,
                )

            handle = Line2D([], [], color=color, linestyle=ls, linewidth=lw,
                            alpha=alpha)
            legend_handles.append(handle)
            legend_labels.append(f"{cl} \u2013 {cond} (N={n_total})")

    _err_label = {"sem": "\u00b1 SEM", "std": "\u00b1 SD", "ci95": "95% CI"}.get(error_type, "")
    ax.set_xlabel("Time (hours)", fontsize=label_fs)
    ax.set_ylabel(ylabel, fontsize=label_fs)
    ax.tick_params(axis="both", labelsize=tick_fs)
    ax.grid(alpha=0.3)
    ax.set_title(f"{title} ({_err_label})", fontsize=title_fs)
    ax.legend(legend_handles, legend_labels, fontsize=tick_fs * 0.85,
              frameon=False, handlelength=2.5)

    if panel_label:
        ax.text(-0.15, 1.05, panel_label, transform=ax.transAxes,
                fontsize=label_fontsize, fontweight="bold", va="top")

    despine(ax)
    return ax


# ---------------------------------------------------------------------------
# Panel: Cross-sectional bar chart at single timepoint
# ---------------------------------------------------------------------------

def panel_crosssectional_bar(
    ax: Axes,
    df_cs: pd.DataFrame,
    value_col: str = "speed_mean",
    color_map: Optional[Dict[str, str]] = None,
    conditions: Optional[List[str]] = None,
    cell_lines: Optional[List[str]] = None,
    ylabel: str = "Speed (pixels/h)",
    title: str = "",
    bar_width: float = 0.28,
    show_points: bool = True,
    significance_brackets: Optional[List[Dict]] = None,
    panel_label: str = "",
    label_fontsize: int = 14,
    font_scale: float = 1.0,
) -> Axes:
    """
    Grouped bar chart of a wound metric at a single timepoint.

    Visual encoding:
    - Bar color encodes cell_line (via color_map)
    - Bar alpha encodes condition (via CONDITION_ALPHA)
    - Individual data points overlaid as scatter
    - Optional significance brackets drawn above compared bars

    Parameters
    ----------
    ax : Axes
        Target axes.
    df_cs : pd.DataFrame
        Cross-sectional data (single timepoint).
    value_col : str
        Column to display (speed_mean, distance_mean, etc.)
    color_map : dict | None
        cell_line -> hex color.
    show_points : bool
        Overlay individual wells as scatter points.
    significance_brackets : list of dict | None
        Each dict has keys: cell_line, condition, control, p_corrected.
        Draws a bracket between the condition and control bars within
        each cell_line group.

    Returns
    -------
    Axes
    """
    if color_map is None:
        color_map = CELL_LINE_COLORS

    tick_fs = 9 * font_scale
    label_fs = 10 * font_scale
    title_fs = 11 * font_scale
    pt_sz = 28 * font_scale

    if conditions is None:
        conditions = [c for c in CONDITION_ORDER if c in df_cs["sample_condition"].unique()]
    if cell_lines is None:
        cell_lines = sorted(df_cs["cell_line"].dropna().unique())

    agg = (
        df_cs.groupby(["cell_line", "sample_condition"])[value_col]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    agg["sem"] = agg["std"] / np.sqrt(agg["count"].clip(lower=1))

    x = np.arange(len(cell_lines))
    n_cond = len(conditions)

    # Build lookup: (cell_line_idx, condition) -> x_position
    bar_x_lookup: Dict[Tuple[int, str], float] = {}

    for i, cond in enumerate(conditions):
        offset = (i - (n_cond - 1) / 2) * bar_width
        alpha = CONDITION_ALPHA.get(cond, 0.8)

        means, sems, colors_bar = [], [], []
        cond_n_total = 0
        for j, cl in enumerate(cell_lines):
            bar_x_lookup[(j, cond)] = x[j] + offset
            row = agg[(agg["cell_line"] == cl) & (agg["sample_condition"] == cond)]
            means.append(row["mean"].values[0] if not row.empty else np.nan)
            sems.append(row["sem"].values[0] if not row.empty else 0.0)
            cond_n_total += int(row["count"].values[0]) if not row.empty else 0
            rgba = list(mcolors.to_rgba(color_map.get(cl, "#999999")))
            rgba[3] = alpha
            colors_bar.append(tuple(rgba))

        ax.bar(x + offset, means, bar_width, yerr=sems,
               color=colors_bar, edgecolor="black", linewidth=0.8,
               error_kw={"lw": 1.0, "capsize": 2},
               label=f"{cond} (N={cond_n_total})", zorder=2)

        if show_points:
            rng = np.random.default_rng(seed=42)
            for j, cl in enumerate(cell_lines):
                pts = df_cs[
                    (df_cs["cell_line"] == cl) & (df_cs["sample_condition"] == cond)
                ][value_col].dropna()
                if pts.empty:
                    continue
                jitter = rng.normal(0, bar_width * 0.08, size=len(pts))
                ax.scatter(
                    np.full(len(pts), x[j] + offset) + jitter,
                    pts.values,
                    s=pt_sz, color="black", alpha=0.6, zorder=3,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(cell_lines, fontsize=tick_fs)
    ax.set_ylabel(ylabel, fontsize=label_fs)
    ax.tick_params(axis="y", labelsize=tick_fs)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    if title:
        ax.set_title(title, fontsize=title_fs)
    ax.legend(fontsize=tick_fs * 0.85, frameon=False)

    # --- Significance brackets ---
    if significance_brackets:
        # Compute the max bar top (mean + sem) for bracket placement
        max_top = 0.0
        for _, row in agg.iterrows():
            val = row["mean"] + row["sem"]
            if np.isfinite(val) and val > max_top:
                max_top = val

        bracket_y = max_top * 1.08
        y_step = max_top * 0.10

        for k, bracket in enumerate(significance_brackets):
            cl_name = bracket["cell_line"]
            cond_name = bracket["condition"]
            ctrl_name = bracket["control"]
            p_corr = bracket["p_corrected"]

            cl_idx = cell_lines.index(cl_name) if cl_name in cell_lines else None
            if cl_idx is None:
                continue

            x_cond = bar_x_lookup.get((cl_idx, cond_name))
            x_ctrl = bar_x_lookup.get((cl_idx, ctrl_name))
            if x_cond is None or x_ctrl is None:
                continue

            annotate_significance(
                ax, x_ctrl, x_cond, bracket_y + k * y_step, p_corr,
                fontsize=9 * font_scale,
            )

        # Extend y-axis to accommodate brackets
        n_brackets = len(significance_brackets)
        ax.set_ylim(top=bracket_y + n_brackets * y_step + max_top * 0.08)

    if panel_label:
        ax.text(-0.15, 1.05, panel_label, transform=ax.transAxes,
                fontsize=label_fontsize, fontweight="bold", va="top")

    despine(ax)
    return ax
