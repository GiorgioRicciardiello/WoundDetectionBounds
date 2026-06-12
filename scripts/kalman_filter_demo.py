"""
Kalman Filter Temporal Integration Visualization
=================================================
Create a pedagogical figure showing how the Kalman filter integrates
per-column edge observations across time, smoothing noise and outliers.

Standalone demonstration (no main pipeline dependencies).

Usage:
    cd C:\\Users\\riccig01\\OneDrive\\Projects\\MtSinai\\Vascbrain\\WoundDetectionBounds
    python scripts/kalman_filter_demo.py
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.ndimage import gaussian_filter1d

OUT_DIR: Path = Path(__file__).resolve().parent.parent / "results" / "kalman_demo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI: int = 300


class KalmanFilter1D:
    """Simple 1D Kalman filter for temporal edge tracking."""

    def __init__(self, Q: float = 25.0, R: float = 100.0):
        """
        Parameters
        ----------
        Q : process noise variance (how much we expect the true state to drift)
        R : measurement noise variance (how noisy are the observations)
        """
        self.Q = Q
        self.R = R
        self.x = None  # state estimate
        self.P = None  # state covariance (uncertainty)

    def update(self, z: float) -> tuple:
        """
        One Kalman filter step.

        Parameters
        ----------
        z : measurement (observed edge position)

        Returns
        -------
        x_posterior : filtered estimate
        P_posterior : posterior covariance
        """
        if self.x is None:
            # Initialize on first measurement
            self.x = z
            self.P = self.R
            return self.x, self.P

        # Prediction step
        x_pred = self.x  # constant velocity model (no drift)
        P_pred = self.P + self.Q  # add process noise

        # Update step (Bayes rule)
        K = P_pred / (P_pred + self.R)  # Kalman gain
        self.x = x_pred + K * (z - x_pred)  # update estimate
        self.P = (1 - K) * P_pred  # update covariance

        return self.x, self.P


def generate_synthetic_edge_sequence(num_frames: int = 25, num_cols: int = 6) -> tuple:
    """
    Generate synthetic edge trajectories: smooth true motion + noisy observations.

    Returns
    -------
    true_edges : (num_frames, num_cols) true edge positions
    observed_edges : (num_frames, num_cols) noisy observations with occasional outliers
    """
    np.random.seed(42)

    true_edges = np.zeros((num_frames, num_cols))
    observed_edges = np.zeros((num_frames, num_cols))

    for col in range(num_cols):
        # True edge position: smooth wound closing
        base_pos = 300 + col * 30
        drift = np.linspace(0, 60, num_frames)  # wound edge moves down ~60px over time
        true_edges[:, col] = base_pos + drift + 5 * np.sin(np.linspace(0, 2 * np.pi, num_frames))

        # Observations: add noise and occasional outliers
        noise = np.random.normal(0, 8, num_frames)
        outliers = np.random.rand(num_frames) < 0.1  # 10% chance of outlier
        outlier_mag = np.random.normal(0, 25, num_frames)

        observed_edges[:, col] = true_edges[:, col] + noise
        observed_edges[outliers, col] += outlier_mag[outliers]

    return true_edges, observed_edges


def apply_kalman_filter(observed_edges: np.ndarray) -> np.ndarray:
    """Apply Kalman filter to each column."""
    num_frames, num_cols = observed_edges.shape
    filtered_edges = np.zeros_like(observed_edges)

    for col in range(num_cols):
        kf = KalmanFilter1D(Q=25.0, R=100.0)
        for t in range(num_frames):
            x_filt, _ = kf.update(observed_edges[t, col])
            filtered_edges[t, col] = x_filt

    return filtered_edges


def create_figure(true_edges: np.ndarray, observed_edges: np.ndarray,
                  filtered_edges: np.ndarray) -> plt.Figure:
    """
    Create a 3-panel figure showing:
      Panel A: Time series for one representative column (raw + filtered)
      Panel B: All columns at t=0 (raw edges)
      Panel C: All columns at t=24 (filtered edges)
    """
    num_frames, num_cols = observed_edges.shape
    col_demo = num_cols // 2  # middle column for demo

    fig = plt.figure(figsize=(14, 5))
    fig.patch.set_facecolor("none")
    fig.patch.set_alpha(0.0)

    # Panel A: Time series for one column
    ax_a = plt.subplot(1, 3, 1)
    ax_a.set_facecolor("none")
    t = np.arange(num_frames)

    ax_a.scatter(t, observed_edges[:, col_demo], s=30, alpha=0.6, color="red",
                label="Raw measurements", zorder=2)
    ax_a.plot(t, filtered_edges[:, col_demo], color="blue", linewidth=2.5,
             label="Kalman filtered", zorder=3)
    ax_a.plot(t, true_edges[:, col_demo], color="green", linewidth=2, linestyle="--",
             label="True (ground truth)", alpha=0.7, zorder=1)

    ax_a.set_xlabel("Timepoint", fontsize=10, weight="bold")
    ax_a.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_a.set_title("A. Per-Column Temporal Smoothing", fontsize=11, weight="bold")
    ax_a.legend(fontsize=9, loc="upper left")
    ax_a.grid(True, alpha=0.3)

    # Panel B: Raw edges across all columns at t=0
    ax_b = plt.subplot(1, 3, 2)
    ax_b.set_facecolor("none")
    x_cols = np.arange(num_cols)
    ax_b.scatter(x_cols, observed_edges[0, :], s=80, alpha=0.7, color="red",
                edgecolor="darkred", linewidth=1.5, label="Raw (t=0)", zorder=2)
    ax_b.plot(x_cols, true_edges[0, :], color="green", linewidth=2.5, linestyle="--",
             label="True (t=0)", alpha=0.7, zorder=1)

    ax_b.set_xlabel("Column index", fontsize=10, weight="bold")
    ax_b.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_b.set_title("B. Initial Noisy Detection (t=0)", fontsize=11, weight="bold")
    ax_b.legend(fontsize=9)
    ax_b.grid(True, alpha=0.3)
    ax_b.set_xticks(x_cols)

    # Panel C: Filtered edges across all columns at final timepoint
    ax_c = plt.subplot(1, 3, 3)
    ax_c.set_facecolor("none")
    t_final = num_frames - 1
    ax_c.scatter(x_cols, observed_edges[t_final, :], s=80, alpha=0.5, color="orange",
                edgecolor="darkorange", linewidth=1.5, label="Raw (t=final)", zorder=1)
    ax_c.scatter(x_cols, filtered_edges[t_final, :], s=100, alpha=0.8, color="blue",
                edgecolor="darkblue", linewidth=1.5, marker="s", label="Filtered (t=final)", zorder=3)
    ax_c.plot(x_cols, true_edges[t_final, :], color="green", linewidth=2.5, linestyle="--",
             label="True (t=final)", alpha=0.7, zorder=2)

    ax_c.set_xlabel("Column index", fontsize=10, weight="bold")
    ax_c.set_ylabel("Edge position (pixels)", fontsize=10, weight="bold")
    ax_c.set_title("C. Kalman Correction (t=final)", fontsize=11, weight="bold")
    ax_c.legend(fontsize=9)
    ax_c.grid(True, alpha=0.3)
    ax_c.set_xticks(x_cols)

    fig.suptitle("Kalman Filter: Temporal Integration of Per-Column Edges",
                fontsize=13, weight="bold", y=1.00)
    fig.tight_layout()

    return fig


def main():
    print("=" * 60)
    print("Kalman filter temporal integration visualization")
    print("=" * 60)

    print("\nGenerating synthetic edge sequences...")
    true_edges, observed_edges = generate_synthetic_edge_sequence(num_frames=25, num_cols=6)
    print(f"  {observed_edges.shape[0]} timepoints, {observed_edges.shape[1]} columns")

    print("\nApplying Kalman filter to each column...")
    filtered_edges = apply_kalman_filter(observed_edges)

    # Compute error metrics
    raw_rmse = np.sqrt(np.mean((observed_edges - true_edges) ** 2))
    filtered_rmse = np.sqrt(np.mean((filtered_edges - true_edges) ** 2))

    print(f"  Raw measurement RMSE:  {raw_rmse:.2f} px")
    print(f"  Filtered estimate RMSE: {filtered_rmse:.2f} px")
    print(f"  Improvement: {(raw_rmse - filtered_rmse) / raw_rmse * 100:.1f}%")

    print("\nRendering figure...")
    fig = create_figure(true_edges, observed_edges, filtered_edges)

    out_path = OUT_DIR / "kalman_temporal_integration.png"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="none", transparent=True)
    plt.close(fig)

    print(f"  Saved: {out_path}")
    print(f"\nAll outputs written to: {OUT_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
