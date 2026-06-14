# Ablation Study Verification

Quick launcher for the Kalman filter ablation study verification app.

## Quick Start

```bash
python run_ablation_verification.py
```

Then visit: **http://localhost:5000**

## What This Does

- Loads trajectories from: `Z:\DATA\elahi\giocrm\WoundHealingImgs\results_06122026\ablation\kalman_hard\`
- Extracts t=0 (initial) images from all trajectories
- Launches an interactive web app for reviewing segmentation quality

## Commands

### Default (port 5000)
```bash
python run_ablation_verification.py
```

### Custom port (if 5000 is busy)
```bash
python run_ablation_verification.py --port 8080
```

### Debug mode (with auto-reload)
```bash
python run_ablation_verification.py --debug
```

### Use different ablation results
```bash
python run_ablation_verification.py --dir Z:\path\to\other\ablation\results
```

## Data Being Verified

**Source:** `Z:\DATA\elahi\giocrm\WoundHealingImgs\results_06122026\ablation\kalman_hard\segmentation\trajectories.pickle` (1.2 GB)

**Contains:** 
- Segmentation results for ~150 images (all Alk5i condition, ablation study)
- Each with raw image, predicted mask, wound edges, QC status

## Features

✅ Review segmentation quality at t=0  
✅ Mark images correct/incorrect  
✅ Draw manual polygons to compute metrics  
✅ Edge correction mode  
✅ Export results to Excel  
✅ Auto-save progress  

## Exit

Press **Ctrl+C** in terminal to stop the server.

## If You Get Errors

| Error | Fix |
|-------|-----|
| Flask not installed | `pip install flask` |
| Port already in use | Use `--port 8080` |
| Can't find directory | Check Z: drive is accessible |

## Full Documentation

See **VERIFICATION_APP.md** for comprehensive guide including:
- How to use each mode (Review, Annotate, Edge Correct)
- What metrics mean (Dice, IoU, precision, recall)
- How to export results
- Keyboard shortcuts
- Troubleshooting
