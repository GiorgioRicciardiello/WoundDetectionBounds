"""
Monotonic Constraint (Wound Closure) Visualization
===================================================
Create a pedagogical figure showing how the monotonic constraint prevents
wound edges from expanding after they've contracted. Demonstrates the
biological invariant: wound area can only decrease or stay constant over time.

Standalone demonstration (no main pipeline dependencies).

Usage:
    cd C:\\Users\\riccig01\\OneDrive\\Projects\\MtSinai\\Vascbrain\\WoundDetectionBounds
    python scripts/monotonic_constraint_demo.py
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

OUT_DIR: Path = Path(__file__).resolve().parent.parent / "results" / "kalman_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI: int = 300


def apply_monotonic_constraint(edges: np.ndarray) -> np.ndarray:
    """
    Apply monotonic constraint: each column's edge position can only move
    monotonically (inward/closing). Once contracted, cannot expand back.

    Parameters
    ----------
    edges : (num_frames, num_cols) array of edge positions

    Returns
    -------
    constrained_edges : same shape, with monotonicity enforced
    """
    num_frames, num_cols = edges.shape
    constrained = np.zeros_like(edges)

    for col in range(num_cols):
        constrained[:, col] = np.maximum.accumulate(edges[:, col])

    return constrained


def generate_synthetic_edges_with_violation(num_frames: int = 25, num_cols: int = 6) -> np.ndarray:
    """
    Generate synthetic edges that violate monotonicity:
    - Initially closing (contracting downward for upper edge)
    - Then expanding back upward (biologically impossible for a wound)
    - Has noise and outliers at the boundary

    For an upper edge: closed state has smaller row index, expanded has larger.
    Monotonic constraint: row index should only increase (move down) or stay.
    """
    np.random.seed(42)

    edges = np.zeros((num_frames, num_cols))

    for col in range(num_cols):
        base_pos = 350 + col * 30

        # First half: contracting (edge moves DOWN = position increases)
        t1 = np.linspace(0, 12, 12)
        edges[:12, col] = base_pos + 50 * (t1 / 12)  # increases (closes)

        # Second half: expanding back (edge moves UP = position decreases) — VIOLATION
        t2 = np.linspace(0, 13, 13)
        rebound = 40 * (1 - np.cos(np.pi * t2 / 13)) / 2  # smooth rebound
        edges[12:, col] = edges[11, col] - rebound  # decreases (violates monotonicity!)

        # Add noise
        edges[:, col] += np.random.normal(0, 2, num_frames)

    return edges


def create_figure(unconstrained_edges: np.ndarray, constrained_edges: np.ndarray) -> plt.Figure:
    """
    Create a 4-panel figure showing:
      Panel A: Time series for one column (unconstrained + constrained)
      Panel B: All columns before constraint (violation visible)
      Panel C: All columns after constraint (monotonicity enforced)
      Panel D: The correction applied (delta)
    """
    num_frames, num_cols = unconstrained_edges.shape
    col_demo = num_cols // 2

    fig = plt.figure(figsize=(16, 5))
    fig.patch.set_facecolor("none")
    fig.patch.set_alpha(0.0)

    # Panel A: Time series for one column
    ax_a = plt.subplot(1, 4, 1)
    ax_a.set_facecolor("none")
    t = np.arange(num_frames)

    ax_a.plot(t, unconstrained_edges[:, col_demo], color="red", linewidth=2.5,
             marker="o", markersize=4, label="Detected (unconstrained)", alpha=0.8, zorder=2)
    ax_a.plot(t, constrained_edges[:, col_demo], color="green", linewidth=2.5,
             marker="s", markersize=4, label="Constrained (monotonic)", alpha=0.8, zorder=3)

    # Shade the violation region
    violation_mask = unconstrained_edges[:, col_demo] > constrained_edges[:, col_demo]
    ax_a.fill_between(t, constrained_edges[:, col_demo], unconstrained_edges[:, col_demo],
                      where=violation_mask, alpha=0.2, color="orange", label="Violation corrected")

    ax_a.axvline(12, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    ax_a.text(12, ax_a.get_ylim()[1] * 0.95, "← Closing | Violation →",
             ha="center", fontsize=8, style="italic", color="gray")

    ax_a.set_xlabel("Timepoint", fontsize=10, weight="bold")
    ax_a.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_a.set_title("A. Temporal Trajectory", fontsize=11, weight="bold")
    ax_a.legend(fontsize=8, loc="upper right")
    ax_a.grid(True, alpha=0.3)

    # Panel B: Unconstrained edges (violation visible)
    ax_b = plt.subplot(1, 4, 2)
    ax_b.set_facecolor("none")
    x_cols = np.arange(num_cols)

    # Show multiple timepoints — highly distinct colors
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]  # blue, orange, green, red, purple
    times = [0, 6, 12, 18, 24]
    for i, t_idx in enumerate(times):
        ax_b.plot(x_cols, unconstrained_edges[t_idx, :], marker="o", markersize=5,
                 label=f"t={t_idx}", color=colors[i], alpha=0.8, linewidth=2.5)

    ax_b.set_xlabel("Column index", fontsize=10, weight="bold")
    ax_b.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_b.set_title("B. Before Constraint\n(expanding = violation)", fontsize=11, weight="bold")
    ax_b.legend(fontsize=8, ncol=1, loc="best")
    ax_b.grid(True, alpha=0.3)
    ax_b.set_xticks(x_cols)

    # Panel C: Constrained edges (monotonic)
    ax_c = plt.subplot(1, 4, 3)
    ax_c.set_facecolor("none")
    for i, t_idx in enumerate(times):
        ax_c.plot(x_cols, constrained_edges[t_idx, :], marker="s", markersize=5,
                 label=f"t={t_idx}", color=colors[i], alpha=0.9, linewidth=2.5)

    ax_c.set_xlabel("Column index", fontsize=10, weight="bold")
    ax_c.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_c.set_title("C. After Constraint\n(monotonic closure)", fontsize=11, weight="bold")
    ax_c.legend(fontsize=8, ncol=1, loc="best")
    ax_c.grid(True, alpha=0.3)
    ax_c.set_xticks(x_cols)

    # Panel D: Correction (delta)
    ax_d = plt.subplot(1, 4, 4)
    ax_d.set_facecolor("none")
    correction = constrained_edges - unconstrained_edges

    for i, t_idx in enumerate(times):
        if np.any(correction[t_idx, :] != 0):
            ax_d.bar(x_cols + i * 0.12 - 0.24, correction[t_idx, :], width=0.12,
                    label=f"t={t_idx}", alpha=0.9, color=colors[i])

    ax_d.set_xlabel("Column index", fontsize=10, weight="bold")
    ax_d.set_ylabel("Correction magnitude (pixels)", fontsize=10, weight="bold")
    ax_d.set_title("D. Corrections Applied\n(inward adjustment)", fontsize=11, weight="bold")
    ax_d.legend(fontsize=8, ncol=1, loc="best")
    ax_d.grid(True, alpha=0.3, axis="y")
    ax_d.set_xticks(x_cols)

    fig.suptitle("Monotonic Constraint: Enforcing Wound Closure Invariant",
                fontsize=13, weight="bold", y=1.00)
    fig.tight_layout()

    return fig


def main():
    print("=" * 60)
    print("Monotonic constraint (wound closure) visualization")
    print("=" * 60)

    print("\nGenerating synthetic edges with monotonicity violations...")
    unconstrained_edges = generate_synthetic_edges_with_violation(num_frames=25, num_cols=6)
    print(f"  {unconstrained_edges.shape[0]} timepoints, {unconstrained_edges.shape[1]} columns")

    print("\nApplying monotonic constraint...")
    constrained_edges = apply_monotonic_constraint(unconstrained_edges)

    # Compute correction statistics
    correction = constrained_edges - unconstrained_edges
    num_violations = np.sum(correction > 0)
    total_correction_px = np.sum(correction)
    max_correction = np.max(correction)

    print(f"  Violations detected: {num_violations} (out of {unconstrained_edges.size} measurements)")
    print(f"  Total correction:    {total_correction_px:.1f} px")
    print(f"  Max single correction: {max_correction:.2f} px")

    print("\nRendering figure...")
    fig = create_figure(unconstrained_edges, constrained_edges)

    out_path = OUT_DIR / "monotonic_constraint.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="none", transparent=True)
    plt.close(fig)

    print(f"  Saved: {out_path}")
    print(f"\nAll outputs written to: {OUT_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
