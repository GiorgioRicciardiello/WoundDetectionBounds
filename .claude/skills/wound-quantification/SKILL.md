---
name: wound-quantification
description: Run and configure the WoundDetectionBounds scratch-wound quantification pipeline. Use when processing wound healing images, configuring the Kalman filter or hard monotonic constraint, computing wound metrics (distance, speed, closure), generating publication figures, or troubleshooting segmentation issues. Covers the full pipeline from raw Incucyte images to publication-ready outputs.
---

# Wound Quantification Pipeline

## Overview

WoundDetectionBounds is a fully automated scratch-wound healing quantification pipeline. It segments wound boundaries from phase-contrast time-lapse microscopy using local variance texture analysis and enforces a biologically motivated monotonic closure constraint (Kalman-filtered by default) across the temporal sequence.

## When to Use This Skill

- Running the segmentation pipeline (`main.py`)
- Configuring constraint strategy (Kalman vs hard)
- Tuning detector parameters (`WoundDetectorConfig`)
- Computing wound metrics (distance, speed, closure)
- Generating publication figures and statistical tables
- Debugging segmentation failures or QC issues
- Comparing results across configurations

---

## Architecture

```
Raw Incucyte images
    |
    v  organize_experiments()
Organized images ({exposure}/{experiment}/{sample}/*.tif)
    |
    v  main.py -> run_quantification_pipeline()
WoundDetector (single-frame, 7-stage)
    -> QuantificationSegmenter (temporal constraint)
        -> Kalman filter (default) OR hard max/min
    |
    v  output_dir/{model_key}/
trajectories.pickle, final_legacy_table.xlsx, per-sample experiment.pkl
    |
    v  python -m scripts.publication.generate_figures
paper_publication/fig1_model_quality.{png,pdf}
paper_publication/fig2_wound_dynamics.{png,pdf}
paper_publication/tables/{statistics,supplementary_tables}.xlsx
```

## Key Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `WoundDetector` | `library/wound_standard/detector.py` | 7-stage single-frame detection (variance map, Y-band, edge extraction, RANSAC, Savgol, mask, QC) |
| `QuantificationSegmenter` | `library/wound_quantification/segmenter.py` | Stateful temporal integrator with Kalman or hard constraint |
| `KalmanEdgeFilter` | `library/wound_quantification/kalman_constraint.py` | Per-column 1-D Kalman filter with data-driven Q/R estimation |
| `process_trajectory` | `library/wound_quantification/trajectory.py` | Batch time-series processing for one sample |
| `distance_calculator` | `library/filtering/cross_sectional.py` | Cross-sectional speed/distance at a target timepoint |
| `distance_calculator_timeseries` | `library/filtering/timeseries.py` | Time-series speed/distance for all timepoints |
| `verify_wound_by_distribution` | `library/woundtrack/qc.py` | Canonical t=0 QC validation |
| `generate_figures.py` | `scripts/publication/generate_figures.py` | Publication figure orchestrator |

## Configuration

All pipeline parameters live in `WoundDetectorConfig` (`library/core/types.py`):

```python
from library.core.types import WoundDetectorConfig

# Default: Kalman filter enabled, all params auto-tuned
cfg = WoundDetectorConfig()

# Disable Kalman (legacy hard constraint)
cfg = WoundDetectorConfig(use_kalman=False)

# Override Kalman parameters
cfg = WoundDetectorConfig(
    use_kalman=True,
    kalman_Q=400.0,           # Process noise (None = data-driven)
    kalman_R_base=None,       # Observation noise (None = data-driven)
    kalman_fallback_multiplier=3.0,  # R multiplier for fallback detections
    kalman_spatial_sigma=5.0,        # Spatial smoothing before Kalman update
)

# Override detector parameters
cfg = WoundDetectorConfig(
    variance_window=15,            # Stage 1: local variance kernel size
    variance_sigma=2.0,            # Stage 1: Gaussian post-smoothing
    y_profile_sigma=10.0,          # Stage 2: Y-band profile smoothing
    y_band_percentile=35.0,        # Stage 2: wound band threshold
    edge_threshold_percentile=40.0, # Stage 3: fallback edge threshold
    ransac_poly_degree=2,          # Stage 4: RANSAC polynomial degree
    ransac_max_deviation=25.0,     # Stage 4: outlier deviation threshold
    smoothing_window=51,           # Stage 5: Savgol window length
    fallback_enabled=True,         # Stage 7: region-growing fallback
)
```

## Running the Pipeline

### Step 1: Segmentation

```python
# In main.py or custom script
from library.core.types import WoundDetectorConfig
from main import run_quantification_pipeline

cfg = WoundDetectorConfig(use_kalman=True)

df_final, trajectories = run_quantification_pipeline(
    image_folder=Path("path/to/organized/images"),
    output_root=Path("path/to/output"),
    exposures=["alk5i", "Candasertan"],
    experiments=["EXP1", "EXP2"],
    process_missing=True,
    save_debug=True,
    n_workers=10,
    detector_config=cfg,
)
```

### Step 2: Publication Figures

```bash
python -m scripts.publication.generate_figures
```

### Single-Sample Processing

```python
from library.wound_quantification.trajectory import process_trajectory
from library.core.types import WoundDetectorConfig

cfg = WoundDetectorConfig(use_kalman=True)
results, segmenter = process_trajectory(
    image_paths=[Path("t0.tif"), Path("t1.tif"), ...],
    output_dir=Path("output/sample_1"),
    config=cfg,
    save_debug=True,
)

# Each result dict contains:
# t, file_name, img_raw, mask, upper_edge, lower_edge, area, qc, method, constrained
```

### Single-Frame Detection

```python
from library.wound_standard.detector import WoundDetector
from library.core.types import WoundDetectorConfig

detector = WoundDetector(WoundDetectorConfig())
result = detector.detect(grayscale_image, debug=True, save_path=Path("debug.png"))

# result: WoundResult with mask, upper_edge, lower_edge, qc, method
# result.qc["valid"] -> bool
```

## Kalman Filter: How It Works

### Two Constraint Strategies

| | Kalman (default) | Hard |
|---|---|---|
| **Config** | `use_kalman=True` | `use_kalman=False` |
| **Mechanism** | Kalman blend + hard safety net | `np.maximum` / `np.minimum` |
| **Spurious edge handling** | Attenuated (high R -> trusts prediction) | Permanently locked |
| **`constrained` flag** | True when safety net modified edges | True when edges were clamped |

### Q/R Parameter Resolution

**Q (process noise)** -- how much the true edge moves per frame:
1. `WoundDetectorConfig.kalman_Q` if not None -> use explicitly
2. `estimate_Q_from_trajectories(trajectories, clean_keys=...)` -> data-driven from cached results
3. `DEFAULT_Q = 400.0 px^2` -> conservative fallback (first run)

**R (observation noise)** -- how noisy the detector is per column per frame:
- Estimated automatically from: variance contrast, edge residuals, jump magnitude, detection method
- Override baseline via `WoundDetectorConfig.kalman_R_base`

### Estimating Q from Existing Data

```python
from library.wound_quantification.kalman_constraint import estimate_Q_from_trajectories

# From QC-passing trajectories (default)
Q = estimate_Q_from_trajectories(trajectories)

# From explicit list
Q = estimate_Q_from_trajectories(trajectories, clean_keys=["sample1-EXP1-alk5i", ...])

# From all trajectories (no QC filter)
Q = estimate_Q_from_trajectories(trajectories, use_qc_filter=False)

# Use estimated Q in config
cfg = WoundDetectorConfig(use_kalman=True, kalman_Q=Q)
```

## Downstream Metrics

### Cross-Sectional (Single Timepoint)

```python
from library.filtering.cross_sectional import distance_calculator

df_cs = distance_calculator(trajectories, t_target=20.0)
# Columns: trajectory, t_used, area_t0, area_tT,
#           distance_upper, distance_lower, distance_mean,
#           speed_upper, speed_lower, speed_mean, is_closing
```

### Time-Series (All Timepoints)

```python
from library.filtering.timeseries import distance_calculator_timeseries

df_ts = distance_calculator_timeseries(trajectories)
# Columns: trajectory, t, area_t0, area_t,
#           distance_mean, speed_mean, is_closing
```

### Speed Units

Speed is computed as `distance / frame_index` (px/frame, NOT px/hour). The `t` values in trajectory results are frame indices. To convert:
```
speed_um_per_hour = speed_px_per_frame / hours_per_frame * um_per_pixel
# For Incucyte 10x at ~2h intervals: speed_um_per_hour = speed * 1.24 / 2.0
```

## Quality Control

Three hierarchical levels:

| Level | Function | Applied to |
|-------|----------|------------|
| 1. Geometric validation | `WoundDetector._validate_wound_geometry()` | Every frame |
| 2. Distributional analysis | `verify_wound_by_distribution()` | t=0 only |
| 3. Manual curation | Annotation Excel workflow | Optional |

```python
# Filter trajectories by t=0 QC
from library.filtering.cross_sectional import filter_trajectories_by_t0_wound_distribution

filtered, keep_table = filter_trajectories_by_t0_wound_distribution(trajectories)
```

## Config Paths

All I/O paths are centralized in `config/config.py`:

```python
from config.config import config

config["data_in_organized"]    # Organized images (pipeline input)
config["model_output_dir"]     # Model-specific output directory
config["trajectories_pickle"]  # trajectories.pickle path
config["final_legacy_table"]   # experiments.xlsx path
config["aligned_legacy_table"] # aligned_legacy_table.xlsx path
config["publication_dir"]      # paper_publication/ directory
```

## Troubleshooting

### Segmentation Failures

1. Check debug PNGs in `output_root/{identifier}/debug_t*.png`
2. Look at QC flags: `result.qc["valid"]`, `result.qc["reason"]`
3. Common failure reasons:
   - `width_0.45` -> wound doesn't span enough columns (debris, partial wound)
   - `thickness_cv_0.72` -> wound thickness too variable (bubble, artifact)
   - `y_pos_0.12` -> wound not centered (mis-scratched well)

### Kalman vs Hard Constraint Comparison

```python
# Run both and compare (as in main.py __main__ block)
cfg_kalman = WoundDetectorConfig(use_kalman=True)
cfg_hard = WoundDetectorConfig(use_kalman=False)

# Process with separate output directories
# Compare wound areas: Kalman typically yields ~1-2% larger areas
# (hard constraint over-shrinks due to permanent artifact lock-in)
```

### Cached Results

Per-sample results are cached at `output_root/{identifier}/experiment.pkl`. To reprocess:
- Delete the specific `experiment.pkl` file, or
- Delete the entire `{identifier}/` directory

Set `process_missing=True` to process only uncached samples.

## Mandatory Constraints

1. The monotonic constraint is a biological invariant -- wound area can only decrease
2. Candesartan must be excluded from all publication analyses (`filter_candesartan()`)
3. `verify_wound_by_distribution()` in `woundtrack/qc.py` is the canonical QC -- do not duplicate
4. All measurements are in pixel units unless explicitly calibrated (1.24 um/px for Incucyte 10x)
5. Kalman filter is the default (`use_kalman=True`); set `use_kalman=False` for legacy reproducibility