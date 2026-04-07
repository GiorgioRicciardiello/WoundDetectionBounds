"""
Batch Wound Segmentation for Time-Series
=========================================

Process ordered image sequences through the standard
:class:`~library.wound_standard.segmenter.WoundSegmenter`.
"""

from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from library.wound_standard.segmenter import WoundSegmenter


def process_slice(
    paths: List[Path],
    res_dir: Optional[Path] = None,
) -> Tuple[List[Dict], Optional[pd.DataFrame]]:
    """Segment a slice of time-ordered images and optionally generate a report.

    Parameters
    ----------
    paths : list of Path
        Time-ordered image paths (``t=0`` first).
    res_dir : Path | None
        Output directory.  Created if it does not exist.

    Returns
    -------
    results : list of dict
        Per-frame segmentation results.
    df_summary : pd.DataFrame | None
        Summary table (requires ``library.visualization``).
    """
    if res_dir:
        res_dir.mkdir(exist_ok=True, parents=True)

    results = _segment_wound_video(
        image_paths=paths,
        res_dir=res_dir,
        verbose_first=False,
        verbose_steps=False,
    )

    # Generate report if visualization module is available
    df_summary = None
    try:
        from library.visualization.visualization import report
        df_summary = report(results, save_dir=res_dir)
    except ImportError:
        pass

    return results, df_summary


def _segment_wound_video(
    image_paths: List[Union[np.ndarray, Path]],
    res_dir: Optional[Path] = None,
    verbose_first: bool = False,
    verbose_steps: bool = False,
) -> List[Dict]:
    """Segment wounds across a time-series with monotonic constraint.

    Frame 0 establishes the wound container (unconstrained anchor).
    Subsequent frames are intersected with the previous boundary to
    guarantee monotonic closure.

    Parameters
    ----------
    image_paths : list
        Ordered image paths or arrays.
    res_dir : Path | None
        Output directory for per-frame overlays.
    verbose_first : bool
        Verbose output for frame 0.
    verbose_steps : bool
        Verbose output for subsequent frames.

    Returns
    -------
    results : list of dict
        Per-frame results containing ``img_raw``, ``mask``, ``area``,
        ``y_upper``, ``y_lower``, ``overlay``, ``t``, ``file_name``.
    """
    results: List[Dict] = []

    segmenter = WoundSegmenter(
        y_upper_prev=None,
        y_lower_prev=None,
        constrain=False,
    )

    # Frame 0 - anchor
    img_first = image_paths[0]
    if verbose_first:
        tqdm.write(f"Frame 0 (anchor): {img_first}")

    w0 = segmenter.segment(
        img_raw=img_first,
        verbose=verbose_first,
        path_out=res_dir.joinpath(img_first.stem.split(".")[0]) if res_dir else None,
    )
    w0["t"] = 0
    w0["file_name"] = img_first
    results.append(w0)

    # Frames t > 0 - constrained
    for t, img_path in tqdm(
        enumerate(image_paths[1:], start=1),
        total=len(image_paths) - 1,
        desc="Segmenting frames",
        unit="frame",
    ):
        if verbose_steps:
            tqdm.write(f"Frame {t}: {img_path}")

        wt = segmenter.segment(
            img_raw=img_path,
            verbose=verbose_steps,
            time=t,
            path_out=res_dir.joinpath(img_path.stem.split(".")[0]) if res_dir else None,
        )
        wt["t"] = t
        wt["file_name"] = img_path
        results.append(wt)

    segmenter.reset()

    return results
