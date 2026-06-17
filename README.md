# WoundDetectionBounds

Annotation-free, open-source pipeline for quantifying wound closure in scratch-wound
healing assays from brightfield Incucyte images.

## Overview

WoundDetectionBounds segments wound boundaries frame-by-frame using a variance-based
detector, then enforces the biological monotonicity constraint (wound can only close)
via a per-column Kalman filter. The result is publication-ready wound area trajectories,
QC-validated per frame, with pairwise statistical analysis across conditions.

**Key properties:**
- No annotation or training data required
- Minimal parameter tuning — hyperparameters are fixed, not learned per dataset
- Temporal constraint integrated into segmentation (not post-hoc smoothing)
- Freely available to the research community

---

## Installation

### Prerequisites

- [Anaconda](https://www.anaconda.com/download) or Miniconda
- Python 3.11

### Setup

```bash
# 1. Create and activate environment
conda create -n wound-detection python=3.11
conda activate wound-detection

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify
python -c "from library.pipeline import Pipeline; print('Installation OK')"
```

---

## Quick Start

### 1. Prepare your input Excel file

Each row is one image. The minimum required columns are:

| Column (default name) | Description |
|-----------------------|-------------|
| `image_path`          | Absolute path to the `.tif` image |
| `time_min`            | Timepoint in minutes |
| `sample_condition`    | Treatment condition (e.g., `DMSO`, `Alk5i`, `Media`) |
| `experiment`          | Replicate identifier (e.g., `EXP1`, `EXP2`) |
| `sample_name`         | Well/sample identifier (e.g., `A1`, `A2`) |
| `cell_line`           | Cell line name |

See `data/README.md` for full column specification.
See `experiments.xlsx` for a real-data example showing the expected format.

### 2. Configure

```bash
cp config.example.yaml config.yaml
# Open config.yaml and set input_excel and output.base_dir
```

All other settings have sensible defaults. See `config.example.yaml` for the full
reference with inline documentation.

### 3. Run segmentation

```bash
python run_pipeline.py
```

Or programmatically:

```python
from library.pipeline import Pipeline

pipeline = Pipeline("config.yaml")
results = pipeline.run()          # segmentation + statistical analysis
# results = pipeline.run(stages=["segmentation"])  # segmentation only
```

### 4. Generate publication figures

```bash
python -m scripts.publication.generate_figures
```

### 5. Review segmentations interactively (optional)

```bash
python run_verification_app.py
# Navigate to http://localhost:5000
```

---

## Project Structure

```
WoundDetectionBounds/
├── library/                          # Core Python package
│   ├── pipeline.py                   # Pipeline orchestrator (main entry point)
│   ├── config/pipeline_config.py     # YAML configuration system
│   ├── core/                         # Shared types, segmentation runner
│   ├── wound_standard/               # Variance-based wound detector
│   ├── wound_quantification/         # Kalman filter + monotonic constraint
│   │   ├── segmenter.py              # QuantificationSegmenter
│   │   └── kalman_constraint.py      # KalmanEdgeFilter
│   ├── woundtrack/                   # QC validation and metrics
│   ├── filtering/                    # Time-series and cross-sectional analysis
│   ├── verification/                 # Flask-based interactive QC GUI
│   └── visualization/                # Matplotlib figure builders
├── scripts/
│   └── publication/                  # Reproducible figure and table generation
│       ├── generate_figures.py       # Fig 1 + Fig 2 orchestrator
│       ├── generate_tables.py        # Statistical tables
│       └── figure_panels.py          # Panel-level builders
├── grant_reporting/
│   └── stat_test.py                  # Statistical tests (used by generate_tables.py)
├── latexdoc/                         # LaTeX manuscript source
├── data/                             # Input format documentation
├── tests/                            # Unit and integration tests
├── docs/                             # Extended documentation
├── config.example.yaml               # Configuration template
├── experiments.xlsx                  # Example input (real-data template)
├── run_pipeline.py                   # Production entry point
├── run_verification_app.py           # Interactive QC GUI launcher
├── run_ablation_verification.py      # Ablation study launcher
├── ablation_study.py                 # Ablation analysis script
└── example_usage.py                  # Code examples
```

---

## Configuration Reference

Create `config.yaml` from the template:

```bash
cp config.example.yaml config.yaml
```

| Section | Key settings |
|---------|-------------|
| `input_excel` | Path to your experiments Excel file |
| `columns` | Map your column names to pipeline internals |
| `segmentation.temporal_mode` | `kalman` (default) / `hard` / `none` |
| `segmentation.n_workers` | Parallel workers for segmentation |
| `analysis.control_condition` | Baseline condition for pairwise comparisons |
| `analysis.stratify_by` | Factor(s) to stratify analysis by |
| `output.base_dir` | Root output directory |

Full documentation of every option is in `config.example.yaml`.

---

## Temporal Constraint Modes

The pipeline enforces the biological invariant that wound area can only decrease
(close) over time. Three modes are available:

| Mode | Description | Recommended for |
|------|-------------|-----------------|
| `kalman` | Per-column Kalman filter + optional hard safety net | Production use |
| `hard` | Deterministic max/min clamping | Ablation / legacy comparison |
| `none` | Raw detector output, no constraint | Debugging only |

```yaml
# config.yaml
segmentation:
  temporal_mode: "kalman"       # default and recommended
  enforce_safety_net: true      # guarantees A(t) ≤ A(t−1)
```

---

## Statistical Analysis

- Pairwise comparisons: **Welch's t-test** (vs. control condition)
- Multiple comparison correction: **Bonferroni** (configurable)
- Effect sizes: **Cohen's d**
- Time-series model: **mixed-effects** (wound area ~ time × condition × cell line,
  random slopes per trajectory)

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Manuscript

The LaTeX source is in `latexdoc/`. Compile with:

```bash
cd latexdoc
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

Publication figures are regenerated with:

```bash
python -m scripts.publication.generate_figures
```

---

## Limitations

- QC thresholds (aspect ratio, edge homogeneity, width coverage) were optimised on a
  126-image Incucyte brightfield cohort. Transfer to different microscopes, cell types,
  or illumination conditions will likely require re-tuning. Start with 20–30 manually
  annotated images from your system.
- Validation was performed by a single trained observer. Inter-rater reliability (ICC,
  Cohen's κ) has not been quantified; multi-observer validation is recommended before
  applying to new biological contexts.

---

## Citation

> Citation to be added upon publication.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contact

Giorgio Ricciardiello · Icahn School of Medicine at Mount Sinai
