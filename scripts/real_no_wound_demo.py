"""
Real No-Wound Profile Extraction
==================================
Load a real image from the ground-truth dataset marked as "no wound"
and render its variance profile alongside the synthetic closing examples.

Usage:
    cd C:\\Users\\riccig01\\OneDrive\\Projects\\MtSinai\\Vascbrain\\WoundDetectionBounds
    python scripts/real_no_wound_demo.py
"""

import pickle
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import cv2
from scipy.ndimage import gaussian_filter1d

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.config import config
from library.wound_standard.detector import WoundDetector
from library.core.types import WoundDetectorConfig

OUT_DIR: Path = _PROJECT_ROOT / "results" / "synthetic_closing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI: int = 300


def main():
    print("=" * 60)
    print("Real no-wound profile extraction")
    print("=" * 60)

    # Load verification results
    verif_path = config["verification_results"]
    print(f"\nLoading verification results from:\n  {verif_path}")
    verif_df = pd.read_excel(verif_path)

    # Filter for "no wound" cases
    no_wound_cases = verif_df[verif_df["notes"].str.contains("no wound", na=False, case=False)]
    print(f"Found {len(no_wound_cases)} 'no wound' cases in ground truth")

    # Exclude Candesartan (published cohort only)
    no_wound_cases = no_wound_cases[~no_wound_cases["exposure"].str.contains("candesartan", na=False, case=False)]
    print(f"After excluding Candesartan: {len(no_wound_cases)} cases")

    if len(no_wound_cases) == 0:
        print("No suitable no-wound cases found. Exiting.")
        return

    # Load trajectories to get images
    traj_path = config["trajectories_pickle"]
    print(f"\nLoading trajectories from:\n  {traj_path}")
    with traj_path.open("rb") as f:
        trajectories: dict = pickle.load(f)

    # Try to find a no-wound case with a t=0 image
    found = False
    for idx, row in no_wound_cases.iterrows():
        traj_key = row["trajectory_key"]
        print(f"\nChecking: {traj_key}")

        if traj_key not in trajectories:
            print(f"  [SKIP] trajectory key not found in pickle")
            continue

        traj_data = trajectories[traj_key]
        results = traj_data.get("results", [])
        t0 = next((r for r in results if r.get("t") == 0), None)

        if t0 is None or "img_raw" not in t0:
            print(f"  [SKIP] no t=0 image")
            continue

        img_raw = t0["img_raw"]
        qc_valid = t0.get("qc", {}).get("valid", False)
        print(f"  [OK] Found t=0 image (QC valid: {qc_valid})")

        # Compute variance profile
        print(f"  Computing variance profile...")
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

        # Detector's attempted Y-band detection (may be spurious)
        y_min, y_max, y_center = detector._detect_y_band(variance_smooth)
        band_width = y_max - y_min

        print(f"  Detected Y-band: y={y_min}..{y_max} (width={band_width}px)")

        # Render profile
        vmax = np.percentile(variance_smooth, 99)
        vm_norm = np.clip(variance_smooth, 0, vmax) / (vmax + 1e-12)

        row_profile = variance_smooth.mean(axis=1)
        row_profile_norm = np.clip(row_profile, 0, np.percentile(row_profile, 99)) / (np.percentile(row_profile, 99) + 1e-12)

        fig_w = 4.0
        fig, (ax_hm, ax_prof) = plt.subplots(2, 1, figsize=(fig_w, fig_w * 1.3),
                                              gridspec_kw={"height_ratios": [3, 1]})

        # Heatmap with detected (spurious) band
        ax_hm.imshow(vm_norm, cmap="viridis", aspect="auto", interpolation="nearest", vmin=0, vmax=1)
        ax_hm.axhspan(y_min, y_max, alpha=0.25, facecolor="red", linewidth=2)
        ax_hm.set_xlim(0, W - 1)
        ax_hm.set_ylim(H - 1, 0)
        ax_hm.set_ylabel("Row (pixels)", fontsize=8, color="white")
        ax_hm.tick_params(colors="white", labelsize=6)
        ax_hm.spines["bottom"].set_visible(False)
        ax_hm.set_xticklabels([])

        # Profile
        y_coords = np.arange(H)
        ax_prof.plot(y_coords, row_profile_norm, color="white", linewidth=1.5)
        ax_prof.fill_between(y_coords, 0, row_profile_norm, alpha=0.3, color="white")
        ax_prof.axvspan(y_min, y_max, alpha=0.2, facecolor="red", linewidth=2)
        ax_prof.axhline(row_profile_norm.mean(), color="orange", linestyle="--", linewidth=1.5, alpha=0.7,
                       label="Mean (should be flat)")
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
        ax_prof.legend(loc="upper right", fontsize=7, facecolor="#1a1a1a", edgecolor="white")

        fig.suptitle(f"Real No-Wound Example: {traj_key}", fontsize=9, color="white")
        fig.patch.set_facecolor("#0a0a0a")
        fig.subplots_adjust(left=0.08, right=1, top=0.95, bottom=0.08, hspace=0.15)

        out_path = OUT_DIR / "real_no_wound_example.png"
        fig.savefig(out_path, dpi=DPI, bbox_inches="tight", facecolor="#0a0a0a")
        plt.close(fig)

        print(f"  [DONE] Saved: {out_path.name}")
        print(f"\n  Label: {row['notes']}")
        print(f"  Exposure: {row['exposure']}, Experiment: {row['experiment']}")

        found = True
        break

    if not found:
        print("\nCould not find a suitable no-wound case with t=0 image and trajectories.")
    else:
        print(f"\nProfile saved to: {OUT_DIR}")
        print("Done.")


if __name__ == "__main__":
    main()
