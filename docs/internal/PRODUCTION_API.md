# Production-Grade Wound Healing Quantification API

This document describes the new sklearn-style API for running wound healing experiments. The API is modular, extensible, and production-ready.

## Quick Start

### 1. Create a Configuration File

Copy `config.example.yaml` and customize for your experiment:

```yaml
input_excel: "/path/to/your/master_experiments.xlsx"

columns:
  image_path: "image_path"
  exposure: "exposure"
  experiment: "experiment"
  sample_name: "sample_name"
  time_min: "time_min"
  cell_line: "cell_line"

segmentation:
  n_workers: 10
  save_debug_images: false
  use_kalman: true

analysis:
  control_condition: "DMSO"
  statistical_tests: ["t_test", "mixed_effects"]

output:
  base_dir: "./results"
```

### 2. Run the Pipeline

```python
from library import Pipeline

config = Pipeline.from_yaml("your_config.yaml")
config.validate()  # ← Checks for typos and missing columns

pipeline = Pipeline(config)
results = pipeline.run()
```

### 3. Access Results

```python
# Trajectories (raw segmentation results)
trajectories = results["trajectories"]

# Measurements (wound area, QC flags, constraints)
measurements = results["measurements"]

# Analysis results
analysis = results.get("analysis", {})

# Configuration used (for reproducibility)
config_used = results["config"]
```

---

## Configuration Details

### Input Data Format

Your Excel file should have (at minimum):

| image_path | exposure | experiment | sample_name | time_min | cell_line |
|------------|----------|-----------|------------|----------|-----------|
| /path/img1.tif | DMSO | EXP1 | S001 | 0 | Line1 |
| /path/img2.tif | DMSO | EXP1 | S001 | 60 | Line1 |
| /path/img3.tif | Alk5i | EXP1 | S002 | 0 | Line2 |
| ... | ... | ... | ... | ... | ... |

**Required columns** (map in config):
- `image_path`: Absolute path to image file
- `exposure`: Condition/treatment label (user-defined, any value OK)
- `experiment`: Replicate/batch identifier (user-defined)
- `sample_name`: Unique sample ID
- `time_min`: Timepoint in minutes

**Optional columns:**
- `cell_line`: Cell type
- `concentration`: Drug concentration
- `well_id`: Well identifier
- `batch_id`: Batch identifier
- `notes`: Free-text notes

### Column Mapping

If your Excel columns are named differently, map them in the config:

```yaml
columns:
  image_path: "ImagePath"          # Your actual column name
  exposure: "Treatment"
  experiment: "Batch"
  sample_name: "SampleID"
  time_min: "TimeMinutes"
  cell_line: "CellType"
```

The `validate()` function will check these columns exist in your data.

### Segmentation Parameters

```yaml
segmentation:
  n_workers: 10                         # Parallel workers
  save_debug_images: false              # 6-panel diagnostic PNGs?
  use_kalman: true                      # Kalman filter for robustness
  kalman_Q: null                        # Process noise (null = auto)
  kalman_R_base: null                   # Obs noise (null = auto)
  process_missing: true                 # Re-segment missing samples?
```

**`use_kalman`**: When true, uses Kalman filtering to smooth edges and enforce monotonic constraint. When false, uses hard constraints only. Default is `true` (recommended).

**`process_missing`**: If false, only loads cached results. If true, re-segments samples without results.

### Analysis Parameters

```yaml
analysis:
  control_condition: "DMSO"             # Baseline for comparisons
  statistical_tests:
    - "t_test"                          # Welch's t-tests
    - "mixed_effects"                   # Mixed-effects model
  multiple_comparison_correction: "bonferroni"
  effect_size_metric: "cohens_d"
  alpha: 0.05
```

**`control_condition`**: The condition to use as baseline. Pipeline will compare all other conditions to this. Must exist in your data.

### Output Structure

```
./results/
├── config_used.yaml                  # Config used for reproducibility
├── segmentation/
│   ├── trajectories.pickle           # Raw trajectory objects
│   ├── final_legacy_table.xlsx       # Per-frame measurements
│   ├── aligned_legacy_table.xlsx     # Time-aligned version
│   ├── segmentation_log.json         # Caching metadata
│   └── debug/                        # Optional diagnostic images
├── verification/
│   ├── verification_session.json     # Manual review state
│   └── verification_results.xlsx     # QC verdict + metrics
├── analysis/
│   ├── statistics.xlsx               # Summary statistics
│   ├── pairwise_tests.csv            # t-test results
│   └── mixed_effects_model.txt       # Model summary
└── figures/
    ├── fig1_model_quality.pdf
    └── fig2_wound_dynamics.pdf
```

---

## API Reference

### PipelineConfig

Load and validate configuration:

```python
from library import PipelineConfig

# From YAML
config = PipelineConfig.from_yaml("config.yaml")

# Validate (checks columns, creates output dirs)
config.validate()

# Save for reproducibility
config.to_yaml("./results/config_used.yaml")
```

**Validation checks:**
- ✓ Input Excel file exists
- ✓ Required columns exist in data
- ✓ Column names are spelled correctly
- ✓ Output directory can be created
- ✓ Control condition exists in data
- ✓ Warns on typos/mismatches

### Pipeline

Main orchestrator:

```python
from library import Pipeline

pipeline = Pipeline(config)

# Run full pipeline (segmentation + analysis)
results = pipeline.run()

# Run only segmentation
results = pipeline.run(stages=["segmentation"])

# Load previous results
results = pipeline.load_results(stage="segmentation")
```

**Returns dict with keys:**
- `trajectories`: Dict[identifier → trajectory object]
- `measurements`: DataFrame with measurements
- `analysis`: Statistical results
- `config`: Config object used
- `metadata`: Timing, sample counts, paths

### Verification GUI (Optional)

Run manual review on t=0 images:

```python
app = pipeline.get_verification_interface()

# Launch GUI
if app:
    app.run(debug=False, port=5000)
    # Opens http://localhost:5000
```

---

## Caching & Re-runs

The pipeline caches segmentation results. On re-run:

1. **If `overwrite_existing=false`** (default):
   - Pipeline detects existing results
   - Prompts user: "Found X existing segmentations. Overwrite? (y/n)"
   - Only re-segments if user approves

2. **If `overwrite_existing=true`**:
   - Pipeline re-segments automatically (no prompt)

3. **Log file** (`segmentation_log.json`):
   - Records which samples were processed
   - Timestamp of each run
   - Enables efficient re-runs

---

## Error Handling & Validation

### Config Validation

```python
try:
    config.validate()
except FileNotFoundError as e:
    print(f"Input file missing: {e}")
except ValueError as e:
    print(f"Config error: {e}")
    print("Check column names in your config:")
    print(config.columns.to_dict())
```

### Common Errors

**"Missing required columns: ['exposure']"**
- Your Excel columns don't match the config mapping
- Check: `columns.exposure = "actual_column_name"`

**"Control condition 'DMSO' not found in data"**
- The control condition you specified doesn't exist
- Check what conditions you have: `df['exposure'].unique()`

**"Cannot create output directory"**
- Permission issue or invalid path
- Check `output.base_dir` is writable

---

## Modularity & Extensibility

The library is designed for researchers to mix-and-match components:

```python
# Load segmentation results
results = pipeline.load_results("segmentation")
trajectories = results["trajectories"]
measurements = results["measurements"]

# Use individual components
from library.woundtrack.qc import verify_wound_by_distribution

for traj_id, traj in trajectories.items():
    qc_result = verify_wound_by_distribution(
        img_raw=traj["results"][0]["img_raw"],
        mask=traj["results"][0]["mask"],
    )
    print(f"{traj_id}: QC valid = {qc_result['valid']}")

# Custom analysis
from library.filtering.timeseries import distance_calculator_timeseries

for traj_id, traj in trajectories.items():
    results_list = traj["results"]
    distances = distance_calculator_timeseries(
        results_list=results_list,
        config=None,
    )
    print(f"{traj_id}: closure distance = {distances}")
```

---

## Reproducibility

The pipeline automatically saves the config used:

```yaml
# ./results/config_used.yaml
input_excel: "/exact/path/to/master_experiments.xlsx"
columns:
  image_path: "image_path"
  exposure: "exposure"
  ...
segmentation:
  use_kalman: true
  ...
```

This allows:
1. **Exact reproduction**: Re-run with `Pipeline.from_yaml("results/config_used.yaml")`
2. **Audit trail**: Track which parameters were used for published results
3. **Version control**: Commit config files alongside results in Git

---

## Example Workflows

### Workflow 1: Full Pipeline, Single Run

```python
from library import Pipeline

config = Pipeline.from_yaml("config.yaml")
config.validate()

pipeline = Pipeline(config)
results = pipeline.run()

# Extract results
measurements = results["measurements"]
measurements.to_csv("my_measurements.csv", index=False)
```

### Workflow 2: Segmentation Only (No Analysis Yet)

```python
config = Pipeline.from_yaml("config.yaml")
config.analysis.statistical_tests = []  # Skip analysis

pipeline = Pipeline(config)
results = pipeline.run(stages=["segmentation"])
```

### Workflow 3: Manual Review with GUI

```python
pipeline = Pipeline(config)
results = pipeline.run(stages=["segmentation"])

# Launch verification GUI
app = pipeline.get_verification_interface()
app.run(port=5000)

# User manually reviews images, marks correct/incorrect
# Results saved to ./results/verification/

# Optionally re-load and check
verification = pipeline.load_results(stage="verification")
```

### Workflow 4: Reuse Segmentation for Multiple Analyses

```python
# Segment once
config = Pipeline.from_yaml("config.yaml")
config.segmentation.process_missing = True
pipeline = Pipeline(config)
results = pipeline.run(stages=["segmentation"])

# Save for later
import pickle
with open("segmentation_results.pkl", "wb") as f:
    pickle.dump(results, f)

# Later: load and re-analyze with different settings
with open("segmentation_results.pkl", "rb") as f:
    results = pickle.load(f)

measurements = results["measurements"]
trajectories = results["trajectories"]

# Custom analysis...
```

---

## Support & Troubleshooting

### Running Tests

```bash
cd WoundDetectionBounds
pytest tests/ -v
```

### Debugging

Enable verbose output:

```yaml
verbose: true
```

Then re-run. Pipeline prints progress at each stage.

### Slow Segmentation?

- Reduce `n_workers` if memory-constrained
- Set `save_debug_images: false` to skip PNG generation
- Check if `process_missing: false` to only load cached results

---

## Version & Citation

**WoundDetectionBounds** — Production quantification pipeline for wound healing assays.

Citation: [Your paper details]

License: [Your license]
