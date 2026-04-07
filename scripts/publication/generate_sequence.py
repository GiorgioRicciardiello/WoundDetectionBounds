"""
Sequence Panel Generator
========================

Load an ``experiment.pkl`` trajectory and export each of the six
detection-pipeline panels as a **separate** publication-ready image,
organised into per-timepoint folders.

The six panels mirror ``WoundDetector._debug_plot`` but are rendered
individually so they can be composed in a manuscript layout manager.

Output structure
----------------
::

    paper_publication/sequence/{sample_name}/
    ├── t_00/
    │   ├── panel_1_original.png
    │   ├── panel_2_variance_map.png
    │   ├── panel_3_y_profile.png
    │   ├── panel_4_raw_edges.png
    │   ├── panel_5_smooth_edges.png
    │   └── panel_6_mask_overlay.png
    ├── t_01/
    │   └── ...

Usage
-----
Run from the project root::

    python -m scripts.publication.generate_sequence <path_to_experiment_pkl>

Or import and call programmatically::

    from scripts.publication.generate_sequence import generate_sequence
    generate_sequence(Path(".../.../experiment.pkl"))
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

from library.core.types import WoundDetectorConfig
from library.wound_quantification.trajectory import load_trajectory_results
from library.wound_standard.detector import WoundDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Publication defaults
# ---------------------------------------------------------------------------
DPI = 300
FIGSIZE_PANEL = (6, 5)
FIGSIZE_PROFILE = (4, 5)


# ---------------------------------------------------------------------------
# Intermediate extraction (no detector modification)
# ---------------------------------------------------------------------------

def _extract_intermediates(
    detector: WoundDetector,
    img_raw: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Re-run the detector pipeline stages to recover all intermediates.

    Parameters
    ----------
    detector : WoundDetector
        Configured detector instance (only its config and private methods
        are used — ``detect()`` is NOT called).
    img_raw : np.ndarray
        Grayscale image, ``uint8`` or ``float``, shape ``(H, W)``.

    Returns
    -------
    dict
        Keys: ``img_f``, ``variance_smooth``, ``y_min``, ``y_max``,
        ``y_center``, ``upper_raw``, ``lower_raw``, ``upper_smooth``,
        ``lower_smooth``, ``mask``, ``qc``.
    """
    cfg = detector.config

    # Normalise to float32 [0, 1]
    if img_raw.ndim == 3:
        img_raw = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
    img_f = img_raw.astype(np.float32)
    if img_f.max() > 1.0:
        img_f = img_f / 255.0

    # Stage 1 — local variance
    variance_map = detector._compute_local_variance(img_f, cfg.variance_window)
    variance_smooth = gaussian_filter1d(
        gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
        cfg.variance_sigma,
        axis=1,
    )

    # Stage 2 — Y-band
    y_min, y_max, y_center = detector._detect_y_band(variance_smooth)

    # Stage 3 — raw column-wise edges
    upper_raw, lower_raw = detector._extract_edges_per_column(
        variance_smooth, y_min, y_max, y_center,
    )

    # Stage 4 — RANSAC
    upper_ransac, lower_ransac = detector._ransac_smooth_edges(
        upper_raw, lower_raw,
    )

    # Stage 5 — Savgol smoothing
    upper_smooth = detector._savgol_smooth(upper_ransac)
    lower_smooth = detector._savgol_smooth(lower_ransac)

    # Stage 6 — mask + QC
    H, W = img_f.shape
    mask = detector._edges_to_mask(upper_smooth, lower_smooth, H, W)
    qc = detector._validate_wound_geometry(mask)

    return {
        "img_f": img_f,
        "variance_smooth": variance_smooth,
        "y_min": y_min,
        "y_max": y_max,
        "y_center": y_center,
        "upper_raw": upper_raw,
        "lower_raw": lower_raw,
        "upper_smooth": upper_smooth,
        "lower_smooth": lower_smooth,
        "mask": mask,
        "qc": qc,
    }


# ---------------------------------------------------------------------------
# Individual panel renderers
# ---------------------------------------------------------------------------

def _save_panel_original(
    img_f: np.ndarray,
    save_path: Path,
) -> None:
    """Panel 1: original grayscale image."""
    fig, ax = plt.subplots(figsize=FIGSIZE_PANEL)
    ax.imshow(img_f, cmap="gray")
    ax.axis("off")
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _save_panel_variance_map(
    img_f: np.ndarray,
    variance_smooth: np.ndarray,
    y_min: int,
    y_max: int,
    y_center: int,
    save_path: Path,
) -> None:
    """Panel 2: variance map with Y-band and centre overlaid."""
    fig, ax = plt.subplots(figsize=FIGSIZE_PANEL)
    ax.imshow(variance_smooth, cmap="viridis")
    ax.axhline(y_min, color="r", linestyle="--", linewidth=1)
    ax.axhline(y_max, color="r", linestyle="--", linewidth=1)
    ax.axhline(y_center, color="cyan", linewidth=2)
    ax.set_title(f"Variance Map  (Y-band: {y_min}\u2013{y_max})", fontsize=10)
    ax.axis("off")
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _save_panel_y_profile(
    variance_smooth: np.ndarray,
    y_min: int,
    y_max: int,
    y_center: int,
    save_path: Path,
) -> None:
    """Panel 3: row-averaged variance profile."""
    y_profile = variance_smooth.mean(axis=1)
    fig, ax = plt.subplots(figsize=FIGSIZE_PROFILE)
    ax.plot(y_profile, np.arange(len(y_profile)), "b-", linewidth=1.5)
    ax.axhline(y_center, color="cyan", linewidth=2, label="Y centre")
    ax.axhspan(y_min, y_max, alpha=0.2, color="red", label="Y band")
    ax.invert_yaxis()
    ax.set_xlabel("Mean Variance")
    ax.set_ylabel("Y (row)")
    ax.set_title("Y-Profile")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _save_panel_raw_edges(
    img_f: np.ndarray,
    upper_raw: np.ndarray,
    lower_raw: np.ndarray,
    save_path: Path,
) -> None:
    """Panel 4: raw per-column edges overlaid on the image."""
    W = img_f.shape[1]
    x = np.arange(W)
    fig, ax = plt.subplots(figsize=FIGSIZE_PANEL)
    ax.imshow(img_f, cmap="gray", alpha=0.7)
    ax.plot(x, upper_raw, "r.", markersize=1, label="Upper (raw)")
    ax.plot(x, lower_raw, "b.", markersize=1, label="Lower (raw)")
    ax.set_title("Raw Edges (per column)")
    ax.legend(fontsize=8)
    ax.axis("off")
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _save_panel_smooth_edges(
    img_f: np.ndarray,
    upper_smooth: np.ndarray,
    lower_smooth: np.ndarray,
    save_path: Path,
) -> None:
    """Panel 5: RANSAC + Savgol smoothed edges with wound region fill."""
    W = img_f.shape[1]
    x = np.arange(W)
    fig, ax = plt.subplots(figsize=FIGSIZE_PANEL)
    ax.imshow(img_f, cmap="gray", alpha=0.7)
    ax.plot(x, upper_smooth, "r-", linewidth=2, label="Upper (smooth)")
    ax.plot(x, lower_smooth, "b-", linewidth=2, label="Lower (smooth)")
    ax.fill_between(x, upper_smooth, lower_smooth, color="orange", alpha=0.3)
    ax.set_title("Smoothed Edges (RANSAC + Savgol)")
    ax.legend(fontsize=8)
    ax.axis("off")
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _save_panel_mask_overlay(
    img_f: np.ndarray,
    mask: np.ndarray,
    qc: Dict,
    method: str,
    constrained: bool,
    save_path: Path,
) -> None:
    """Panel 6: final constrained mask overlay with QC status."""
    overlay = np.stack([img_f, img_f, img_f], axis=-1)
    overlay[mask > 0, 0] = np.minimum(overlay[mask > 0, 0] + 0.3, 1.0)
    overlay[mask > 0, 1] = overlay[mask > 0, 1] * 0.7
    overlay[mask > 0, 2] = overlay[mask > 0, 2] * 0.7

    status = "PASS" if qc.get("valid", False) else f"FAIL: {qc.get('reason', '?')}"
    tag = " [constrained]" if constrained else ""

    fig, ax = plt.subplots(figsize=FIGSIZE_PANEL)
    ax.imshow(overlay)
    ax.set_title(f"Mask ({method}){tag} \u2014 {status}", fontsize=10)
    ax.axis("off")
    fig.savefig(save_path, dpi=DPI, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_sequence(
    pkl_path: Path,
    output_root: Optional[Path] = None,
    config: Optional[WoundDetectorConfig] = None,
    dpi: int = DPI,
) -> Path:
    """Generate per-timepoint panel images from an experiment pickle.

    Parameters
    ----------
    pkl_path : Path
        Path to ``experiment.pkl``.
    output_root : Path | None
        Root output directory.  Defaults to
        ``paper_publication/sequence/{sample_name}/``.
    config : WoundDetectorConfig | None
        Detector configuration for intermediate re-computation.
    dpi : int
        Figure resolution.

    Returns
    -------
    Path
        The output directory containing the timepoint folders.
    """
    global DPI
    DPI = dpi

    pkl_path = Path(pkl_path)
    if not pkl_path.exists():
        raise FileNotFoundError(f"Pickle not found: {pkl_path}")

    # Derive sample name from parent folder
    sample_name = pkl_path.parent.name

    # Default output location
    if output_root is None:
        project_root = Path(__file__).resolve().parents[2]
        output_root = project_root / "paper_publication" / "sequence" / sample_name

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    # Load trajectory
    logger.info("Loading trajectory from %s", pkl_path)
    results = load_trajectory_results(pkl_path.parent)

    if not results:
        raise ValueError(f"No results found in {pkl_path}")

    logger.info("Loaded %d timepoints for sample '%s'", len(results), sample_name)

    # Instantiate detector (re-uses same config for all frames)
    detector = WoundDetector(config=config)

    # Accumulators for trajectory-level figures
    _traj_timepoints: List[int] = []
    _traj_areas: List[float] = []
    _traj_masks: List[np.ndarray] = []
    _traj_upper_edges: List[np.ndarray] = []
    _traj_lower_edges: List[np.ndarray] = []
    _background_image: Optional[np.ndarray] = None  # t=0 frame for context

    # Sort results by timepoint index to guarantee temporal order
    results_sorted = sorted(results, key=lambda r: r["t"])

    for result in results_sorted:
        t = result["t"]
        img_raw = result.get("img_raw")

        if img_raw is None:
            logger.warning("Skipping t=%d — no image data stored", t)
            continue

        t_dir = output_root / f"t_{t:02d}"
        t_dir.mkdir(parents=True, exist_ok=True)

        logger.info("  t=%02d  →  %s", t, t_dir)

        # Re-run pipeline stages to recover intermediates
        intermediates = _extract_intermediates(detector, img_raw)

        # Panel 1 — original
        _save_panel_original(
            intermediates["img_f"],
            t_dir / "panel_1_original.png",
        )

        # Panel 2 — variance map
        _save_panel_variance_map(
            intermediates["img_f"],
            intermediates["variance_smooth"],
            intermediates["y_min"],
            intermediates["y_max"],
            intermediates["y_center"],
            t_dir / "panel_2_variance_map.png",
        )

        # Panel 3 — Y-profile
        _save_panel_y_profile(
            intermediates["variance_smooth"],
            intermediates["y_min"],
            intermediates["y_max"],
            intermediates["y_center"],
            t_dir / "panel_3_y_profile.png",
        )

        # Panel 4 — raw edges
        _save_panel_raw_edges(
            intermediates["img_f"],
            intermediates["upper_raw"],
            intermediates["lower_raw"],
            t_dir / "panel_4_raw_edges.png",
        )

        # Panel 5 — smoothed edges
        _save_panel_smooth_edges(
            intermediates["img_f"],
            intermediates["upper_smooth"],
            intermediates["lower_smooth"],
            t_dir / "panel_5_smooth_edges.png",
        )

        # Panel 6 — constrained mask overlay (from the pickle, not re-detection)
        # Normalise img for overlay
        img_f = intermediates["img_f"]
        constrained_mask = result.get("mask")
        if constrained_mask is None:
            constrained_mask = intermediates["mask"]

        _save_panel_mask_overlay(
            img_f,
            constrained_mask,
            result.get("qc", intermediates["qc"]),
            result.get("method", "unknown"),
            result.get("constrained", False),
            t_dir / "panel_6_mask_overlay.png",
        )

        # Accumulate trajectory data for summary figures
        area = result.get("area")
        if area is not None:
            upper_e, lower_e = _extract_wound_boundaries(constrained_mask)
            _traj_timepoints.append(t)
            _traj_areas.append(float(area))
            _traj_masks.append(constrained_mask)
            _traj_upper_edges.append(upper_e)
            _traj_lower_edges.append(lower_e)
            # Capture the first frame as spatial background
            if _background_image is None:
                _background_image = intermediates["img_f"]

    # ── Trajectory-level summary figures ────────────────────────────────────
    if len(_traj_timepoints) >= 2:
        logger.info("Generating trajectory summary figures…")

        t_arr = np.asarray(_traj_timepoints, dtype=float)
        a_arr = np.asarray(_traj_areas, dtype=float)

        dynamics_path = str(output_root / "dynamics.png")
        plot_wound_healing_dynamics(
            t_arr, a_arr, dynamics_path,
            upper_edges=_traj_upper_edges,
            lower_edges=_traj_lower_edges,
        )
        logger.info("  Saved: %s", dynamics_path)

        boundary_path = str(output_root / "boundary_evolution.png")
        plot_wound_boundary_evolution(
            _traj_masks, list(t_arr), boundary_path,
            background_image=_background_image,
        )
        logger.info("  Saved: %s", boundary_path)
    else:
        logger.warning(
            "Fewer than 2 timepoints with area data — skipping summary figures."
        )

    logger.info("Done. Output at: %s", output_root)
    return output_root


# ---------------------------------------------------------------------------
# Publication figure: wound healing dynamics
# ---------------------------------------------------------------------------

def _boundary_velocity(
    positions: np.ndarray,
    time_points: np.ndarray,
    sign: float,
    smooth: bool,
    savgol_window: int,
    savgol_poly: int,
) -> np.ndarray:
    """Compute and optionally smooth a boundary velocity curve.

    Parameters
    ----------
    positions : np.ndarray
        Mean boundary row position at each timepoint, shape ``(T,)``.
    time_points : np.ndarray
        Timepoints, shape ``(T,)``.
    sign : float
        +1 for the upper boundary (moves down → row increases as wound closes),
        -1 for the lower boundary (moves up → row decreases as wound closes).
        Multiplying by *sign* yields a positive-valued closing velocity.
    smooth : bool
        Apply Savitzky–Golay smoothing before returning.
    savgol_window : int
        SG filter window length (must be odd, ≤ T).
    savgol_poly : int
        SG filter polynomial order.

    Returns
    -------
    np.ndarray
        Velocity curve, shape ``(T,)``, peak-normalised to [0, 1].
    """
    from scipy.signal import savgol_filter

    v = sign * np.gradient(positions, time_points)
    if smooth and len(v) >= savgol_window:
        v = savgol_filter(v, savgol_window, savgol_poly)
    peak = np.abs(v).max()
    return v / peak if peak != 0 else v


def plot_wound_healing_dynamics(
    time_points: np.ndarray,
    wound_area: np.ndarray,
    output_path: str,
    upper_edges: Optional[List[np.ndarray]] = None,
    lower_edges: Optional[List[np.ndarray]] = None,
    smooth_velocity: bool = False,
    savgol_window: int = 5,
    savgol_poly: int = 2,
) -> None:
    """Plot normalised wound area and boundary closure velocities over time.

    Wound area A(t) is normalised to [0, 1] relative to t=0 and shown
    as the primary curve.  When *upper_edges* and *lower_edges* are
    provided, two separate velocity curves are computed:

    - **Upper boundary velocity** ``v_upper(t) = +d[ū(t)]/dt``
      where ``ū(t)`` is the column-mean upper edge row position.
      Positive values indicate the upper front moving downward (closing).

    - **Lower boundary velocity** ``v_lower(t) = -d[l̄(t)]/dt``
      where ``l̄(t)`` is the column-mean lower edge row position.
      Positive values indicate the lower front moving upward (closing).

    Both velocities are peak-normalised to [0, 1] for overlay on the
    same axis as the normalised area.  If boundary arrays are not
    supplied, a single area-based velocity ``-dA/dt`` is plotted instead.

    Parameters
    ----------
    time_points : array-like
        Timepoints (frame indices or hours), length T.
    wound_area : array-like
        Wound area values at each timepoint, length T.
    output_path : str
        Destination path for the PNG.
    upper_edges : list of np.ndarray, optional
        Per-timepoint upper boundary row arrays, each shape ``(W,)``.
        Length must equal T.
    lower_edges : list of np.ndarray, optional
        Per-timepoint lower boundary row arrays, each shape ``(W,)``.
        Length must equal T.
    smooth_velocity : bool
        Apply Savitzky–Golay smoothing to velocity curves.
    savgol_window : int
        SG filter window length (must be odd, ≤ T).
    savgol_poly : int
        SG filter polynomial order.
    """
    t = np.asarray(time_points, dtype=float)
    a = np.asarray(wound_area, dtype=float)

    # Normalise area to [0, 1] relative to t=0
    a_norm = a / a[0] if a[0] != 0 else a

    # ── Velocity curves ──────────────────────────────────────────────────────
    have_boundaries = (
        upper_edges is not None
        and lower_edges is not None
        and len(upper_edges) == len(t)
        and len(lower_edges) == len(t)
    )

    if have_boundaries:
        # Mean boundary position per timepoint (scalar per frame)
        u_mean = np.array([np.mean(e) for e in upper_edges])
        l_mean = np.array([np.mean(e) for e in lower_edges])

        # Upper front moves down (row ↑) → positive closing velocity
        v_upper = _boundary_velocity(
            u_mean, t, sign=+1.0,
            smooth=smooth_velocity,
            savgol_window=savgol_window,
            savgol_poly=savgol_poly,
        )
        # Lower front moves up (row ↓) → positive closing velocity
        v_lower = _boundary_velocity(
            l_mean, t, sign=-1.0,
            smooth=smooth_velocity,
            savgol_window=savgol_window,
            savgol_poly=savgol_poly,
        )
    else:
        from scipy.signal import savgol_filter
        v_area = -np.gradient(a_norm, t)
        if smooth_velocity and len(v_area) >= savgol_window:
            v_area = savgol_filter(v_area, savgol_window, savgol_poly)
        peak = np.abs(v_area).max()
        v_area = v_area / peak if peak != 0 else v_area

    # ── Figure ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(5.5, 4))

    amber  = "#C49A00"
    coral  = "#D94F3D"
    teal   = "#2CA89A"
    blue   = "#1f77b4"

    # Wound area — fill + line
    ax.fill_between(t, a_norm, alpha=0.18, color=amber, linewidth=0)
    ax.plot(t, a_norm, color=amber, linewidth=2.0, solid_capstyle="round")

    mid = len(t) // 2
    ax.text(
        t[mid], float(a_norm[mid]) + 0.05,
        "Wound Area $A(t)$",
        color=amber, fontsize=9, ha="center", va="bottom",
    )

    if have_boundaries:
        ax.plot(t, v_upper, color=coral, linewidth=2.0, solid_capstyle="round")
        ax.plot(t, v_lower, color=teal,  linewidth=2.0, solid_capstyle="round",
                linestyle="--")

        iu = int(np.argmax(v_upper))
        ax.text(
            t[iu], float(v_upper[iu]) + 0.05,
            "Upper velocity $v_{\\mathrm{up}}(t)$",
            color=coral, fontsize=9, ha="center", va="bottom",
        )
        il = int(np.argmax(v_lower))
        ax.text(
            t[il], float(v_lower[il]) + 0.05,
            "Lower velocity $v_{\\mathrm{lo}}(t)$",
            color=teal, fontsize=9, ha="center", va="bottom",
        )
    else:
        ax.plot(t, v_area, color=blue, linewidth=2.0, solid_capstyle="round")
        iv = int(np.argmax(v_area))
        ax.text(
            t[iv], float(v_area[iv]) + 0.05,
            "Closure Velocity",
            color=blue, fontsize=9, ha="center", va="bottom",
        )

    # ── Axes styling (Nature / minimalist) ──────────────────────────────────
    ax.set_xlabel("Time [h]", fontsize=10, labelpad=6)
    ax.tick_params(axis="both", which="both", length=3, width=0.8, labelsize=9)
    ax.set_ylim(-0.05, 1.20)
    ax.set_xlim(t[0], t[-1])

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)

    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, color="#cccccc", alpha=0.7)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Publication figure: wound boundary evolution
# ---------------------------------------------------------------------------

def _extract_wound_boundaries(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Extract upper and lower wound boundaries from a binary mask.

    For each column the upper edge is the row index of the first non-zero
    pixel and the lower edge is the row index of the last non-zero pixel.
    Columns with no wound pixels are filled by linear interpolation from
    neighbours so the curves remain continuous.

    Parameters
    ----------
    mask : np.ndarray
        2-D binary array, shape ``(H, W)``, dtype ``bool`` or ``uint8``.

    Returns
    -------
    upper : np.ndarray
        Row indices of the upper wound boundary, shape ``(W,)``.
    lower : np.ndarray
        Row indices of the lower wound boundary, shape ``(W,)``.
    """
    H, W = mask.shape
    upper = np.full(W, np.nan)
    lower = np.full(W, np.nan)

    m = mask.astype(bool)
    for col in range(W):
        rows = np.where(m[:, col])[0]
        if rows.size:
            upper[col] = rows[0]
            lower[col] = rows[-1]

    x = np.arange(W, dtype=float)

    # Interpolate over empty columns
    valid = ~np.isnan(upper)
    if valid.any():
        upper = np.interp(x, x[valid], upper[valid])
        lower = np.interp(x, x[valid], lower[valid])
    else:
        upper[:] = 0.0
        lower[:] = float(H)

    return upper, lower


def plot_wound_boundary_evolution(
    masks: List[np.ndarray],
    time_points: List[float],
    output_path: str,
    background_image: Optional[np.ndarray] = None,
    cmap_name: str = "turbo",
    alpha: float = 0.85,
    n_ticks: int = 6,
) -> None:
    """Visualise wound boundary evolution over time by overlaying edges.

    Each mask contributes an upper and a lower boundary curve, colour-coded
    from early (cool end of *cmap_name*) to late (warm end).  An optional
    background image (e.g. the t=0 brightfield frame) is rendered at
    reduced opacity to provide spatial context.

    A horizontal colorbar, sized to match the axes width, is placed below
    the image.  Only *n_ticks* evenly-spaced timepoint labels are shown to
    avoid label crowding with ~24 levels.

    Parameters
    ----------
    masks : list of np.ndarray
        Binary wound masks, shape ``(H, W)``, one per timepoint.
    time_points : list of float
        Corresponding timepoints (frame index or hours).
        Must be the same length as *masks*.
    output_path : str
        Destination path for the PNG.
    background_image : np.ndarray, optional
        Grayscale image, shape ``(H, W)``, used as a background rendered
        at alpha 0.7.  If ``None``, a plain white background is used.
    cmap_name : str
        Matplotlib colormap for temporal encoding.  ``"turbo"`` provides
        better perceptual separation than ``"plasma"`` for ~24 levels.
    alpha : float
        Boundary line opacity (0–1).
    n_ticks : int
        Number of evenly-spaced ticks shown on the colorbar (default 6).
    """
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    if len(masks) != len(time_points):
        raise ValueError(
            f"masks ({len(masks)}) and time_points ({len(time_points)}) "
            "must have the same length."
        )

    n = len(masks)
    t_arr = np.asarray(time_points, dtype=float)
    t_min, t_max = float(t_arr.min()), float(t_arr.max())

    # Map to full [0, 1] range so all 24 steps use the entire colormap
    if t_max > t_min:
        t_norm = (t_arr - t_min) / (t_max - t_min)
    else:
        t_norm = np.full(n, 0.5)

    cmap = plt.get_cmap(cmap_name)

    H, W = masks[0].shape[:2]
    x = np.arange(W)

    # ── Figure sized to image aspect ratio ──────────────────────────────────
    fig_w = 8.0
    fig_h = fig_w * H / W
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_facecolor("white")

    # ── Background image ─────────────────────────────────────────────────────
    if background_image is not None:
        bg = background_image.astype(np.float32)
        if bg.max() > 1.0:
            bg = bg / 255.0
        ax.imshow(bg, cmap="gray", vmin=0, vmax=1,
                  extent=[0, W - 1, H, 0], alpha=0.7, aspect="auto")

    # ── Boundary curves ──────────────────────────────────────────────────────
    for mask, c_val in zip(masks, t_norm):
        color = cmap(c_val)
        upper, lower = _extract_wound_boundaries(mask)
        ax.plot(x, upper, color=color, linewidth=1.4, alpha=alpha,
                solid_capstyle="round")
        ax.plot(x, lower, color=color, linewidth=1.4, alpha=alpha,
                solid_capstyle="round")

    # ── Axes styling ─────────────────────────────────────────────────────────
    ax.set_xlim(0, W - 1)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    # ── Horizontal colorbar — same width as the axes ──────────────────────
    norm = mcolors.Normalize(vmin=t_min, vmax=t_max)
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("bottom", size="4%", pad=0.08)
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")

    # Evenly-spaced tick subset
    tick_idx = np.round(np.linspace(0, n - 1, min(n_ticks, n))).astype(int)
    tick_vals = t_arr[tick_idx]
    cbar.set_ticks(tick_vals)
    cbar.set_ticklabels([
        f"{int(v)}" if v == int(v) else f"{v:.1f}"
        for v in tick_vals
    ])
    cbar.set_label("Timepoint", fontsize=9, labelpad=4)
    cbar.ax.tick_params(labelsize=8, length=3)
    cbar.outline.set_linewidth(0.6)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI / IDE entry point
# ---------------------------------------------------------------------------

# ── Edit these paths to run directly from the IDE ──────────────────────────
RESULTS_ROOT = Path(
    r"C:\Users\riccig01\OneDrive - The Mount Sinai Hospital"
    r"\Projects\fanny\WoundHealing\results_quantification_updated"
    r"\Quantification_kalman"
)
SAMPLE = "alk5i_c5_1-EXP2-alk5i"
OUTPUT_ROOT = None  # None → paper_publication/sequence/{SAMPLE}/
# ───────────────────────────────────────────────────────────────────────────


def main(
    sample: str = SAMPLE,
    results_root: Path = RESULTS_ROOT,
    output_root: Optional[Path] = OUTPUT_ROOT,
) -> Path:
    """Entry point for both CLI and IDE execution.

    Parameters
    ----------
    sample : str
        Sample folder name inside *results_root* (contains ``experiment.pkl``).
    results_root : Path
        Root directory containing per-sample subfolders.
    output_root : Path | None
        Override output location.  Defaults to
        ``paper_publication/sequence/{sample}/``.

    Returns
    -------
    Path
        The output directory.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # CLI override: first positional arg is the full pkl path
    if len(sys.argv) >= 2:
        pkl_path = Path(sys.argv[1])
    else:
        pkl_path = Path(results_root) / sample / "experiment.pkl"

    return generate_sequence(pkl_path, output_root=output_root)


if __name__ == "__main__":
    main()
