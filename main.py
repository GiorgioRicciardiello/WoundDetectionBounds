"""
Main Quantification Pipeline
====================

Robust wound healing analysis using variance-based detection
with monotonic closure constraint.

For each exposure × experiment × sample:
- Load legacy metadata table
- Run wound segmentation with QuantificationSegmenter
- Enforce monotonic constraint (wound can only shrink)
- Extract measurements and merge into legacy data
- Aggregate all results into final dataset
"""

import warnings
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import re
import pickle
import numpy as np
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from config.config import config
from library.core.types import WoundDetectorConfig
from library.wound_quantification.segmenter import QuantificationSegmenter
from library.wound_quantification.trajectory import (
    process_trajectory,
    load_trajectory_results,
    save_trajectory_results,
)
from library.experiment_handler.organize_experiments import organize_experiments


# =============================================================================
# Helper Functions
# =============================================================================

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



def pickle_io(path: str | Path, obj: Any = None, save: bool = True):
    """
    Save or load an object using pickle.

    Parameters
    ----------
    path : str | Path
        File path for the pickle file
    obj : Any, optional
        Object to save (required if save=True)
    save : bool
        True -> save object
        False -> load object

    Returns
    -------
    Any
        Loaded object if save=False, otherwise None
    """
    path = Path(path)

    if save:
        if obj is None:
            raise ValueError("obj must be provided when save=True")
        with path.open("wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        return None
    else:
        with path.open("rb") as f:
            return pickle.load(f)

# =============================================================================
# Parallel Worker Function
# =============================================================================

def _process_single_sample(
    sample_name: str,
    df_slice: pd.DataFrame,
    experiment_path: Path,
    output_root: Path,
    exposure: str,
    experiment: str,
    process_missing: bool,
    save_debug: bool,
    detector_config: Optional[WoundDetectorConfig] = None,
) -> Optional[Dict]:
    """
    Process a single sample for wound segmentation.
    
    This function is designed to run in a separate process.
    
    Returns
    -------
    dict or None
        Dictionary containing results, trajectory info, and df_area,
        or None if processing failed.
    """
    identifier = f"{sample_name}-{experiment}-{exposure}"
    sample_out_dir = output_root / identifier
    results_pkl = sample_out_dir / "experiment.pkl"
    
    # Obtain segmentation results - check for the actual results file, not just the directory
    if results_pkl.exists():
        # Load existing results
        try:
            results = load_trajectory_results(sample_out_dir)
        except Exception as e:
            warnings.warn(f"Failed to load {identifier}: {e}")
            return None
    else:
        if not process_missing:
            return None
        
        # Prepare image paths
        df_slice = df_slice.copy()
        df_slice["path"] = df_slice["new_file"].apply(
            lambda x: experiment_path / x
        )
        df_slice = df_slice[df_slice["path"].apply(Path.exists)]
        
        if df_slice.empty:
            warnings.warn(f"{identifier}: no valid paths found")
            return None
        
        df_slice.sort_values("time_min", inplace=True)
        paths = df_slice["path"].tolist()
        
        # Run segmentation with Quantification pipeline
        results, _ = process_trajectory(
            image_paths=paths,
            output_dir=sample_out_dir,
            config=detector_config,
            save_debug=save_debug,
        )
    
    # Build measurement dataframe
    df_area = pd.DataFrame({
        "img_name": [
            r["file_name"].name if r.get("file_name") else None
            for r in results
        ],
        "wound_area": [r.get("area") for r in results],
        "img_area": [
            r["img_raw"].shape[0] * r["img_raw"].shape[1]
            if r.get("img_raw") is not None else None
            for r in results
        ],
        "t_seg": [r.get("t") for r in results],
        "constrained": [r.get("constrained") for r in results],
        "qc_valid": [
            r.get("qc", {}).get("valid") for r in results
        ],
    })
    
    df_area["identifier"] = identifier
    df_area["sample_out_dir"] = str(sample_out_dir)
    
    # Remove duplicates
    df_area = df_area.drop_duplicates(["img_name"], keep="first")
    
    return {
        "identifier": identifier,
        "results": results,
        "sample_out_dir": sample_out_dir,
        "exposure": exposure,
        "experiment": experiment,
        "sample_name": sample_name,
        "df_area": df_area,
    }


# =============================================================================
# Main Pipeline
# =============================================================================

def run_quantification_pipeline(
    image_folder: Path,
    output_root: Path,
    exposures: List[str],
    experiments: List[str],
    process_missing: bool = False,
    save_debug: bool = False,
    n_workers: int = 4,
    detector_config: Optional[WoundDetectorConfig] = None,
) -> Tuple[pd.DataFrame, Dict[str, Dict]]:
    """
    Main Quantification pipeline for wound-healing experiments.

    Uses QuantificationSegmenter with monotonic closure constraint.

    Parameters
    ----------
    image_folder : Path
        Root folder containing organized images:
        image_folder / exposure / experiment / *.tif
    output_root : Path
        Root folder for segmentation outputs.
    exposures : List[str]
        Experimental exposures (e.g. ["alk5i", "Candasertan"]).
    experiments : List[str]
        Experiment identifiers (e.g. ["EXP1", "EXP2"]).
    process_missing : bool
        If False: only collect existing results.
        If True: run segmentation for samples without results.
    save_debug : bool
        Save debug visualizations for each frame.
    detector_config : WoundDetectorConfig | None
        Configuration for the wound detector.  Controls Kalman filter
        settings (``use_kalman``), thresholds, and all pipeline stages.
        When None, defaults are used (Kalman enabled).

    Returns
    -------
    df_final : pd.DataFrame
        Unified dataframe with segmentation measurements.
    trajectories : Dict
        Raw trajectories keyed by identifier.
    """
    final_legacy_tables: List[pd.DataFrame] = []
    trajectories: Dict[str, Dict] = {}
    
    for exposure in exposures:
        exposure_path = image_folder / exposure
        if not exposure_path.exists():
            continue
        
        for experiment in experiments:
            experiment_path = exposure_path / experiment
            legacy_filename = f"{exposure}_{experiment}_sample_file.xlsx"
            legacy_path = experiment_path / legacy_filename
            
            if not legacy_path.exists():
                continue
            
            # ----------------------------------------------------------
            # Load legacy table
            # ----------------------------------------------------------
            df_legacy = pd.read_excel(legacy_path)
            df_legacy.columns = (
                df_legacy.columns.str.replace(" ", "_").str.lower()
            )
            
            df_area_all = []
            
            # ----------------------------------------------------------
            # Process samples in parallel
            # ----------------------------------------------------------
            sample_groups = list(df_legacy.groupby("sample_name"))
            
            # Determine effective workers (cap at number of samples)
            effective_workers = min(n_workers, len(sample_groups))
            
            if effective_workers > 1:
                # Parallel processing
                with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                    futures = {}
                    
                    for sample_name, df_slice in sample_groups:
                        df_slice_copy = df_legacy.loc[
                            df_legacy["sample_name"] == sample_name
                        ].copy()
                        
                        future = executor.submit(
                            _process_single_sample,
                            sample_name=sample_name,
                            df_slice=df_slice_copy,
                            experiment_path=experiment_path,
                            output_root=output_root,
                            exposure=exposure,
                            experiment=experiment,
                            process_missing=process_missing,
                            save_debug=save_debug,
                            detector_config=detector_config,
                        )
                        futures[future] = sample_name
                    
                    # Collect results with progress bar
                    for future in tqdm(
                        as_completed(futures),
                        total=len(futures),
                        desc=f"{exposure}/{experiment}",
                    ):
                        sample_name = futures[future]
                        try:
                            result = future.result()
                            if result is not None:
                                # Store trajectory
                                identifier = result["identifier"]
                                if identifier in trajectories:
                                    raise ValueError(f"Duplicate identifier: {identifier}")
                                
                                trajectories[identifier] = {
                                    "results": result["results"],
                                    "sample_out_dir": result["sample_out_dir"],
                                    "exposure": result["exposure"],
                                    "experiment": result["experiment"],
                                    "sample_name": result["sample_name"],
                                }
                                df_area_all.append(result["df_area"])
                        except Exception as e:
                            warnings.warn(f"Error processing {sample_name}: {e}")
            else:
                # Sequential processing (n_workers=1)
                for sample_name, df_slice in tqdm(
                    sample_groups,
                    desc=f"{exposure}/{experiment}",
                ):
                    df_slice_copy = df_legacy.loc[
                        df_legacy["sample_name"] == sample_name
                    ].copy()
                    
                    result = _process_single_sample(
                        sample_name=sample_name,
                        df_slice=df_slice_copy,
                        experiment_path=experiment_path,
                        output_root=output_root,
                        exposure=exposure,
                        experiment=experiment,
                        process_missing=process_missing,
                        save_debug=save_debug,
                        detector_config=detector_config,
                    )
                    
                    if result is not None:
                        identifier = result["identifier"]
                        if identifier in trajectories:
                            raise ValueError(f"Duplicate identifier: {identifier}")
                        
                        trajectories[identifier] = {
                            "results": result["results"],
                            "sample_out_dir": result["sample_out_dir"],
                            "exposure": result["exposure"],
                            "experiment": result["experiment"],
                            "sample_name": result["sample_name"],
                        }
                        df_area_all.append(result["df_area"])
            
            # ----------------------------------------------------------
            # Merge into legacy table
            # ----------------------------------------------------------
            if not df_area_all:
                continue
            
            df_area_all = pd.concat(df_area_all, ignore_index=True)
            
            df_legacy = df_legacy.merge(
                df_area_all,
                how="left",
                left_on="new_file",
                right_on="img_name",
                validate="one_to_one",
            )
            
            final_legacy_tables.append(df_legacy)
    
    # ------------------------------------------------------------------
    # Final aggregation
    # ------------------------------------------------------------------
    if not final_legacy_tables:
        raise RuntimeError("No legacy tables were processed.")
    
    df_final = pd.concat(final_legacy_tables, ignore_index=True)
    
    return df_final, trajectories


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
    path_legacy = output_root / "final_legacy_table.xlsx"

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
