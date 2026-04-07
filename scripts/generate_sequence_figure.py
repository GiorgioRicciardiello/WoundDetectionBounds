#!/usr/bin/env python3
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np


def _load_img_safe(path):
    """Load image or return None if missing."""
    if not Path(path).exists():
        return None
    try:
        return mpimg.imread(path)
    except Exception:
        return None


def _format_time_label(t):
    return f"time = {t}h"


def plot_wound_sequence(
    sequence_root: str,
    cell_name: str,
    timepoints: list,
    output_path: str,
    dpi: int = 300,
):
    """
    Generate a styled multi-panel figure for wound healing pipeline.

    Parameters
    ----------
    sequence_root : str
        Root folder containing sequences
    cell_name : str
        Folder name of the sequence
    timepoints : list[int]
        Time indices to visualize (e.g., [0, 6, 12, 20])
    output_path : str
        Full output path (including filename)
    dpi : int
        Figure resolution
    """

    base_path = Path(sequence_root) / cell_name

    # Panel definitions (row-wise)
    panel_files = [
        "panel_1_original.png",
        "panel_2_variance_map.png",
        "panel_3_y_profile.png",
        "panel_5_smooth_edges.png",
        "panel_6_mask_overlay.png",
    ]

    n_cols = len(timepoints)
    n_rows = len(panel_files)

    # --- Figure setup (clean scientific style) ---
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(3.2 * n_cols, 2.4 * n_rows),
        dpi=dpi
    )

    if n_cols == 1:
        axes = np.expand_dims(axes, axis=1)

    # --- Row labels ---
    row_labels = [
        "Raw Image",
        "Variance Map",
        "Y-Profile",
        "Smoothed Edges",
        "Final Mask",
    ]

    # --- Load and plot ---
    for col_idx, t in enumerate(timepoints):

        t_folder = base_path / f"t_{str(t).zfill(2)}"

        for row_idx, panel_name in enumerate(panel_files):

            ax = axes[row_idx, col_idx]

            img_path = t_folder / panel_name
            img = _load_img_safe(img_path)

            if img is not None:
                ax.imshow(img, cmap='gray')
            else:
                ax.text(
                    0.5, 0.5,
                    "Missing",
                    ha='center', va='center',
                    fontsize=8
                )

            ax.axis("off")

            # Column titles
            if row_idx == 0:
                ax.set_title(
                    _format_time_label(t),
                    fontsize=11,
                    pad=8,
                    fontweight='medium'
                )

            # Row labels
            if col_idx == 0:
                ax.set_ylabel(
                    row_labels[row_idx],
                    fontsize=10,
                    rotation=0,
                    labelpad=50,
                    va='center'
                )

    # --- Section separators (visual grouping) ---
    for row_idx in range(n_rows):
        for col_idx in range(n_cols):
            ax = axes[row_idx, col_idx]
            for spine in ax.spines.values():
                spine.set_visible(False)

    # --- Global title ---
    fig.suptitle(
        "Automated Scratch-Wound Quantification Pipeline",
        fontsize=14,
        y=0.995,
        fontweight='bold'
    )

    # --- Tight layout ---
    plt.subplots_adjust(
        left=0.12,
        right=0.98,
        top=0.93,
        bottom=0.05,
        wspace=0.05,
        hspace=0.15
    )

    # --- Save ---
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=dpi)
    plt.close(fig)


# =========================
# Example usage
# =========================
if __name__ == "__main__":

    sequence_root = r"C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\paper_publication\sequence"
    cell_name = "alk5i_c5_1-EXP2-alk5i"
    timepoints = [0, 6, 24]

    output_path = r"C:\Users\riccig01\OneDrive\Projects\MtSinai\Vascbrain\WoundDetectionBounds\paper_publication\sequence\wound_pipeline_figure.png"

    plot_wound_sequence(
        sequence_root=sequence_root,
        cell_name=cell_name,
        timepoints=timepoints,
        output_path=output_path
    )