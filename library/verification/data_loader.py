"""
Data Loader
===========

Load the master trajectories pickle produced by the Gemini pipeline and
extract the t=0 records needed for manual verification.

The master pickle (``trajectories.pickle``) contains all trajectory data
keyed by identifier string.  Each trajectory stores a list of per-timepoint
result dicts.  We only need t=0 for verification: the raw grayscale image,
the binary wound mask, QC metrics, and metadata.

Debug PNG paths are resolved by scanning the per-sample subdirectories
under the gemini_results root.
"""

from __future__ import annotations

import glob
import pathlib
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Pickle compatibility
# ---------------------------------------------------------------------------
# Pickles saved on newer Python may reference ``pathlib._local`` which does
# not exist on older builds.  Aliasing it avoids an ImportError.
sys.modules["pathlib._local"] = pathlib


def load_master_trajectories(pickle_path: Path) -> Dict[str, Any]:
    """Load the master trajectories dictionary from disk.

    Parameters
    ----------
    pickle_path : Path
        Absolute path to ``trajectories.pickle``.

    Returns
    -------
    dict
        Mapping ``{trajectory_key: {results, sample_out_dir, exposure, ...}}``.

    Raises
    ------
    FileNotFoundError
        If *pickle_path* does not exist.
    RuntimeError
        If the pickle cannot be deserialised.
    """
    pickle_path = Path(pickle_path)
    if not pickle_path.exists():
        raise FileNotFoundError(f"Master pickle not found: {pickle_path}")

    try:
        with open(pickle_path, "rb") as fh:
            data = pickle.load(fh)
    except (OSError, pickle.PickleError, EOFError) as exc:
        raise RuntimeError(f"Failed to load pickle: {pickle_path}\n{exc}") from exc

    return data


def _resolve_debug_png(gemini_root: Path, key: str) -> Optional[Path]:
    """Find the t=0 debug PNG for a trajectory key.

    The Gemini pipeline saves debug images as
    ``{gemini_root}/{key}/debug_t000_*.png``.  We glob for the pattern
    and return the first match (there should be exactly one).

    Parameters
    ----------
    gemini_root : Path
        Root directory of gemini results (contains per-key subdirectories).
    key : str
        Trajectory identifier (matches the subdirectory name).

    Returns
    -------
    Path or None
        Absolute path to the debug PNG, or ``None`` if not found.
    """
    sample_dir = gemini_root / key
    if not sample_dir.is_dir():
        return None
    matches = glob.glob(str(sample_dir / "debug_t000_*.png"))
    if matches:
        return Path(matches[0])
    return None


def extract_t0_records(
    trajectories: Dict[str, Any],
    gemini_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Extract t=0 data from every trajectory for verification.

    Parameters
    ----------
    trajectories : dict
        Master trajectories dictionary (from :func:`load_master_trajectories`).
    gemini_root : Path or None, optional
        Root directory containing per-sample subdirectories with debug PNGs.
        If None, debug PNG paths are omitted.

    Returns
    -------
    list of dict
        Each dict contains:
        - ``trajectory_key`` : str
        - ``img_raw``        : np.ndarray (H, W) uint8
        - ``mask``           : np.ndarray (H, W) uint8, binary {0, 1}
        - ``qc_valid``       : bool
        - ``qc_details``     : dict (full QC metrics)
        - ``debug_png_path`` : Path | None
        - ``exposure``       : str
        - ``experiment``     : str
        - ``sample_name``    : str
        - ``original_filename`` : str
        - ``img_shape``      : tuple (H, W)

    Notes
    -----
    Trajectories whose t=0 ``img_raw`` is ``None`` (failed processing) are
    silently skipped.
    """
    gemini_root = Path(gemini_root) if gemini_root is not None else None
    records: List[Dict[str, Any]] = []

    for key, traj in trajectories.items():
        results = traj.get("results", [])
        if not results:
            continue

        r0 = results[0]
        img_raw = r0.get("img_raw")
        mask = r0.get("mask")

        # Skip failed segmentations
        if img_raw is None or mask is None:
            continue

        qc = r0.get("qc", {})

        records.append({
            "trajectory_key": key,
            "img_raw": img_raw,
            "mask": mask,
            "upper_edge": r0.get("upper_edge"),
            "lower_edge": r0.get("lower_edge"),
            "qc_valid": bool(qc.get("valid", False)),
            "qc_details": qc,
            "debug_png_path": _resolve_debug_png(gemini_root, key) if gemini_root is not None else None,
            "exposure": traj.get("exposure", ""),
            "experiment": traj.get("experiment", ""),
            "sample_name": traj.get("sample_name", ""),
            "original_filename": Path(r0.get("file_name", "")).name,
            "img_shape": (img_raw.shape[0], img_raw.shape[1]),
        })

    # Sort by key for deterministic ordering
    records.sort(key=lambda r: r["trajectory_key"])
    return records
