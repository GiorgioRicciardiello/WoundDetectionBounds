# Filtering Library

Analysis and filtering tools for wound healing trajectories.

## Modules

### `timeseries.py`
Time-series analysis computing distance/speed across **all** time points.

**Functions:**
- `distance_calculator_timeseries()` - Compute wound edge displacement for every time point vs t=0
- `plot_timeseries_by_condition()` - Line plots faceted by cell line
- `plot_timeseries_grouped()` - Subplots per concentration with line style per condition

### `cross_sectional.py`
Single-timepoint (cross-sectional) analysis for comparing conditions at specific time.

**Functions:**
- `distance_calculator()` - Compute speed/distance at a single target time
- `filter_trajectories_by_t0_wound_distribution()` - QC filter using t=0 wound mask
- `select_best_experiments_across_wells_cross_sectional()` - Select wells closest to mean
- `plot_speed_by_cellline_condition()` - Bar plots grouped by cell line and condition

**Note on speed units:** The `t` values in trajectory results are frame indices, not hours.
Speed outputs (`speed_mean`, `speed_upper`, `speed_lower`) are therefore in **pixels/frame**,
not pixels/hour. To convert to physical units, divide by the imaging interval (e.g., 2 h/frame
for typical Incucyte acquisitions) and multiply by the pixel calibration (1.24 µm/px).

### `manual_check.py`
Export t=0 images for manual annotation/curation.

**Functions:**
- `export_t0_images_for_annotation()` - Export images and create annotation Excel
- `load_annotations()` - Load completed annotation file
- `filter_trajectories_by_annotation()` - Apply annotations to filter trajectories

## Usage

```python
from library.filtering import (
    distance_calculator_timeseries,
    distance_calculator,
    export_t0_images_for_annotation,
)
```

## Caller Scripts

See `scripts/` folder:
- `run_timeseries_analysis.py`
- `run_cross_sectional_analysis.py`
- `run_manual_annotation_export.py`
