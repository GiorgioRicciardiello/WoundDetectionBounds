"""
Trajectory Processing
=====================

Process time-series of wound images with monotonic closure constraint.
"""

from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pickle
import warnings

import numpy as np
import cv2
from tqdm import tqdm

from library.wound_quantification.segmenter import QuantificationSegmenter, SegmentationResult
from library.core.types import WoundDetectorConfig


def process_trajectory(
    image_paths: List[Path],
    output_dir: Optional[Path] = None,
    config: Optional[WoundDetectorConfig] = None,
    verbose: bool = True,
    save_debug: bool = True,
) -> Tuple[List[Dict], QuantificationSegmenter]:
    """
    Process a time-series of images with monotonic wound closure constraint.
    
    Parameters
    ----------
    image_paths : List[Path]
        Ordered list of image paths (t=0 first, then t=1, t=2, ...).
    output_dir : Path | None
        Directory to save results. Creates if needed.
    config : WoundDetectorConfig | None
        Custom detector configuration.
    verbose : bool
        Show progress bar.
    save_debug : bool
        Save debug visualizations for each frame.
    
    Returns
    -------
    results : List[Dict]
        Segmentation results for each timepoint.
    segmenter : QuantificationSegmenter
        Segmenter instance (can access final state).
    
    Examples
    --------
     results, seg = process_trajectory(image_paths, output_dir=Path("output"))
     print(f"t=0 area: {results[0]['area']}")
     print(f"t=N area: {results[-1]['area']}")
    """
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    
    segmenter = QuantificationSegmenter(config=config)
    results: List[Dict] = []
    
    iterator = tqdm(
        enumerate(image_paths),
        total=len(image_paths),
        desc="Processing trajectory",
        disable=not verbose,
    )
    
    for t, img_path in iterator:
        img_path = Path(img_path)
        
        # Debug save path
        debug_path = None
        if save_debug and output_dir:
            debug_path = output_dir / f"debug_t{t:03d}_{img_path.stem}.png"
        
        try:
            result = segmenter.segment(
                img=img_path,
                t=t,
                file_name=img_path,
                debug=save_debug,
                save_path=debug_path,
            )
            
            # Convert to dict for compatibility
            result_dict = {
                "t": result.t,
                "file_name": result.file_name,
                "img_raw": result.img_raw,
                "mask": result.mask,
                "upper_edge": result.upper_edge,
                "lower_edge": result.lower_edge,
                "area": result.area,
                "qc": result.qc,
                "method": result.method,
                "constrained": result.constrained,
            }
            results.append(result_dict)
            
            if verbose:
                iterator.set_postfix(area=result.area, method=result.method)
        
        except Exception as e:
            warnings.warn(f"Failed to process  \n\t{img_path}: \n\t\t{e}")
            results.append({
                "t": t,
                "file_name": img_path,
                "img_raw": None,
                "mask": None,
                "area": None,
                "error": str(e),
            })
    
    # Save results
    if output_dir:
        save_trajectory_results(results, output_dir)
    
    return results, segmenter


# import cv2
#
# img = cv2.imread(img_path)
#
# if img is None:
#     raise FileNotFoundError(f"Could not read image at {img_path}")
#
# # Optional: convert BGR → RGB
# img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)



def save_trajectory_results(
    results: List[Dict],
    output_dir: Path,
) -> None:
    """
    Save trajectory results to disk.
    
    Saves:
    - experiment.pkl: Full results with masks and images
    - summary.csv: Lightweight summary table
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save full pickle
    pkl_path = output_dir / "experiment.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump({"experiment": {"results": results}}, f)
    
    # Save lightweight summary
    import pandas as pd
    summary_rows = []
    for r in results:
        if r.get("area") is not None:
            summary_rows.append({
                "t": r["t"],
                "file_name": str(r["file_name"]) if r.get("file_name") else None,
                "area": r["area"],
                "method": r.get("method"),
                "constrained": r.get("constrained"),
                "qc_valid": r.get("qc", {}).get("valid"),
            })
    
    if summary_rows:
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_csv(output_dir / "summary.csv", index=False)
        
        # Generate wound area trajectory plot
        plot_wound_trajectory(df_summary, output_dir)


def plot_wound_trajectory(
    df_summary: "pd.DataFrame",
    output_dir: Path,
    title: str = None,
) -> None:
    """
    Create and save a scatter plot of wound area over time.
    
    Parameters
    ----------
    df_summary : pd.DataFrame
        Summary dataframe with 't' and 'area' columns.
    output_dir : Path
        Directory to save the plot.
    title : str | None
        Custom title. If None, uses folder name.
    """
    import matplotlib.pyplot as plt
    
    output_dir = Path(output_dir)
    
    # Extract data
    t = df_summary["t"].values
    area = df_summary["area"].values
    
    # Calculate normalized area (percent of initial)
    if len(area) > 0 and area[0] > 0:
        area_pct = (area / area[0]) * 100
    else:
        area_pct = area
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: Absolute wound area
    ax1.scatter(t, area, c='steelblue', s=60, alpha=0.8, edgecolors='navy', linewidths=0.5)
    ax1.plot(t, area, c='steelblue', alpha=0.5, linewidth=1)
    ax1.set_xlabel("Time (frames)", fontsize=11)
    ax1.set_ylabel("Wound Area (pixels)", fontsize=11)
    ax1.set_title("Wound Area Over Time", fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(left=-0.5)
    ax1.set_ylim(bottom=0)
    
    # Plot 2: Normalized wound area (% of initial)
    ax2.scatter(t, area_pct, c='forestgreen', s=60, alpha=0.8, edgecolors='darkgreen', linewidths=0.5)
    ax2.plot(t, area_pct, c='forestgreen', alpha=0.5, linewidth=1)
    ax2.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='Initial (100%)')
    ax2.set_xlabel("Time (frames)", fontsize=11)
    ax2.set_ylabel("Wound Area (% of initial)", fontsize=11)
    ax2.set_title("Wound Closure Progress", fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(left=-0.5)
    ax2.set_ylim(0, 110)
    ax2.legend(loc='upper right')
    
    # Add sample name as suptitle
    sample_name = title or output_dir.name
    fig.suptitle(sample_name, fontsize=13, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    # Save plot
    plot_path = output_dir / "wound_trajectory.png"
    fig.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def load_trajectory_results(output_dir: Path) -> List[Dict]:
    """Load trajectory results from disk."""
    import sys
    import pathlib
    
    pkl_path = output_dir / "experiment.pkl"
    
    # Handle pathlib module issue
    sys.modules["pathlib._local"] = pathlib
    
    try:
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError) as e:
        raise RuntimeError(f"Failed to load: {pkl_path}\n{e}")
    
    if "experiment" in data:
        return data["experiment"]["results"]
    return data.get("results", data)
