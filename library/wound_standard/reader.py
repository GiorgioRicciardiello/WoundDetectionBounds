"""
Filename Parsing and Image Grouping
====================================

Parse wound-healing microscopy filenames that follow the convention::

    {CELL}_{REPLICATE}_{WELL}_{DD}d{HH}h{MM}m.tif_crop.jpg

and group them by sample identity for batch processing.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def parse_filename_time(file_path: Path) -> Dict:
    """Parse a wound-image filename into structured metadata.

    Parameters
    ----------
    file_path : Path
        Image file path matching the naming convention.

    Returns
    -------
    info : dict
        Keys: ``cell``, ``replicate``, ``well``, ``days``, ``hours``,
        ``minutes``, ``total_minutes``, ``filename``.

    Raises
    ------
    ValueError
        If the filename does not match the expected pattern.
    """
    fname = Path(file_path).name

    m = re.match(
        r"^([A-Za-z0-9]+)_([A-Za-z0-9]+)_([0-9]+)_([0-9]+)d([0-9]+)h([0-9]+)m",
        fname,
    )
    if not m:
        raise ValueError(f"Filename not recognized: {fname}")

    cell = m.group(1)
    replicate = m.group(2)
    well = m.group(3)
    days = int(m.group(4))
    hours = int(m.group(5))
    minutes = int(m.group(6))

    total_minutes = days * 1440 + hours * 60 + minutes

    return {
        "cell": cell,
        "replicate": replicate,
        "well": well,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "total_minutes": total_minutes,
        "filename": file_path,
    }


def group_and_sort_images(
    file_paths: List[Path],
) -> Dict[Tuple[str, str, str], List[Path]]:
    """Group image paths by sample identity and sort by time.

    Parameters
    ----------
    file_paths : list of Path
        Unordered image paths.

    Returns
    -------
    sorted_groups : dict
        ``{(cell, replicate, well): [path_t0, path_t1, ...]}``
    """
    groups: Dict[Tuple[str, str, str], List] = defaultdict(list)

    for fp in file_paths:
        info = parse_filename_time(fp)
        key = (info["cell"], info["replicate"], info["well"])
        groups[key].append(info)

    sorted_groups = {}
    for key, lst in groups.items():
        lst_sorted = sorted(lst, key=lambda x: x["total_minutes"])
        sorted_groups[key] = [x["filename"] for x in lst_sorted]

    return sorted_groups
