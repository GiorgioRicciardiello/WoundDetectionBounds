# Quick Start: Verification App

## One-Line Launch

```bash
python run_verification_app.py
```

Then open: **http://localhost:5000**

## Common Commands

### Review existing segmentation
```bash
python run_verification_app.py
```
Launches the app immediately. Assumes `trajectories.pickle` already exists.

### Segment + Review (All-in-One)
```bash
python run_verification_app.py --run-segmentation
```
Runs segmentation, then launches the app. Takes 10-30 min depending on image count.

### Use custom port (if 5000 is busy)
```bash
python run_verification_app.py --port 8080
```
Access at: http://localhost:8080

### Run with debug logging
```bash
python run_verification_app.py --debug
```
Helpful for troubleshooting. Auto-reloads on code changes.

## Typical Workflow

### Day 1: Run Segmentation
```bash
# Run the quantification segmentation pipeline
python main.py

# Or use the one-liner combo:
python run_verification_app.py --run-segmentation
```

This creates:
- `trajectories.pickle` (segmentation results)
- `experiments.xlsx` (per-frame measurements)

### Day 2+: Review & Annotate
```bash
python run_verification_app.py
```

In browser:
1. **Review mode** → Mark images as correct/incorrect
2. **Annotate mode** → Draw polygons, compute metrics
3. **Edge correct mode** → Fine-tune boundaries
4. **Export** → Download results as Excel

### Export Results
- Click "Export" button in app
- Downloads `verification_results_YYYYMMDD_HHMMSS.xlsx`
- Contains: annotations, metrics, notes

## What Each File Does

| File | Purpose |
|------|---------|
| `run_verification_app.py` | **Main script** — Launches the app |
| `VERIFICATION_APP.md` | **Full documentation** — Comprehensive guide |
| `QUICK_START_VERIFICATION.md` | **This file** — Quick reference |

## Troubleshooting

### "Flask not installed"
```bash
pip install flask
```

### "Config file not found"
```bash
cp config.example.yaml config.yaml
# Then edit config.yaml with your paths
```

### "Segmentation not found"
```bash
# Option 1: Run segmentation first
python main.py

# Option 2: Use combo command
python run_verification_app.py --run-segmentation
```

### "Port 5000 already in use"
```bash
python run_verification_app.py --port 8080
```

## Features at a Glance

✅ **Review** — View t=0 images with model predictions  
✅ **Annotate** — Mark as correct/incorrect, add notes  
✅ **Draw** — Create manual polygons to compute metrics  
✅ **Measure** — Get Dice, IoU, precision, recall, F1-score  
✅ **Correct** — Fine-tune wound edges  
✅ **Export** — Download results to Excel  
✅ **Save** — Auto-saves progress, resume anytime  

## Accessing the App

### Local Machine
```
http://localhost:5000
```

### Remote SSH (port forwarding)
```bash
# On local machine:
ssh -L 5000:localhost:5000 user@remote

# Then visit: http://localhost:5000
```

### Remote Direct (expose to network)
```bash
# On server (WARNING: no authentication!)
python run_verification_app.py

# From any machine: http://<server-ip>:5000
```

## Tips for Efficient Reviewing

1. **Batch approve/reject** — Use bulk buttons for QC-valid/invalid
2. **Focus on edge cases** — Mark all obvious ones, then detail review
3. **Use keyboard shortcuts** — Arrow keys, C/X/U for quick marking
4. **Regular exports** — Download progress every hour
5. **Split by condition** — Review one condition at a time for consistency

## Data Flow

```
experiments.xlsx  (image paths + metadata)
        ↓
   python main.py  (segmentation)
        ↓
   trajectories.pickle  (results)
        ↓
   python run_verification_app.py  (launch app)
        ↓
   http://localhost:5000  (browser)
        ↓
   verification_session.json  (auto-saved annotations)
        ↓
   [Export button]
        ↓
   verification_results_*.xlsx  (download)
```

## Configuration Checklist

Before running the app, ensure:

- [ ] Python 3.11+ installed
- [ ] `conda activate imgai_env` or virtual env activated
- [ ] `config.yaml` exists and points to valid paths
- [ ] `experiments.xlsx` has required columns: image_path, time_min, condition, experiment, sample_name
- [ ] Output directory exists and is writable
- [ ] Flask installed: `pip install flask`

## Session Management

### Resume Previous Session
```bash
python run_verification_app.py
```
Automatically loads `verification_session.json` from segmentation directory.

### Reset Session (start over)
```bash
# Delete the session file:
rm <output_dir>/segmentation/verification_session.json

# Then relaunch:
python run_verification_app.py
```

### Backup Session
```bash
# Before major changes:
cp <output_dir>/segmentation/verification_session.json \
   <output_dir>/segmentation/verification_session_backup.json
```

## Next Steps

1. Read **VERIFICATION_APP.md** for detailed documentation
2. Read **VERIFICATION_APP.md → "Metrics Explained"** to understand Dice, IoU, etc.
3. Check **run_verification_app.py --help** for all command-line options

---

**Need help?** See `VERIFICATION_APP.md` → "Troubleshooting" section.
