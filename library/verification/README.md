# Wound Verification GUI

Web-based manual verification tool for reviewing Gemini wound segmentation
results at t=0.

## Purpose

Replaces the previous Excel-based manual annotation workflow
(`run_manual_annotation_export.py`) with an interactive browser interface
that supports:

- Visual review of the 6-panel diagnostic image (original, variance map,
  Y-profile, raw edges, smoothed edges, final mask)
- Binary verdict per trajectory: **correct** or **incorrect**
- Optional ground-truth polygon drawing on the raw image for quantitative
  comparison against the model mask
- Automatic computation of pixel-level metrics (Dice, IoU, precision,
  recall, F1, Hausdorff distance)
- Aggregate statistics and QC-vs-human agreement (Cohen's kappa)
- Excel export with per-image and summary sheets

## Quick Start

```bash
conda activate stats_env
python scripts/run_verification_gui.py
```

The browser opens automatically at `http://localhost:5000`.

## Workflow

1. **Review**: Click a row in the left table to load the t=0 diagnostic
   panels and raw image.
2. **Verdict**: Click **Correct** (Y) or **Incorrect** (N) to mark the
   detection quality.  Keyboard shortcuts: `y` / `n`.
3. **Polygon** (optional): Click on the raw image to draw a polygon
   around the true wound area.  Double-click or click near the start
   vertex to close.  Click **Compute Metrics** to see Dice, IoU, etc.
4. **Save**: Click **Save & Next** (or `Ctrl+Enter`) to persist and
   advance.
5. **Export**: Click **Export Excel** to download the results workbook.

### Keyboard Shortcuts

| Key              | Action                  |
|------------------|-------------------------|
| `y`              | Mark as correct         |
| `n`              | Mark as incorrect       |
| `Arrow Right`    | Next image              |
| `Arrow Left`     | Previous image          |
| `Ctrl+Enter`     | Save & next             |
| `Ctrl+S`         | Save current            |
| `Ctrl+Z`         | Undo last vertex        |

### Bulk Actions

- **Approve QC-valid**: Sets all un-annotated images that passed
  automatic QC to "correct".
- **Reject QC-invalid**: Sets all un-annotated images that failed
  automatic QC to "incorrect".
- These only affect images without an existing verdict.

## Architecture

```
library/verification/
├── __init__.py          # Package docstring
├── app.py               # Flask application factory and REST API routes
├── data_loader.py       # Load trajectories.pickle, extract t=0 records
├── metrics.py           # Dice, IoU, precision, recall, F1, Hausdorff
├── ground_truth.py      # Polygon vertices → binary mask (skimage)
├── export.py            # Excel export (per-image + aggregate sheets)
├── README.md            # This file
├── templates/
│   └── index.html       # Single-page app layout
└── static/
    ├── style.css        # UI styling
    └── app.js           # Canvas drawing, table, API communication
```

### Data Flow

```
trajectories.pickle
        │
        ▼
  data_loader.py ──► {key, img_raw, mask, qc, metadata} per trajectory
        │
        ▼
   Flask app.py ──► Serves images as PNG, manages session JSON
        │
        ▼
   Browser (index.html + app.js)
   ├── Table: list all trajectories with verdict/status
   ├── Debug PNG: 6-panel diagnostic (read-only)
   └── Canvas: raw image + mask overlay + polygon drawing
        │
        ▼  (Compute Metrics)
  ground_truth.py ──► polygon vertices → binary mask
        │
        ▼
    metrics.py ──► {dice, iou, precision, recall, f1, hausdorff_95}
        │
        ▼  (Export)
    export.py ──► verification_results_YYYYMMDD_HHMMSS.xlsx
```

## Metrics Reference

### Per-Image (model mask vs. manual polygon)

| Metric         | Formula                              | Range   |
|----------------|--------------------------------------|---------|
| Dice           | 2·TP / (2·TP + FP + FN)             | [0, 1]  |
| IoU (Jaccard)  | TP / (TP + FP + FN)                  | [0, 1]  |
| Precision      | TP / (TP + FP)                       | [0, 1]  |
| Recall         | TP / (TP + FN)                       | [0, 1]  |
| F1             | 2 · P · R / (P + R)                  | [0, 1]  |
| Pixel Accuracy | (TP + TN) / total                    | [0, 1]  |
| Hausdorff 95   | 95th percentile boundary distance    | pixels  |

### Aggregate (across all annotated images)

- Counts: total, annotated, correct, incorrect, polygon-drawn
- Mean ± std of each per-image metric
- QC agreement rate (fraction where auto-QC matches human verdict)
- Cohen's kappa (chance-corrected inter-rater agreement)

## Session Persistence

Annotation state is saved to `verification_session.json` in the output
directory after every save action.  The session file stores:

- Per-image: verdict (bool), polygon vertices, notes, computed metrics
- Timestamp of last modification

You can safely close the browser and resume later; all progress is
preserved.

## Excel Export Format

The exported workbook contains two sheets:

**Sheet 1: Per-Image Annotations**

| Column           | Description                              |
|------------------|------------------------------------------|
| trajectory_key   | Unique sample identifier                 |
| original_filename| Source image filename                    |
| exposure         | Experimental condition                   |
| experiment       | Experiment ID                            |
| qc_auto_valid    | Automatic QC verdict (bool)              |
| correct          | Human verdict (bool)                     |
| polygon_drawn    | Whether a ground-truth polygon was drawn |
| dice             | Dice coefficient (if polygon drawn)      |
| iou              | Intersection over Union                  |
| precision        | Pixel precision                          |
| recall           | Pixel recall                             |
| f1               | F1 score                                 |
| accuracy         | Pixel accuracy                           |
| hausdorff_95     | 95th percentile Hausdorff distance       |
| notes            | Free-text reviewer notes                 |
| keep             | Alias for `correct` (backward compat)    |

**Sheet 2: Aggregate Summary**

Single metric-value table with overall statistics, mean/std of all
metrics, and QC-vs-human agreement analysis.

## Dependencies

All should be available in the project conda environment:

- `flask` — web server
- `numpy`, `scipy` — metric computation
- `scikit-image` — polygon rasterisation
- `pandas`, `openpyxl` — Excel export
- `Pillow` — image encoding
