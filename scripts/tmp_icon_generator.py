"""
Temporary Icon Generator for Main Figure
=========================================
Run ONCE to produce five high-contrast PNGs illustrating the detection pipeline.

Icons generated (cropped to wound band):
  icon_1_variance.png       — Local variance map (inferno colormap)
  icon_2_edge_raw.png       — Per-column edge detection output (scatter dots)
  icon_3_edge_ransac.png    — RANSAC outlier-rejected edges
  icon_4_edge_savgol.png    — Savitzky-Golay smoothed edges
  icon_5_wound_mask.png     — Final binary wound mask overlay

Selection: trajectory with highest wound closure ratio (area_t0 - area_final) / area_t0,
t=0 frame, candesartan excluded.

Usage:
    cd C:\\Users\\riccig01\\OneDrive\\Projects\\MtSinai\\Vascbrain\\WoundDetectionBounds
    python scripts/tmp_icon_generator.py
"""

import pickle
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

# ---------------------------------------------------------------------------
# Path setup — project root on sys.path so library imports work
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.config import config                         # noqa: E402
from library.wound_standard.detector import WoundDetector  # noqa: E402
from library.core.types import WoundDetectorConfig        # noqa: E402

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

OUT_DIR: Path = _PROJECT_ROOT / "results" / "icons_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# DPI for saved icons
DPI: int = 300

# ---------------------------------------------------------------------------
# Sample selection mode
# ---------------------------------------------------------------------------
# Set SELECTION_MODE to choose which trajectory to use:
#   "ransac"   — 75th percentile RANSAC change (shows pipeline stages clearly)
#   "closure"  — highest wound closure ratio (shows wound healing dynamics)
SELECTION_MODE: str = "closure"

# Commented-out reference: the original sample used for pipeline illustration
# ORIGINAL_SAMPLE = "alk5i_e12_1-EXP2-alk5i"  # RANSAC score 8.1 px, 31.5% coverage at t=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_icon(fig: plt.Figure, name: str) -> Path:
    out = OUT_DIR / name
    fig.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return out


def _full_figure(img: np.ndarray, cmap: str = "gray",
                 vmin: float = 0.0, vmax: float = 1.0) -> tuple:
    """Figure sized to the image aspect ratio, no axes, no padding."""
    H, W = img.shape[:2]
    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
    ax.imshow(img, cmap=cmap, aspect="auto", interpolation="nearest",
              vmin=vmin, vmax=vmax)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig, ax


# ---------------------------------------------------------------------------
# Step 1 — Load trajectories and select best sample
# ---------------------------------------------------------------------------

def _ransac_change_score(img_raw: np.ndarray, detector: WoundDetector) -> float:
    """
    Run pipeline stages 1–4 on img_raw and return the mean absolute
    deviation between raw and RANSAC-cleaned edges (upper + lower combined).
    Higher = more outliers corrected by RANSAC.
    """
    import cv2
    cfg = detector.config

    img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY) if img_raw.ndim == 3 else img_raw
    img_f = img_gray.astype(np.float32)
    if img_f.max() > 1.0:
        img_f /= 255.0

    variance_map = detector._compute_local_variance(img_f, cfg.variance_window)
    variance_smooth = gaussian_filter1d(
        gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
        cfg.variance_sigma, axis=1,
    )
    y_min, y_max, y_center = detector._detect_y_band(variance_smooth)
    upper_raw, lower_raw = detector._extract_edges_per_column(
        variance_smooth, y_min, y_max, y_center
    )
    upper_ransac, lower_ransac = detector._ransac_smooth_edges(upper_raw, lower_raw)

    score = (
        np.nanmean(np.abs(upper_raw - upper_ransac)) +
        np.nanmean(np.abs(lower_raw - lower_ransac))
    )
    return float(score)


def load_best_frame():
    """
    Return (img_raw_uint8, traj_key) for a QC-valid t=0 trajectory.
    Selection mode controlled by SELECTION_MODE:
      "ransac"  — 75th percentile RANSAC change (shows pipeline stages)
      "closure" — highest wound closure ratio t=0 → t=24 (shows healing)
    Candesartan trajectories are excluded.
    """
    traj_path = config["trajectories_pickle"]
    print(f"Loading trajectories from:\n  {traj_path}")

    with traj_path.open("rb") as f:
        trajectories: dict = pickle.load(f)

    print(f"  {len(trajectories)} trajectories loaded.")

    # Collect all QC-valid t=0 candidates with their wound areas and closure
    candidates = []
    for key, traj_data in trajectories.items():
        if "candasertan" in key.lower() or "candesartan" in key.lower():
            continue
        results = traj_data.get("results", [])
        t0 = next((r for r in results if r.get("t") == 0), None)
        if t0 is None or "img_raw" not in t0:
            continue
        if not t0.get("qc", {}).get("valid", False):
            continue

        area_t0 = t0.get("area", 0)
        # Find final timepoint
        final = max((r for r in results if "area" in r), key=lambda r: r.get("t", -1), default=None)
        area_final = final.get("area", area_t0) if final else area_t0
        closure_ratio = (area_t0 - area_final) / (area_t0 + 1e-6) if area_t0 > 0 else 0

        candidates.append((key, t0["img_raw"], area_t0, closure_ratio))

    print(f"  {len(candidates)} QC-valid t=0 candidates.")

    # Keep only candidates with wound area >= median
    areas = [c[2] for c in candidates]
    area_threshold = float(np.median(areas))
    large_wound = [(k, img, a, c) for k, img, a, c in candidates if a >= area_threshold]
    print(f"  {len(large_wound)} candidates with area >= median ({area_threshold:,.0f} px²).")

    if SELECTION_MODE == "closure":
        # Sort by closure ratio (descending) and pick the top one
        large_wound.sort(key=lambda x: x[3], reverse=True)
        best_key, best_img, area_t0, closure = large_wound[0]
        print(f"\nSelected trajectory : {best_key}")
        print(f"Closure ratio       : {closure*100:.1f}% (area {area_t0:,.0f} px -> {area_t0*(1-closure):,.0f} px)")
        print(f"Image shape         : {best_img.shape}, dtype={best_img.dtype}")
        return best_img, best_key

    else:  # RANSAC mode (default)
        detector = WoundDetector(WoundDetectorConfig())
        scored = []
        for key, img_raw, area, closure in large_wound:
            try:
                score = _ransac_change_score(img_raw, detector)
                scored.append((score, key, img_raw))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0])
        scores = [s[0] for s in scored]
        print(f"  RANSAC score range: {scores[0]:.1f} – {scores[-1]:.1f} px")

        # Pick 75th percentile: strong but not extreme correction
        idx = int(len(scored) * 0.75)
        best_score, best_key, best_img = scored[idx]

        print(f"\nSelected trajectory : {best_key}")
        print(f"RANSAC change score : {best_score:.2f} px  (75th pct of {len(scored)} candidates)")
        print(f"Image shape         : {best_img.shape}, dtype={best_img.dtype}")
        return best_img, best_key


# ---------------------------------------------------------------------------
# Step 2 — Re-run detector step by step to capture intermediates
# ---------------------------------------------------------------------------

def run_pipeline_steps(img_raw: np.ndarray):
    """
    Reproduce exactly what WoundDetector.detect() does internally,
    capturing each intermediate without modifying the library.

    Returns dict with all named intermediates plus crop coordinates.
    """
    detector = WoundDetector(WoundDetectorConfig())
    cfg = detector.config

    H, W = img_raw.shape[:2]

    # Ensure 2-D grayscale
    import cv2
    if img_raw.ndim == 3:
        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = img_raw

    # Normalize to float [0, 1] — same logic as detect()
    img_f = img_gray.astype(np.float32)
    if img_f.max() > 1.0:
        img_f = img_f / 255.0

    # Stage 1 — Local variance
    variance_map = detector._compute_local_variance(img_f, cfg.variance_window)
    variance_smooth = gaussian_filter1d(
        gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
        cfg.variance_sigma, axis=1,
    )

    # Stage 2 — Y-band detection
    y_min, y_max, y_center = detector._detect_y_band(variance_smooth)

    # Stage 3 — Per-column edge extraction
    upper_raw, lower_raw = detector._extract_edges_per_column(
        variance_smooth, y_min, y_max, y_center
    )

    # Stage 4 — RANSAC outlier rejection
    upper_ransac, lower_ransac = detector._ransac_smooth_edges(upper_raw, lower_raw)

    # Stage 5 — Savitzky-Golay smoothing
    upper_sg = detector._savgol_smooth(upper_ransac)
    lower_sg = detector._savgol_smooth(lower_ransac)

    # Stage 6 — Final wound mask
    mask = detector._edges_to_mask(upper_sg, lower_sg, H, W)

    print(f"\nPipeline intermediates captured:")
    print(f"  Image          : ({H}, {W})")
    print(f"  Y-band         : y_min={y_min}, y_max={y_max}, y_center={y_center}")
    print(f"  Mask coverage  : {mask.mean()*100:.1f}% of pixels")

    return {
        "img_f": img_f,
        "img_gray": img_gray,
        "variance_smooth": variance_smooth,
        "y_min": y_min, "y_max": y_max, "y_center": y_center,
        "upper_raw": upper_raw, "lower_raw": lower_raw,
        "upper_ransac": upper_ransac, "lower_ransac": lower_ransac,
        "upper_sg": upper_sg, "lower_sg": lower_sg,
        "mask": mask,
        "H": H, "W": W,
    }


# ---------------------------------------------------------------------------
# Step 3 — Icon renderers
# ---------------------------------------------------------------------------

def _edge_overlay_figure(
    img_f: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray,
    line: bool = False,
) -> plt.Figure:
    """
    Full grayscale image with upper (red) and lower (blue) edge overlaid.

    Parameters
    ----------
    img_f : float [0,1] full image
    upper, lower : full-width edge arrays (row coords in image space)
    line : solid lines when True; scatter dots when False
    """
    H, W = img_f.shape
    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
    ax.imshow(img_f, cmap="gray", aspect="auto",
              interpolation="nearest", vmin=0, vmax=1)

    x = np.arange(W)
    if line:
        ax.plot(x, upper, color="#FF0000", linewidth=2.5, alpha=1.0)
        ax.plot(x, lower, color="#00CCFF", linewidth=2.5, alpha=1.0)
    else:
        ax.scatter(x, upper, s=3, color="#FF0000", alpha=1.0, linewidths=0)
        ax.scatter(x, lower, s=3, color="#00CCFF", alpha=1.0, linewidths=0)

    ax.set_xlim(0, W - 1)
    ax.set_ylim(H - 1, 0)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig


def icon_raw_image(p: dict) -> Path:
    """Icon 0: plain grayscale image, no overlays, no markers."""
    H, W = p["img_f"].shape
    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
    ax.imshow(p["img_f"], cmap="gray", aspect="auto",
              interpolation="nearest", vmin=0, vmax=1)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return _save_icon(fig, "icon_0_raw.png")


def icon_variance(p: dict) -> Path:
    """
    Icon 1: local variance map, full image.

    Uses variance_smooth directly (sigma=2 post-smoothing), same data that
    the pipeline debug plot renders. Clip to 99th percentile to stretch the
    colormap over the biologically relevant range.
    viridis: low variance (wound, smooth) → dark purple;
             high variance (cells, textured) → bright yellow.
    """
    vm = p["variance_smooth"]
    vmax_clip = np.percentile(vm, 99)
    vm_norm = np.clip(vm, 0, vmax_clip) / (vmax_clip + 1e-12)

    H, W = vm_norm.shape
    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
    ax.imshow(vm_norm, cmap="viridis", aspect="auto",
              interpolation="nearest", vmin=0, vmax=1)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return _save_icon(fig, "icon_1_variance.png")


def icon_edge_raw(p: dict) -> Path:
    """Icon 2: raw per-column edge detection output on full image."""
    fig = _edge_overlay_figure(
        p["img_f"], p["upper_raw"], p["lower_raw"], line=False
    )
    return _save_icon(fig, "icon_2_edge_raw.png")


def icon_edge_ransac(p: dict) -> Path:
    """Icon 3: RANSAC outlier-rejected edges on full image."""
    fig = _edge_overlay_figure(
        p["img_f"], p["upper_ransac"], p["lower_ransac"], line=False
    )
    return _save_icon(fig, "icon_3_edge_ransac.png")


def icon_edge_savgol(p: dict) -> Path:
    """Icon 4: Savitzky-Golay smoothed edges on full image (solid lines)."""
    fig = _edge_overlay_figure(
        p["img_f"], p["upper_sg"], p["lower_sg"], line=True
    )
    return _save_icon(fig, "icon_4_edge_savgol.png")


def icon_wound_mask(p: dict) -> Path:
    """Icon 5: wound mask overlay (cyan fill) on full grayscale image."""
    img_f = p["img_f"]
    mask = p["mask"]

    H, W = img_f.shape
    rgb = np.stack([img_f, img_f, img_f], axis=-1)
    wound_px = mask > 0
    # Dim non-wound background; paint wound region in saturated cyan
    rgb[~wound_px, :] *= 0.55
    rgb[wound_px, 0] = np.clip(img_f[wound_px] * 0.2, 0, 1)            # red   → suppressed
    rgb[wound_px, 1] = np.clip(img_f[wound_px] * 0.5 + 0.5, 0, 1)     # green → boosted
    rgb[wound_px, 2] = np.clip(img_f[wound_px] * 0.5 + 0.9, 0, 1)     # blue  → boosted
    rgb = np.clip(rgb, 0, 1)

    fig_w = 4.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
    ax.imshow(rgb, aspect="auto", interpolation="nearest")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return _save_icon(fig, "icon_5_wound_mask.png")


def icon_variance_profile(p: dict) -> Path:
    """
    Icon 6: variance map with row-sum profile showing the Y-band valley.
    Two-panel figure: top = variance heatmap, bottom = row profile with detected band shaded.
    """
    vm = p["variance_smooth"]
    y_min, y_max = p["y_min"], p["y_max"]
    H, W = vm.shape

    # Prepare variance for heatmap (clip to 99th percentile)
    vmax_clip = np.percentile(vm, 99)
    vm_norm = np.clip(vm, 0, vmax_clip) / (vmax_clip + 1e-12)

    # Compute row-sum profile (mean variance per row)
    row_profile = vm.mean(axis=1)
    row_profile_norm = np.clip(row_profile, 0, np.percentile(row_profile, 99)) / (np.percentile(row_profile, 99) + 1e-12)

    # Two-panel layout: heatmap on top, profile below
    fig_w = 4.0
    fig, (ax_hm, ax_prof) = plt.subplots(2, 1, figsize=(fig_w, fig_w * 1.3),
                                          gridspec_kw={"height_ratios": [3, 1]})

    # Panel 1: variance heatmap
    ax_hm.imshow(vm_norm, cmap="viridis", aspect="auto", interpolation="nearest", vmin=0, vmax=1)
    # Shade the detected Y-band
    ax_hm.axhspan(y_min, y_max, alpha=0.15, color="red", linewidth=0)
    ax_hm.set_xlim(0, W - 1)
    ax_hm.set_ylim(H - 1, 0)
    ax_hm.axis("off")

    # Panel 2: row profile
    y_coords = np.arange(len(row_profile))
    ax_prof.plot(y_coords, row_profile_norm, color="white", linewidth=1.5)
    ax_prof.fill_between(y_coords, 0, row_profile_norm, alpha=0.3, color="white")
    # Shade the detected band
    ax_prof.axvspan(y_min, y_max, alpha=0.2, color="red", linewidth=0)
    ax_prof.set_xlim(0, H - 1)
    ax_prof.set_ylim(0, 1.1)
    ax_prof.set_facecolor("#1a1a1a")
    ax_prof.spines["top"].set_visible(False)
    ax_prof.spines["right"].set_visible(False)
    ax_prof.spines["left"].set_visible(False)
    ax_prof.set_xticks([])
    ax_prof.set_yticks([])
    ax_prof.spines["bottom"].set_color("white")
    ax_prof.spines["bottom"].set_linewidth(0.5)

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0.1)
    return _save_icon(fig, "icon_6_variance_profile.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_distribution_profile_icons(traj_key: str, trajectories: dict) -> list:
    """
    Render variance profile icons (heatmap + row-sum) for timepoints t=0, 6, 12, 18, 24.
    Returns list of saved file paths.
    """
    if traj_key not in trajectories:
        print(f"Warning: trajectory key '{traj_key}' not found in trajectories dict")
        return []

    traj_data = trajectories[traj_key]
    results = traj_data.get("results", [])

    target_times = [0, 6, 12, 18, 24]
    results_by_t = {r.get("t"): r for r in results if "t" in r and "img_raw" in r}
    available_times = sorted(results_by_t.keys())

    paths = []
    for target_t in target_times:
        if target_t in results_by_t:
            actual_t = target_t
        else:
            closest = min(available_times, key=lambda x: abs(x - target_t))
            actual_t = closest

        result = results_by_t[actual_t]
        img_raw = result.get("img_raw")
        if img_raw is None:
            continue

        # Compute variance and Y-band for this frame
        import cv2
        detector = WoundDetector(WoundDetectorConfig())
        cfg = detector.config

        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY) if img_raw.ndim == 3 else img_raw
        img_f = img_gray.astype(np.float32)
        if img_f.max() > 1.0:
            img_f = img_f / 255.0

        H, W = img_f.shape
        variance_map = detector._compute_local_variance(img_f, cfg.variance_window)
        variance_smooth = gaussian_filter1d(
            gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
            cfg.variance_sigma, axis=1,
        )
        y_min, y_max, y_center = detector._detect_y_band(variance_smooth)

        # Render variance profile (heatmap + row-sum)
        vmax_clip = np.percentile(variance_smooth, 99)
        vm_norm = np.clip(variance_smooth, 0, vmax_clip) / (vmax_clip + 1e-12)
        row_profile = variance_smooth.mean(axis=1)
        row_profile_norm = np.clip(row_profile, 0, np.percentile(row_profile, 99)) / (np.percentile(row_profile, 99) + 1e-12)

        fig_w = 4.0
        fig, (ax_hm, ax_prof) = plt.subplots(2, 1, figsize=(fig_w, fig_w * 1.3),
                                              gridspec_kw={"height_ratios": [3, 1]})

        ax_hm.imshow(vm_norm, cmap="viridis", aspect="auto", interpolation="nearest", vmin=0, vmax=1)
        ax_hm.axhspan(y_min, y_max, alpha=0.15, color="red", linewidth=0)
        ax_hm.set_xlim(0, W - 1)
        ax_hm.set_ylim(H - 1, 0)
        ax_hm.axis("off")

        y_coords = np.arange(len(row_profile))
        ax_prof.plot(y_coords, row_profile_norm, color="white", linewidth=1.5)
        ax_prof.fill_between(y_coords, 0, row_profile_norm, alpha=0.3, color="white")
        ax_prof.axvspan(y_min, y_max, alpha=0.2, color="red", linewidth=0)
        ax_prof.set_xlim(0, H - 1)
        ax_prof.set_ylim(0, 1.1)
        ax_prof.set_facecolor("#1a1a1a")
        ax_prof.spines["top"].set_visible(False)
        ax_prof.spines["right"].set_visible(False)
        ax_prof.spines["left"].set_visible(False)
        ax_prof.set_xticks([])
        ax_prof.set_yticks([])
        ax_prof.spines["bottom"].set_color("white")
        ax_prof.spines["bottom"].set_linewidth(0.5)

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0.1)

        fname = f"icon_dist_profile_t{actual_t}.png"
        out_path = OUT_DIR / fname
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

        print(f"  t={actual_t}: variance profile")
        paths.append(out_path)

    return paths


def generate_distribution_icons(traj_key: str, trajectories: dict) -> list:
    """
    Render wound mask overlays for timepoints t=0, 6, 12, 18, 24.
    Returns list of saved file paths.
    """
    if traj_key not in trajectories:
        print(f"Warning: trajectory key '{traj_key}' not found in trajectories dict")
        return []

    traj_data = trajectories[traj_key]
    results = traj_data.get("results", [])

    # Desired timepoints
    target_times = [0, 6, 12, 18, 24]

    # Build a dict of available results by timepoint
    results_by_t = {r.get("t"): r for r in results if "t" in r and "img_raw" in r}
    available_times = sorted(results_by_t.keys())

    print(f"\nAvailable timepoints: {available_times}")

    paths = []
    for target_t in target_times:
        # Find the closest available timepoint (prefer exact match, otherwise closest)
        if target_t in results_by_t:
            actual_t = target_t
        else:
            # Find closest
            closest = min(available_times, key=lambda x: abs(x - target_t))
            actual_t = closest

        result = results_by_t[actual_t]
        img_raw = result.get("img_raw")
        if img_raw is None:
            print(f"  t={target_t}: no image data, skipping")
            continue

        # Compute the wound mask for this frame using the detector
        import cv2
        detector = WoundDetector(WoundDetectorConfig())
        cfg = detector.config

        img_gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY) if img_raw.ndim == 3 else img_raw
        img_f = img_gray.astype(np.float32)
        if img_f.max() > 1.0:
            img_f = img_f / 255.0

        H, W = img_f.shape
        variance_map = detector._compute_local_variance(img_f, cfg.variance_window)
        variance_smooth = gaussian_filter1d(
            gaussian_filter1d(variance_map, cfg.variance_sigma, axis=0),
            cfg.variance_sigma, axis=1,
        )
        y_min, y_max, y_center = detector._detect_y_band(variance_smooth)
        upper_raw, lower_raw = detector._extract_edges_per_column(
            variance_smooth, y_min, y_max, y_center
        )
        upper_ransac, lower_ransac = detector._ransac_smooth_edges(upper_raw, lower_raw)
        upper_sg = detector._savgol_smooth(upper_ransac)
        lower_sg = detector._savgol_smooth(lower_ransac)
        mask = detector._edges_to_mask(upper_sg, lower_sg, H, W)

        # Render wound mask overlay
        rgb = np.stack([img_f, img_f, img_f], axis=-1)
        wound_px = mask > 0
        rgb[~wound_px, :] *= 0.55
        rgb[wound_px, 0] = np.clip(img_f[wound_px] * 0.2, 0, 1)
        rgb[wound_px, 1] = np.clip(img_f[wound_px] * 0.5 + 0.5, 0, 1)
        rgb[wound_px, 2] = np.clip(img_f[wound_px] * 0.5 + 0.9, 0, 1)
        rgb = np.clip(rgb, 0, 1)

        fig_w = 4.0
        fig, ax = plt.subplots(figsize=(fig_w, fig_w * H / W))
        ax.imshow(rgb, aspect="auto", interpolation="nearest")
        ax.axis("off")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        fname = f"icon_dist_t{actual_t}.png"
        out_path = OUT_DIR / fname
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

        coverage = mask.mean() * 100
        print(f"  t={actual_t}: mask coverage {coverage:.1f}%")
        paths.append(out_path)

    return paths


def main():
    print("=" * 60)
    print("Wound pipeline icon generator")
    print("=" * 60)

    img_raw, traj_key = load_best_frame()
    pipeline = run_pipeline_steps(img_raw)

    print("\nRendering pipeline stage icons...")
    paths = [
        icon_raw_image(pipeline),
        icon_variance(pipeline),
        icon_variance_profile(pipeline),
        icon_edge_raw(pipeline),
        icon_edge_ransac(pipeline),
        icon_edge_savgol(pipeline),
        icon_wound_mask(pipeline),
    ]

    print("Saved pipeline icons:")
    for p in paths:
        print(f"  {p}")

    # Load trajectories for distribution icons
    traj_path = config["trajectories_pickle"]
    with traj_path.open("rb") as f:
        trajectories: dict = pickle.load(f)

    print("\nRendering distribution icons (5 timepoints)...")
    dist_paths = generate_distribution_icons(traj_key, trajectories)

    print("Saved distribution wound-mask icons:")
    for p in dist_paths:
        print(f"  {p}")

    print("\nRendering distribution variance-profile icons (5 timepoints)...")
    dist_profile_paths = generate_distribution_profile_icons(traj_key, trajectories)

    print("Saved distribution variance-profile icons:")
    for p in dist_profile_paths:
        print(f"  {p}")

    print(f"\nAll icons written to: {OUT_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
