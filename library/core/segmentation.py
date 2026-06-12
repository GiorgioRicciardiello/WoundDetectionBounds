"""
Core segmentation pipeline.

This module is imported by both main.py and the new Pipeline API.
Keeps the segmentation logic in one place for maintenance.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import pickle
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from library.core.types import WoundDetectorConfig
from library.wound_quantification.trajectory import (
    process_trajectory,
    load_trajectory_results,
)


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

    if results_pkl.exists():
        try:
            results = load_trajectory_results(sample_out_dir)
        except Exception as e:
            warnings.warn(f"Failed to load {identifier}: {e}")
            return None
    else:
        if not process_missing:
            return None

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

        results, _ = process_trajectory(
            image_paths=paths,
            output_dir=sample_out_dir,
            config=detector_config,
            save_debug=save_debug,
        )

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
        Experimental exposures.
    experiments : List[str]
        Experiment identifiers.
    process_missing : bool
        If False: only collect existing results.
        If True: run segmentation for samples without results.
    save_debug : bool
        Save debug visualizations for each frame.
    detector_config : WoundDetectorConfig | None
        Configuration for the wound detector.

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

            df_legacy = pd.read_excel(legacy_path)
            df_legacy.columns = (
                df_legacy.columns.str.replace(" ", "_").str.lower()
            )

            df_area_all = []
            sample_groups = list(df_legacy.groupby("sample_name"))

            effective_workers = min(n_workers, len(sample_groups))

            if effective_workers > 1:
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

                    for future in tqdm(
                        as_completed(futures),
                        total=len(futures),
                        desc=f"{exposure}/{experiment}",
                    ):
                        sample_name = futures[future]
                        try:
                            result = future.result()
                            if result is not None:
                                identifier = result["identifier"]
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
                        trajectories[identifier] = {
                            "results": result["results"],
                            "sample_out_dir": result["sample_out_dir"],
                            "exposure": result["exposure"],
                            "experiment": result["experiment"],
                            "sample_name": result["sample_name"],
                        }
                        df_area_all.append(result["df_area"])

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

    if not final_legacy_tables:
        raise RuntimeError("No legacy tables were processed.")

    df_final = pd.concat(final_legacy_tables, ignore_index=True)

    return df_final, trajectories
