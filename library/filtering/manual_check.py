"""
Manual Annotation Library for Wound Healing Trajectories
=========================================================

Export t=0 images for manual annotation/curation,
and utilities for loading and applying annotations.

Functions:
- export_t0_images_for_annotation: Export images and create annotation Excel
- load_annotations: Load completed annotation file
- filter_trajectories_by_annotation: Apply annotations to filter trajectories
"""

from pathlib import Path
from typing import Dict, Union
import pickle

import numpy as np
import pandas as pd
import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm


def pickle_io(path: Union[str, Path], obj=None, save: bool = True):
    """Save or load an object using pickle."""
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


def export_t0_images_for_annotation(
    trajectories: Dict,
    output_dir: Path,
    legacy_df: pd.DataFrame = None,
    image_format: str = "png",
    show_overlay: bool = False,
    figsize: tuple = (8, 6),
    dpi: int = 100,
) -> pd.DataFrame:
    """
    Export t=0 images from all trajectories for manual annotation.
    
    Creates:
    - Images: {output_dir}/{trajectory_key}.{image_format}
    - Excel: {output_dir}/annotation_sheet.xlsx
    
    Parameters
    ----------
    trajectories : Dict
        Trajectories dictionary from wound healing pipeline.
        Each entry should have 'results' list with t=0 data.
    output_dir : Path
        Directory to save images and annotation sheet.
    legacy_df : pd.DataFrame, optional
        Optional legacy mapping table for additional metadata.
    image_format : str
        Image format (png, jpg). Default "png".
    show_overlay : bool
        If True, overlay wound mask on image. Default True.
    figsize : tuple
        Figure size for saving. Default (8, 6).
    dpi : int
        Image resolution. Default 100.
    
    Returns
    -------
    pd.DataFrame
        Annotation sheet with columns: trajectory_key, filename, keep
    
    Examples
    --------
    from library.filtering.manual_check import export_t0_images_for_annotation
    df_anno = export_t0_images_for_annotation(
         trajectories=trajectories,
         output_dir=Path("output/manual_check"),
     )
    print(f"Exported {len(df_anno)} images for annotation")
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    annotation_rows = []
    
    for traj_key, traj_data in tqdm(
        trajectories.items(),
        desc="Exporting t=0 images",
        total=len(trajectories),
    ):
        results = traj_data.get("results", [])
        
        # Find t=0 entry
        t0_entry = next((r for r in results if r.get("t") == 0), None)
        
        if t0_entry is None:
            print(f"  Warning: No t=0 found for {traj_key}")
            continue
        
        img_raw = t0_entry.get("img_raw")
        mask = t0_entry.get("mask")
        
        if img_raw is None:
            print(f"  Warning: No image found for {traj_key}")
            continue
        
        # Prepare image
        img = np.asarray(img_raw)
        if img.ndim == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Display image
        ax.imshow(img_gray, cmap="gray")
        
        # Overlay mask if available and requested
        if show_overlay and mask is not None:
            mask_array = np.asarray(mask).astype(bool)
            
            # Create colored overlay
            overlay = np.zeros((*mask_array.shape, 4), dtype=np.float32)
            overlay[mask_array, 0] = 0.2  # Red
            overlay[mask_array, 1] = 0.6  # Green
            overlay[mask_array, 2] = 0.8  # Blue
            overlay[mask_array, 3] = 0.3  # Alpha
            
            ax.imshow(overlay, aspect="equal")
            
            # Draw wound edges
            H, W = mask_array.shape
            for x in range(W):
                ys = np.where(mask_array[:, x])[0]
                if ys.size > 0:
                    ax.plot(x, ys.min(), 'c.', markersize=0.5, alpha=0.5)
                    ax.plot(x, ys.max(), 'm.', markersize=0.5, alpha=0.5)
        
        # Title and aesthetics
        ax.set_title(f"{traj_key} (t=0)", fontsize=10)
        ax.axis("off")
        plt.tight_layout(pad=0.5)
        
        # Save image
        filename = f"{traj_key}.{image_format}"
        filepath = output_dir / filename
        fig.savefig(filepath, dpi=dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        
        # Add to annotation table
        annotation_rows.append({
            "trajectory_key": traj_key,
            "filename": filename,
            "keep": True,  # Default: keep all
        })
    
    # Create annotation DataFrame
    df_annotation = pd.DataFrame(annotation_rows)
    
    # Add metadata if legacy_df provided
    if legacy_df is not None and "identifier" in legacy_df.columns:
        df_annotation = pd.merge(
            df_annotation,
            legacy_df[["identifier", "cell_line", "sample_condition", "concentration_mm"]].drop_duplicates(),
            left_on="trajectory_key",
            right_on="identifier",
            how="left",
        )
    
    # Save annotation sheet
    annotation_path = output_dir / "annotation_sheet.xlsx"
    df_annotation.to_excel(annotation_path, index=False)
    
    print(f"\n✓ Exported {len(df_annotation)} images to: {output_dir}")
    print(f"✓ Annotation sheet saved to: {annotation_path}")
    print("\nInstructions:")
    print("  1. Review the images in the output folder")
    print("  2. Open annotation_sheet.xlsx")
    print("  3. Set 'keep' = FALSE for trajectories to exclude")
    print("  4. Save the Excel file")
    print("  5. Use load_annotations() to load your decisions")
    
    return df_annotation


def load_annotations(
    annotation_path: Path,
    trajectory_col: str = "trajectory_key",
    keep_col: str = "keep",
) -> Dict[str, bool]:
    """
    Load completed annotations from Excel file.
    
    Parameters
    ----------
    annotation_path : Path
        Path to the annotation Excel file.
    trajectory_col : str
        Column containing trajectory keys. Default "trajectory_key".
    keep_col : str
        Column containing keep decisions. Default "keep".
    
    Returns
    -------
    Dict[str, bool]
        Dictionary mapping trajectory_key -> keep (bool)
    
    Examples
    --------
    annotations = load_annotations(Path("output/manual_check/annotation_sheet.xlsx"))
    kept_keys = [k for k, v in annotations.items() if v]
    print(f"Keeping {len(kept_keys)} trajectories")
    """
    annotation_path = Path(annotation_path)
    
    if not annotation_path.exists():
        raise FileNotFoundError(f"Annotation file not found: {annotation_path}")
    
    df = pd.read_excel(annotation_path)
    
    if trajectory_col not in df.columns:
        raise ValueError(f"Column '{trajectory_col}' not found in annotation file")
    if keep_col not in df.columns:
        raise ValueError(f"Column '{keep_col}' not found in annotation file")
    
    # Convert to dictionary
    annotations = dict(zip(df[trajectory_col], df[keep_col].astype(bool)))
    
    n_keep = sum(annotations.values())
    n_total = len(annotations)
    print(f"Loaded annotations: {n_keep}/{n_total} marked as keep")
    
    return annotations


def filter_trajectories_by_annotation(
    trajectories: Dict,
    annotations: Dict[str, bool],
) -> Dict:
    """
    Filter trajectories based on manual annotation.
    
    Parameters
    ----------
    trajectories : Dict
        Original trajectories dictionary.
    annotations : Dict[str, bool]
        Dictionary mapping trajectory_key -> keep (bool).
    
    Returns
    -------
    Dict
        Filtered trajectories containing only those marked as keep=True.
    
    Examples
    --------
    annotations = load_annotations(annotation_path)
    filtered = filter_trajectories_by_annotation(trajectories, annotations)
    print(f"Filtered to {len(filtered)} trajectories")
    """
    filtered = {}
    
    for traj_key, traj_data in trajectories.items():
        # Default to keep if not in annotations
        keep = annotations.get(traj_key, True)
        if keep:
            filtered[traj_key] = traj_data
    
    n_original = len(trajectories)
    n_filtered = len(filtered)
    n_removed = n_original - n_filtered
    
    print(f"Filtered: {n_filtered}/{n_original} trajectories kept ({n_removed} removed)")
    
    return filtered


def get_annotation_summary(annotation_path: Path) -> pd.DataFrame:
    """
    Get summary statistics from annotation file.
    
    Parameters
    ----------
    annotation_path : Path
        Path to annotation Excel file.
    
    Returns
    -------
    pd.DataFrame
        Summary counts by cell_line, sample_condition, etc.
    """
    df = pd.read_excel(annotation_path)
    
    summary_cols = ["cell_line", "sample_condition", "concentration_mm"]
    available_cols = [c for c in summary_cols if c in df.columns]
    
    if not available_cols:
        # Simple summary
        return pd.DataFrame({
            "total": [len(df)],
            "keep_true": [df["keep"].sum()],
            "keep_false": [(~df["keep"]).sum()],
        })
    
    # Group summary
    summary = (
        df.groupby(available_cols)
        .agg(
            total=("keep", "count"),
            keep_true=("keep", "sum"),
        )
        .reset_index()
    )
    summary["keep_false"] = summary["total"] - summary["keep_true"]
    summary["keep_pct"] = (summary["keep_true"] / summary["total"] * 100).round(1)
    
    return summary
