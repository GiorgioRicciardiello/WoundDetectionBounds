"""
woundtrack.io
=============

Conversion and persistence utilities.
Handles raw dict <-> typed model conversion and disk I/O for ML training.
"""

from typing import Any, Dict, List, Optional, Union

import numpy as np

from .types import TrajectoriesDict, Trajectory, TrajectoryResult

__all__ = [
    "from_raw_trajectories",
    "export_pairs_t0",
]

def from_raw_trajectories(raw: TrajectoriesDict) -> Dict[str, Trajectory]:
    """
    Convert your existing raw `trajectories` dict into typed `Trajectory` objects.

    Parameters
    ----------
    raw:
        Original nested dict:
            raw[key]["results"] -> list of dict timepoints

    Returns
    -------
    Dict[str, Trajectory]
        Typed trajectories keyed by the same trajectory keys.
    """
    out: Dict[str, Trajectory] = {}

    for key, td in raw.items():
        results_raw = td.get("results", [])
        results: List[TrajectoryResult] = []
        for r in results_raw:
            results.append(
                TrajectoryResult(
                    t=r.get("t"),
                    img_raw=r.get("img_raw"),
                    mask=r.get("mask"),
                    area=r.get("area"),
                    y_upper=r.get("y_upper"),
                    y_lower=r.get("y_lower"),
                    overlay=r.get("overlay"),
                    file_name=r.get("file_name"),
                )
            )

        out[key] = Trajectory(
            results=results,
            sample_out_dir=td.get("sample_out_dir"),
            exposure=td.get("exposure"),
            experiment=td.get("experiment"),
            sample_name=td.get("sample_name"),
        )

    return out



# =============================================================================
# Export utilities for ML training
# =============================================================================

def export_pairs_t0(
    trajectories: TrajectoriesDict,
    out_dir: Union[str, "os.PathLike[str]"],
    image_ext: str = ".png",
    mask_ext: str = ".png",
    overwrite: bool = False,
) -> "np.ndarray":
    """
    Export (img_raw, mask) pairs at t=0 for segmentation training.

    This creates:
    - {out_dir}/images/{trajectory_key}{image_ext}
    - {out_dir}/masks/{trajectory_key}{mask_ext}

    Parameters
    ----------
    trajectories:
        Raw trajectories dict.
    out_dir:
        Output directory.
    image_ext, mask_ext:
        File extensions for saved images/masks.
    overwrite:
        If False, skip existing files.

    Returns
    -------
    np.ndarray
        Array of exported keys (strings) for bookkeeping.

    Notes
    -----
    - Uses imageio.v3 if available; falls back to PIL if available.
    - Masks are saved as 0/255 uint8.
    """
    import os
    from pathlib import Path

    out_dir = Path(out_dir)
    img_dir = out_dir / "images"
    msk_dir = out_dir / "masks"
    img_dir.mkdir(parents=True, exist_ok=True)
    msk_dir.mkdir(parents=True, exist_ok=True)

    # writer
    writer = None
    try:
        import imageio.v3 as iio
        writer = ("imageio", iio)
    except Exception:
        try:
            from PIL import Image
            writer = ("pil", Image)
        except Exception:
            raise ImportError("Install imageio or pillow to export images/masks.")

    exported: List[str] = []

    for traj_key, traj_data in trajectories.items():
        results = traj_data.get("results", [])
        r0 = next((r for r in results if r.get("t") == 0), None)
        if r0 is None:
            continue

        img = r0.get("img_raw", None)
        mask = r0.get("mask", None)
        if img is None or mask is None:
            continue

        img_path = img_dir / f"{traj_key}{image_ext}"
        msk_path = msk_dir / f"{traj_key}{mask_ext}"
        if (not overwrite) and (img_path.exists() or msk_path.exists()):
            continue

        img_arr = np.asarray(img)
        msk_arr = (np.asarray(mask).astype(bool) * 255).astype(np.uint8)

        if writer[0] == "imageio":
            _, iio = writer
            iio.imwrite(img_path, img_arr)
            iio.imwrite(msk_path, msk_arr)
        else:
            _, Image = writer
            Image.fromarray(img_arr).save(img_path)
            Image.fromarray(msk_arr).save(msk_path)

        exported.append(traj_key)

    return np.array(exported, dtype=object)
