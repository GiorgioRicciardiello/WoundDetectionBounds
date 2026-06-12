"""
Synthetic Wound Closing Demonstration
======================================
Create synthetic variance profiles that show a wound band progressively
narrowing as it closes over time. Purely illustrative—not using real data.

Usage:
    cd C:\\Users\\riccig01\\OneDrive\\Projects\\MtSinai\\Vascbrain\\WoundDetectionBounds
    python scripts/synthetic_closing_demo.py
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR: Path = _PROJECT_ROOT / "results" / "synthetic_closing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI: int = 300


def create_synthetic_variance_profile(H: int, band_top: int, band_bottom: int,
                                      noise_level: float = 0.05) -> np.ndarray:
    """
    Create a synthetic variance map with:
      - High variance (cells) in rows 0..band_top and band_bottom..H
      - Low variance (wound) in rows band_top..band_bottom

    Parameters
    ----------
    H : height of image
    band_top, band_bottom : row indices defining the wound band
    noise_level : small random noise to make it more realistic
    """
    profile = np.ones(H) * 0.7  # baseline cell variance
    profile[band_top:band_bottom] = 0.15  # wound (low variance)

    # Add smooth gradient at edges
    edge_width = 20
    for i in range(edge_width):
        alpha = i / edge_width
        profile[band_top - edge_width + i] = 0.7 * (1 - alpha) + 0.15 * alpha
        profile[band_bottom + i] = 0.15 * (1 - alpha) + 0.7 * alpha

    # Add noise
    profile += np.random.normal(0, noise_level, H)
    profile = np.clip(profile, 0.05, 1.0)
    return profile


def render_profile_icon(profile: np.ndarray, band_top: int, band_bottom: int,
                        title_suffix: str = "") -> plt.Figure:
    """
    Create a 2D variance map + row profile visualization.
    """
    H = len(profile)
    W = 300  # synthetic width

    # Tile the 1D profile into a 2D heatmap
    variance_2d = np.tile(profile[:, np.newaxis], (1, W))

    # Normalize for display
    vmax = np.percentile(variance_2d, 99)
    vm_norm = np.clip(variance_2d, 0, vmax) / (vmax + 1e-12)

    # Normalize profile
    profile_norm = np.clip(profile, 0, np.percentile(profile, 99)) / (np.percentile(profile, 99) + 1e-12)

    # Create figure
    fig_w = 4.0
    fig, (ax_hm, ax_prof) = plt.subplots(2, 1, figsize=(fig_w, fig_w * 1.3),
                                          gridspec_kw={"height_ratios": [3, 1]})

    # Panel 1: heatmap
    ax_hm.imshow(vm_norm, cmap="viridis", aspect="auto", interpolation="nearest", vmin=0, vmax=1)
    ax_hm.axhspan(band_top, band_bottom, alpha=0.25, color="red", linewidth=2, edgecolor="red")
    ax_hm.set_xlim(0, W - 1)
    ax_hm.set_ylim(H - 1, 0)
    ax_hm.set_ylabel("Row (pixels)", fontsize=8, color="white")
    ax_hm.tick_params(colors="white", labelsize=6)
    ax_hm.spines["bottom"].set_visible(False)
    ax_hm.set_xticklabels([])

    # Panel 2: profile
    y_coords = np.arange(H)
    ax_prof.plot(y_coords, profile_norm, color="white", linewidth=1.5)
    ax_prof.fill_between(y_coords, 0, profile_norm, alpha=0.3, color="white")
    ax_prof.axvspan(band_top, band_bottom, alpha=0.25, color="red", linewidth=2, edgecolor="red")
    ax_prof.set_xlim(0, H - 1)
    ax_prof.set_ylim(0, 1.1)
    ax_prof.set_facecolor("#1a1a1a")
    ax_prof.set_xlabel("Row (pixels)", fontsize=8, color="white")
    ax_prof.set_ylabel("Variance", fontsize=8, color="white")
    ax_prof.tick_params(colors="white", labelsize=6)
    ax_prof.spines["top"].set_visible(False)
    ax_prof.spines["right"].set_visible(False)
    ax_prof.spines["left"].set_visible(False)
    ax_prof.spines["bottom"].set_color("white")
    ax_prof.spines["bottom"].set_linewidth(0.5)

    fig.suptitle(f"Synthetic Wound Closing{title_suffix}", fontsize=10, color="white")
    fig.patch.set_facecolor("#0a0a0a")
    fig.subplots_adjust(left=0.08, right=1, top=0.95, bottom=0.08, hspace=0.15)

    return fig, band_bottom - band_top


def main():
    print("=" * 60)
    print("Synthetic wound closing demonstration")
    print("=" * 60)

    H = 900  # same as real images
    np.random.seed(42)

    # Define wound band for each timepoint: progressively narrowing
    timepoints = {
        0:  (250, 650),   # t=0: band width = 400 px
        6:  (280, 620),   # t=6: band width = 340 px (closing)
        12: (310, 590),   # t=12: band width = 280 px
        18: (340, 560),   # t=18: band width = 220 px
        24: (370, 530),   # t=24: band width = 160 px (mostly closed)
    }

    print(f"\nGenerating {len(timepoints)} wound-closing profiles...")
    print("Wound band width (pixels):")

    for t, (band_top, band_bottom) in timepoints.items():
        band_width = band_bottom - band_top
        print(f"  t={t:2d}: {band_width} px  (y={band_top}..{band_bottom})")

        # Create synthetic profile
        profile = create_synthetic_variance_profile(H, band_top, band_bottom)

        # Render and save
        fig, _ = render_profile_icon(profile, band_top, band_bottom, title_suffix=f" (t={t}h, width={band_width}px)")

        out_path = OUT_DIR / f"synthetic_closing_t{t}.png"
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="#0a0a0a")
        plt.close(fig)

        print(f"     Saved: {out_path.name}")

    # Generate no-wound example: uniform high variance
    print("\nGenerating no-wound profile (control)...")
    profile_no_wound = np.ones(H) * 0.65 + np.random.normal(0, 0.05, H)
    profile_no_wound = np.clip(profile_no_wound, 0.05, 1.0)

    # Render no-wound icon (no band to highlight)
    H_nw = len(profile_no_wound)
    W = 300
    variance_2d = np.tile(profile_no_wound[:, np.newaxis], (1, W))
    vmax = np.percentile(variance_2d, 99)
    vm_norm = np.clip(variance_2d, 0, vmax) / (vmax + 1e-12)
    profile_norm = np.clip(profile_no_wound, 0, np.percentile(profile_no_wound, 99)) / (np.percentile(profile_no_wound, 99) + 1e-12)

    fig_w = 4.0
    fig, (ax_hm, ax_prof) = plt.subplots(2, 1, figsize=(fig_w, fig_w * 1.3),
                                          gridspec_kw={"height_ratios": [3, 1]})

    ax_hm.imshow(vm_norm, cmap="viridis", aspect="auto", interpolation="nearest", vmin=0, vmax=1)
    ax_hm.text(150, H_nw/2, "NO WOUND\n(uniform monolayer)", ha="center", va="center",
               fontsize=12, color="yellow", weight="bold", alpha=0.7)
    ax_hm.set_xlim(0, W - 1)
    ax_hm.set_ylim(H_nw - 1, 0)
    ax_hm.set_ylabel("Row (pixels)", fontsize=8, color="white")
    ax_hm.tick_params(colors="white", labelsize=6)
    ax_hm.spines["bottom"].set_visible(False)
    ax_hm.set_xticklabels([])

    y_coords = np.arange(H_nw)
    ax_prof.plot(y_coords, profile_norm, color="white", linewidth=1.5)
    ax_prof.fill_between(y_coords, 0, profile_norm, alpha=0.3, color="white")
    ax_prof.axhline(profile_norm.mean(), color="yellow", linestyle="--", linewidth=1.5, alpha=0.7, label="Mean variance (no valley)")
    ax_prof.set_xlim(0, H_nw - 1)
    ax_prof.set_ylim(0, 1.1)
    ax_prof.set_facecolor("#1a1a1a")
    ax_prof.set_xlabel("Row (pixels)", fontsize=8, color="white")
    ax_prof.set_ylabel("Variance", fontsize=8, color="white")
    ax_prof.tick_params(colors="white", labelsize=6)
    ax_prof.spines["top"].set_visible(False)
    ax_prof.spines["right"].set_visible(False)
    ax_prof.spines["left"].set_visible(False)
    ax_prof.spines["bottom"].set_color("white")
    ax_prof.spines["bottom"].set_linewidth(0.5)
    ax_prof.legend(loc="upper right", fontsize=7, facecolor="#1a1a1a", edgecolor="white")

    fig.suptitle("No Wound (Control: uniform monolayer)", fontsize=10, color="white")
    fig.patch.set_facecolor("#0a0a0a")
    fig.subplots_adjust(left=0.08, right=1, top=0.95, bottom=0.08, hspace=0.15)

    out_path_no_wound = OUT_DIR / "synthetic_no_wound.png"
    fig.savefig(out_path_no_wound, dpi=DPI, bbox_inches="tight", facecolor="#0a0a0a")
    plt.close(fig)

    print(f"  Saved: synthetic_no_wound.png (flat variance, no detectable valley)")

    print(f"\nAll synthetic icons written to: {OUT_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
