"""
woundtrack.plots
================

Optional debugging visualizations.
Never required by core logic - purely for visual inspection.
"""

import numpy as np

__all__ = [
    "debug_plot_wound_edges_overlay",
]

def debug_plot_wound_edges_overlay(
    img0: np.ndarray,
    y0_upper: np.ndarray,
    y0_lower: np.ndarray,
    yT_upper: np.ndarray,
    yT_lower: np.ndarray,
    traj_key: str,
    t_used: float,
    img_alpha: float = 0.25,
    line_width: float = 1.5,
) -> None:
    """
    Single-panel debug plot:
    - background: img0 (transparent)
    - lines: upper/lower at t=0 and t=T
    - shaded regions between (t=0 <-> T) for upper and lower

    Notes
    -----
    This plots y vs x (image coordinate convention). Uses Matplotlib.
    """
    import matplotlib.pyplot as plt

    H, W = img0.shape
    x = np.arange(W)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(img0, cmap="gray", alpha=img_alpha)

    # upper
    ax.plot(x, y0_upper, color="cyan", lw=line_width, label="upper t=0")
    ax.plot(x, yT_upper, color="cyan", lw=line_width, ls="--", label="upper t=T")
    ax.fill_between(
        x, y0_upper, yT_upper,
        where=~np.isnan(y0_upper) & ~np.isnan(yT_upper),
        color="cyan", alpha=0.25, interpolate=True,
    )

    # lower
    ax.plot(x, y0_lower, color="magenta", lw=line_width, label="lower t=0")
    ax.plot(x, yT_lower, color="magenta", lw=line_width, ls="--", label="lower t=T")
    ax.fill_between(
        x, y0_lower, yT_lower,
        where=~np.isnan(y0_lower) & ~np.isnan(yT_lower),
        color="magenta", alpha=0.25, interpolate=True,
    )

    ax.set_title(f"{traj_key} | t=0 → t={t_used}")
    ax.set_xlim(0, W - 1)
    ax.set_ylim(H - 1, 0)  # keep image coordinates
    ax.legend(frameon=False, fontsize=9)

    plt.tight_layout()
    plt.show()

