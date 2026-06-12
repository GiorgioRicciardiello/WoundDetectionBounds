"""
Main Quantification Pipeline (Legacy Entry Point)
==================================================

This module provides backward compatibility. The core pipeline logic
is now in library.core.segmentation and used by both main.py and the new API.

For production use, prefer:
    from library import Pipeline
    config = Pipeline.from_yaml("config.yaml")
    results = config.run()
"""

import re
import multiprocessing
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict
from pathlib import Path

from config.config import config
from library.core.types import WoundDetectorConfig
from library.core.segmentation import (
    run_quantification_pipeline,
    pickle_io,
)
from library.experiment_handler.organize_experiments import organize_experiments


def time_to_hours(t: str) -> float:
    """Convert time string '00d02h30m' to hours."""
    m = re.match(r"(\d+)d(\d+)h(\d+)m", t)
    if not m:
        return np.nan
    d, h, m_ = map(int, m.groups())
    return d * 24 + h + m_ / 60


def align_times_within_samples(
    df: pd.DataFrame,
    time_col: str = "time",
    sample_col: str = "sample_name",
    value_cols: list = ("wound_area",),
    target_times: Optional[List[float]] = None,
    method: str = "nearest",
) -> pd.DataFrame:
    """
    Align time-series data within each sample for comparison.

    Parameters
    ----------
    df : pd.DataFrame
        Final legacy dataframe.
    time_col : str
        Column containing time strings like '00d02h30m'.
    sample_col : str
        Column defining independent biological samples.
    value_cols : list
        Columns to align (e.g. wound_area).
    target_times : list | None
        Target times in hours. If None, uses integer hours.
    method : str
        'nearest' or 'interpolate'.

    Returns
    -------
    pd.DataFrame
        Time-aligned dataframe.
    """
    df = df.copy()
    df["_time_h"] = df[time_col].apply(time_to_hours)

    if target_times is None:
        target_times = sorted(set(df["_time_h"].round().astype(int)))

    aligned = []

    for sample, g in df.groupby(sample_col):
        g = g.sort_values("_time_h")
        t_src = g["_time_h"].values

        out = pd.DataFrame({sample_col: sample, "_time_h": target_times})

        if method == "nearest":
            idx = np.abs(
                t_src[:, None] - np.array(target_times)[None, :]
            ).argmin(axis=0)
            for col in value_cols:
                out[col] = g.iloc[idx][col].values

        elif method == "interpolate":
            for col in value_cols:
                out[col] = np.interp(target_times, t_src, g[col].values)
        else:
            raise ValueError("method must be 'nearest' or 'interpolate'")

        aligned.append(out)

    df_out = pd.concat(aligned, ignore_index=True)
    df_out["time_h"] = df_out["_time_h"]
    df_out.drop(columns="_time_h", inplace=True)

    return df_out


# =============================================================================
# Main Entry Point
# =============================================================================

def _run_single_config(
    label: str,
    detector_config: WoundDetectorConfig,
    image_folder: Path,
    output_root: Path,
    exposures: List[str],
    experiments: List[str],
    n_workers: int = 10,
    process_missing: bool = True,
    save_debug: bool = True,
) -> Tuple[pd.DataFrame, Dict]:
    """Run the full pipeline with a single detector configuration.

    Parameters
    ----------
    label : str
        Human-readable label for logging (e.g. "kalman", "hard").
    detector_config : WoundDetectorConfig
        Configuration controlling Kalman filter and all pipeline stages.
    image_folder : Path
        Root folder with organized images.
    output_root : Path
        Root folder for segmentation outputs (unique per config).
    exposures, experiments : list of str
        Experimental factors.
    n_workers : int
        Parallel worker count.
    process_missing : bool
        If True, segment samples that have no cached results.
    save_debug : bool
        Save per-frame debug PNGs.

    Returns
    -------
    df_final : pd.DataFrame
    trajectories : dict
    """
    output_root.mkdir(exist_ok=True, parents=True)

    kalman_status = "ON" if detector_config.use_kalman else "OFF"
    print("\n" + "=" * 60)
    print(f"QUANTIFICATION PIPELINE — {label.upper()} (Kalman {kalman_status})")
    print("=" * 60)
    print(f"Image folder: {image_folder}")
    print(f"Output root:  {output_root}")
    print(f"Exposures:    {exposures}")
    print(f"Experiments:  {experiments}")
    print(f"Workers:      {multiprocessing.cpu_count()} CPUs available")
    print("=" * 60)

    df_final, trajectories = run_quantification_pipeline(
        image_folder=image_folder,
        output_root=output_root,
        exposures=exposures,
        experiments=experiments,
        process_missing=process_missing,
        save_debug=save_debug,
        n_workers=n_workers,
        detector_config=detector_config,
    )

    # Save outputs
    path_traj = output_root / "trajectories.pickle"
    path_legacy = output_root / "experiments.xlsx"

    pickle_io(path_traj, obj=trajectories, save=True)
    df_final.to_excel(path_legacy, index=False)

    print(f"\n[OK] {label}: saved {len(trajectories)} trajectories, {len(df_final)} rows")
    print(f"     -> {path_legacy}")

    # Time alignment
    if "time" in df_final.columns:
        df_aligned = align_times_within_samples(
            df_final,
            value_cols=["wound_area"],
            method="nearest",
        )
        path_aligned = output_root / "aligned_legacy_table.xlsx"
        df_aligned.to_excel(path_aligned, index=False)
        print(f"     -> {path_aligned}")

    return df_final, trajectories


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Shared configuration
    # ------------------------------------------------------------------
    image_folder: Path = config.get("data_in_organized")
    base_output: Path = config.get("output_dir")
    n_workers = 10

    exposures = ["alk5i", "Candasertan"]
    experiments = ["EXP1", "EXP2"]

    # ------------------------------------------------------------------
    # File Pre-Processing
    # ------------------------------------------------------------------
    if not image_folder.exists():
        organize_experiments(
            source_base_dir=config.get("data_in_dir"),
            output_base_dir=image_folder,
        )

    # ------------------------------------------------------------------
    # Run 1: Kalman filter ENABLED (default)
    # ------------------------------------------------------------------
    cfg_kalman = WoundDetectorConfig(use_kalman=True)
    output_kalman = base_output / "Quantification_kalman"

    df_kalman, traj_kalman = _run_single_config(
        label="kalman",
        detector_config=cfg_kalman,
        image_folder=image_folder,
        output_root=output_kalman,
        exposures=exposures,
        experiments=experiments,
        n_workers=n_workers,
        process_missing=True, # set to True
        save_debug=True,
    )

    # ------------------------------------------------------------------
    # Run 2: Kalman filter DISABLED (hard constraint only)
    # ------------------------------------------------------------------
    cfg_hard = WoundDetectorConfig(use_kalman=False)
    output_hard = base_output / "Quantification_hard"

    df_hard, traj_hard = _run_single_config(
        label="hard",
        detector_config=cfg_hard,
        image_folder=image_folder,
        output_root=output_hard,
        exposures=exposures,
        experiments=experiments,
        n_workers=n_workers,
        process_missing=True, # set to True
        save_debug=True,
    )

    # ------------------------------------------------------------------
    # Comparison summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"{'Metric':<30} {'Kalman':>12} {'Hard':>12}")
    print("-" * 54)
    print(f"{'Trajectories':<30} {len(traj_kalman):>12} {len(traj_hard):>12}")
    print(f"{'Total rows':<30} {len(df_kalman):>12} {len(df_hard):>12}")

    if "wound_area" in df_kalman.columns and "wound_area" in df_hard.columns:
        mean_k = df_kalman["wound_area"].mean()
        mean_h = df_hard["wound_area"].mean()
        print(f"{'Mean wound area (px)':<30} {mean_k:>12.1f} {mean_h:>12.1f}")

    if "constrained" in df_kalman.columns and "constrained" in df_hard.columns:
        rate_k = df_kalman["constrained"].mean() * 100
        rate_h = df_hard["constrained"].mean() * 100
        print(f"{'Constraint rate (%)':<30} {rate_k:>12.1f} {rate_h:>12.1f}")

    print("=" * 60)
    print(f"Kalman output: {output_kalman}")
    print(f"Hard output:   {output_hard}")
    print("\nDone!")
