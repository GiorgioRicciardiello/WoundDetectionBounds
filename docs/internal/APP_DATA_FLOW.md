# Verification App - Data Flow & Visualization

## Input Files (What the App Reads)

### Primary Data Source: `trajectories.pickle`
**Location:** `<output_dir>/segmentation/trajectories.pickle`

**What's Inside:**
```python
{
    "trajectory_key_1": {  # e.g., "DMSO_b1_s1-EXP1-DMSO"
        "results": [
            {  # t=0 (timepoint 0 - INITIAL WOUND)
                "img_raw": np.ndarray,        # Raw grayscale image (H × W)
                "mask": np.ndarray,           # Binary wound mask (H × W, values 0/1)
                "upper_edge": np.ndarray,     # Upper wound boundary (W,)
                "lower_edge": np.ndarray,     # Lower wound boundary (W,)
                "qc": {
                    "valid": True/False,      # QC pass/fail
                    ...other metrics...
                },
                "file_name": "path/to/image.tif"
            },
            {  # t=1, t=2, ... (LATER TIMEPOINTS - NOT SHOWN IN APP)
                ...
            }
        ],
        "exposure": "DMSO",           # Treatment condition
        "experiment": "EXP1",         # Experiment batch
        "sample_name": "b1_s1"        # Sample identifier
    },
    "trajectory_key_2": { ... },
    ...
}
```

**Data Extracted for t=0 Only:**
The app extracts ONLY the t=0 (first timepoint) record from each trajectory:
- Raw image
- Model's predicted mask
- Wound edges (upper/lower boundaries)
- QC status
- Metadata (treatment, batch, sample ID)

### Secondary Data: Debug PNGs (Optional)
**Location:** `<output_dir>/segmentation/` or gemini results directory

**What's Inside:**
- 6-panel debug visualization showing detection steps
- Optional, can be missing without breaking app

### Session Persistence: `verification_session.json`
**Location:** `<output_dir>/segmentation/verification_session.json`

**What's Inside:**
```json
{
    "annotations": {
        "trajectory_key_1": {
            "correct": true,
            "polygons": [[[x1,y1], [x2,y2], ...]],
            "notes": "Clean segmentation",
            "metrics": {
                "dice": 0.95,
                "iou": 0.91,
                "precision": 0.96,
                "recall": 0.94,
                "f1": 0.95
            }
        },
        ...
    },
    "last_modified": "2026-06-13T14:30:00"
}
```

---

## Visualization in the Web App

### What the User Sees

**Layout: 3-Panel Interface**

```
┌─────────────────────────────────────────────────────────────┐
│                    VERIFICATION APP UI                      │
├─────────────────────┬──────────────────────┬────────────────┤
│                     │                      │                │
│  IMAGE LIST         │   IMAGE VIEWER       │  ANNOTATION    │
│  (Left Panel)       │   (Center Panel)     │  PANEL         │
│                     │                      │  (Right Panel) │
│  □ DMSO_b1_s1       │  ┌─────────────────┐ │                │
│    ✓ Correct        │  │                 │ │  Verdict:      │
│                     │  │  RAW IMAGE      │ │  ○ Correct     │
│  □ DMSO_b1_s2       │  │  + MASK OVERLAY │ │  ○ Incorrect   │
│    ✗ Incorrect      │  │                 │ │  ○ Unsure      │
│                     │  │  (clickable,    │ │                │
│  □ Alk5i_b2_s3      │  │   drawable)     │ │  Polygons:     │
│    ? Unsure         │  │                 │ │  [draw mode]   │
│                     │  │  Zoom: +  -     │ │                │
│  □ Alk5i_b2_s4      │  │  Pan: click+drag│ │  Metrics:      │
│                     │  └─────────────────┘ │  Dice: 0.95    │
│  ...                │                      │  IoU: 0.91     │
│                     │  Mode: [Review ▼]   │  Precision:    │
│  Filters:           │                      │  Recall:       │
│  [Condition: ▼]     │  [Export]           │  F1: 0.95      │
│  [Experiment: ▼]    │                      │                │
│  [Status: ▼]        │                      │  Notes:        │
│                     │                      │  [text field]  │
└─────────────────────┴──────────────────────┴────────────────┘
```

### Image Viewer (Center) - What's Shown

**Raw Image + Mask Overlay:**
```
Original grayscale image (from img_raw)
with model's predicted wound mask overlaid
(typically shown as semi-transparent colored region)

╔═══════════════════════════════════════╗
║ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ║  ← Background (not wound)
║ ░░░░░░░███████████████░░░░░░░░░░░░░ ║
║ ░░░░███████████████████████░░░░░░░░ ║  ← Predicted wound area
║ ░░███████████████████████████░░░░░░ ║     (shown as colored/transparent)
║ ░░███████████████████████████░░░░░░ ║
║ ░░░░███████████████████████░░░░░░░░ ║
║ ░░░░░░░███████████████░░░░░░░░░░░░░ ║
║ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ║
╚═══════════════════════════════════════╝

User can zoom/pan to inspect details
```

### Three Modes of Visualization

#### Mode 1: Review
- View raw image + model mask
- Quickly mark correct/incorrect
- See QC status indicator
- No drawing

#### Mode 2: Annotate
- Draw manual polygons on image
- Right-click to start, left-click to add vertices, double-click to close
- Real-time metric computation against model mask
- Polygons show: Dice, IoU, precision, recall, F1-score

#### Mode 3: Edge Correction
- Show model's wound edges as lines
- Upper and lower boundaries visible
- Click to adjust edge points
- Recompute metrics from corrected edges

### Data Tables (Left Panel)

**Columns Shown:**

| Column | Source | Values |
|--------|--------|--------|
| trajectory_key | From pickle | "DMSO_b1_s1" |
| condition | From pickle | "DMSO", "Alk5i", "Media" |
| experiment | From pickle | "EXP1", "EXP2" |
| sample_name | From pickle | "b1_s1", "b2_s2" |
| QC status | From pickle `qc.valid` | ✓ pass, ✗ fail |
| Annotation | From session.json | ✓ correct, ✗ incorrect, ? unsure |
| Dice | From session.json `metrics.dice` | 0.0-1.0 (if annotated) |

---

## Complete Data Flow

```
segmentation/trajectories.pickle
    │
    ├─ Python (server-side)
    │  └─ load_master_trajectories()
    │     └─ extract_t0_records()
    │
    ├─ Filter & Index (by trajectory_key)
    │
    └─ Server Ready
       │
       ├─ GET /api/records
       │  → JSON list of all t=0 metadata
       │
       ├─ GET /api/image/<key>
       │  → PNG bytes of raw grayscale image
       │
       ├─ GET /api/mask/<key>
       │  → PNG bytes of predicted mask
       │
       ├─ GET /api/edges/<key>
       │  → JSON {upper: [array], lower: [array]}
       │
       └─ GET /api/session
          → JSON with all user annotations
          
              ↓ (Browser loads)
          
       ┌─────────────────────────────────┐
       │  Browser (HTML/CSS/JavaScript)  │
       │  ────────────────────────────── │
       │                                 │
       │  1. Fetch /api/records          │
       │  2. Display image list          │
       │  3. User clicks record          │
       │  4. Fetch /api/image/<key>      │
       │  5. Fetch /api/mask/<key>       │
       │  6. Display overlaid in canvas  │
       │  7. User annotates             │
       │  8. POST /api/annotate          │
       │     ↓ (server saves to disk)    │
       │     verification_session.json   │
       │                                 │
       └─────────────────────────────────┘
```

---

## What Gets Visualized - Summary

### Visual Elements

1. **Raw Image (Grayscale)**
   - Source: `trajectories.pickle[key]['results'][0]['img_raw']`
   - What: Original brightfield microscopy image
   - Size: Typically 1280×960 pixels (Incucyte 10× objective)
   - Color depth: uint8 (0-255 grayscale)

2. **Predicted Mask (Overlay)**
   - Source: `trajectories.pickle[key]['results'][0]['mask']`
   - What: Binary wound region (0 = background, 1 = wound)
   - Typically shown as semi-transparent colored region on raw image
   - Used to compute comparison metrics

3. **Wound Edges (Edge Correction Mode)**
   - Source: `upper_edge` and `lower_edge` from pickle
   - What: Detected upper and lower wound boundaries
   - Shown as lines across the image
   - Allows user to correct if misdetected

4. **Debug PNG (Optional)**
   - Source: 6-panel debug visualization from pipeline
   - What: Step-by-step segmentation process visualization
   - Shows: Raw → Preprocessing → Edge detection → etc.

5. **User Annotations (Drawing)**
   - Polygons drawn by user on canvas
   - Overlaid on image for visual comparison
   - Real-time Dice/IoU displayed

6. **Metrics Display**
   - Dice coefficient
   - IoU (Intersection over Union)
   - Precision
   - Recall
   - F1-score

---

## Summary Table

| Aspect | Details |
|--------|---------|
| **Primary Input** | `trajectories.pickle` (segmentation results) |
| **Timepoint Shown** | t=0 only (initial wound, first frame) |
| **Data Extracted** | img_raw, mask, edges, qc, metadata |
| **Session Storage** | `verification_session.json` (auto-saved) |
| **Images Displayed** | Raw grayscale + mask overlay |
| **Visualizations** | Review mode, Annotate mode, Edge correction |
| **Metrics** | Dice, IoU, precision, recall, F1 |
| **Export Output** | Excel file with annotations + metrics |
| **File Sizes** | trajectories.pickle: 100MB-2GB (depends on # images) |
| **Number of Records** | One per trajectory (sample × condition × experiment) |

---

## Example: What You Actually See

### For one image from DMSO_b1_s1 experiment, EXP1 batch:

**Raw Image:**
- 1280×960 pixel brightfield microscopy image
- Grayscale values 0-255
- Shows cell monolayer with scratch wound

**Model Mask Overlay:**
- Binary wound region (colored semi-transparent)
- Highlights the segmented wound area
- Green/red depending on QC status

**User Drawing Polygons (if in annotate mode):**
- User clicks to outline what they think the wound is
- Real-time Dice comparison shown
- Can adjust if model prediction is off

**Export Result:**
- Row in Excel with: image ID, verdict (correct/incorrect), Dice score, notes
- Used for quality assessment and model improvement
