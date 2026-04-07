"""
Filtering Library
==================

Analysis and filtering tools for wound healing trajectories.

Modules:
- timeseries: Time-series analysis (all time points)
- cross_sectional: Single-timepoint analysis
- manual_check: Manual annotation export/import
"""

from library.filtering.timeseries import (
    distance_calculator_timeseries,
    plot_timeseries_by_condition,
    plot_timeseries_grouped,
)

from library.filtering.cross_sectional import (
    distance_calculator,
    filter_trajectories_by_t0_wound_distribution,
    select_best_experiments_across_wells_cross_sectional,
    plot_speed_by_cellline_condition,
    select_closest_times,
)

from library.filtering.manual_check import (
    export_t0_images_for_annotation,
    load_annotations,
    filter_trajectories_by_annotation,
)

__all__ = [
    # Time-series
    "distance_calculator_timeseries",
    "plot_timeseries_by_condition",
    "plot_timeseries_grouped",
    # Cross-sectional
    "distance_calculator",
    "filter_trajectories_by_t0_wound_distribution",
    "select_best_experiments_across_wells_cross_sectional",
    "plot_speed_by_cellline_condition",
    "select_closest_times",
    # Manual check
    "export_t0_images_for_annotation",
    "load_annotations",
    "filter_trajectories_by_annotation",
]
