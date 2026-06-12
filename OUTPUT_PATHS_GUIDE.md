# Output Paths Configuration Guide

## Overview

Control where segmentation and analysis outputs are saved. Perfect for **multi-disk setups** (fast SSD for trajectories, slow NAS for archives).

---

## Simple Setup (Default)

All outputs go under one `base_dir`:

```yaml
output:
  base_dir: "./results"
  segmentation_subdir: "segmentation"
  analysis_subdir: "analysis"
```

**Result:**
```
./results/
├── segmentation/
│   ├── trajectories.pickle
│   └── experiments.xlsx
├── analysis/
│   ├── analysis_results.xlsx
│   └── analysis_results.json
```

---

## Multi-Disk Setup (Advanced)

Store critical outputs on **fast SSD**, archives on **slow NAS**:

```yaml
output:
  base_dir: "./results"  # Default location for logs, configs, etc.
  
  # Fast SSD for active computation
  trajectories_pickle_path: "D:/fast_ssd/trajectories.pickle"
  measurements_xlsx_path: "D:/fast_ssd/measurements.xlsx"
  
  # Slow NAS for long-term storage
  analysis_results_xlsx_path: "E:/slow_nas/analysis_results.xlsx"
  analysis_results_json_path: "E:/slow_nas/analysis_results.json"
```

**Why split?**
- **Trajectories & measurements** are large (hundreds of MB), frequently accessed during analysis → fast SSD
- **Analysis results** are small (MB), rarely modified → slow NAS for backup

---

## Examples

### Example 1: Lab with SSD + NAS

```yaml
output:
  base_dir: "/mnt/lab_storage/project_2024"
  
  # Fast SSD for segmentation
  trajectories_pickle_path: "/mnt/fast_ssd/wound_detection/trajectories.pickle"
  measurements_xlsx_path: "/mnt/fast_ssd/wound_detection/measurements.xlsx"
  
  # NAS for archives
  analysis_results_xlsx_path: "/mnt/nas_backup/analysis/results.xlsx"
  analysis_results_json_path: "/mnt/nas_backup/analysis/results.json"
```

### Example 2: Windows with Multiple Drives

```yaml
output:
  base_dir: "C:\\Users\\researcher\\Projects\\Experiment1"
  
  # Trajectory data on D: (fast local SSD)
  trajectories_pickle_path: "D:\\WoundImages\\trajectories.pickle"
  measurements_xlsx_path: "D:\\WoundImages\\measurements.xlsx"
  
  # Analysis results on network drive (E:)
  analysis_results_xlsx_path: "E:\\BackupServer\\WoundDetection\\analysis.xlsx"
  analysis_results_json_path: "E:\\BackupServer\\WoundDetection\\analysis.json"
```

### Example 3: Single Fast Disk (all critical outputs)

```yaml
output:
  base_dir: "./results"  # Unused, kept for compatibility
  
  # Everything on fast SSD for maximum performance
  trajectories_pickle_path: "D:/experiments/2024/trajectories.pickle"
  measurements_xlsx_path: "D:/experiments/2024/measurements.xlsx"
  analysis_results_xlsx_path: "D:/experiments/2024/analysis.xlsx"
  analysis_results_json_path: "D:/experiments/2024/analysis.json"
```

---

## Available Output Paths

| Config Key | What It Stores | Typical Size | Access Pattern |
|---|---|---|---|
| `trajectories_pickle_path` | Wound objects per frame, masks, Kalman state | 200-800 MB | Frequent (analysis) |
| `measurements_xlsx_path` | Per-frame wound area, metadata | 1-5 MB | Moderate (analysis, verification) |
| `analysis_results_xlsx_path` | Statistical tables, p-values, effect sizes | 0.5-2 MB | Rare (review, publication) |
| `analysis_results_json_path` | Same as above, JSON format | 0.5-2 MB | Rare (programmatic use) |

---

## Default Behavior (If Paths Not Specified)

If you omit a custom path, files go to default subdirectories:

```python
# This is what happens internally:
if config.output.trajectories_pickle_path is None:
    path = config.output.base_dir / "segmentation" / "trajectories.pickle"
else:
    path = config.output.trajectories_pickle_path
```

---

## Performance Considerations

### Fast vs. Slow Storage

| Storage Type | Good For | Avoid |
|---|---|---|
| **SSD** (fast, expensive) | Active computation, trajectory data, segmentation | Long-term archives, infrequent reads |
| **HDD/NAS** (slow, cheap) | Long-term storage, backups, analysis results | Active computation, trajectory reads |

### When to Split Paths

**Use split paths if:**
- Trajectory data > 100 MB (segmentation becomes I/O bottleneck)
- You have both fast SSD and slow NAS available
- Analysis runs frequently on stable trajectories

**Use single `base_dir` if:**
- All disks have similar speed
- Total data < 100 MB
- Simplicity is preferred over performance

---

## Verification

Check where outputs will be saved:

```bash
python -c "
from library.config.pipeline_config import PipelineConfig

config = PipelineConfig.from_yaml('config.yaml')
print('Trajectories:', config.output.get_trajectories_pickle_path())
print('Measurements:', config.output.get_measurements_xlsx_path())
print('Analysis Excel:', config.output.get_analysis_results_xlsx_path())
print('Analysis JSON:', config.output.get_analysis_results_json_path())
"
```

---

## Real-World Example: Your Current Setup

Your config already uses a custom output location:

```yaml
output:
  base_dir: "C:\\Users\\riccig01\\Documents\\vascbrain\\WoundImages\\WoundQuantification\\results_06122026"
```

**To optimize with multiple disks, you could split it:**

```yaml
output:
  base_dir: "C:\\Users\\riccig01\\Documents\\vascbrain\\WoundImages\\WoundQuantification\\results_06122026"
  
  # Fast SSD for trajectories
  trajectories_pickle_path: "D:/fast_ssd/wound_trajectories/trajectories.pickle"
  measurements_xlsx_path: "D:/fast_ssd/wound_trajectories/measurements.xlsx"
  
  # Keep analysis on Documents for easy access
  # analysis_results_xlsx_path and analysis_results_json_path use base_dir/analysis
```

---

## Troubleshooting

### "No such file or directory" error

The parent directory of your output path doesn't exist. The pipeline creates it automatically, but the parent's parent must exist.

**Fix:** Ensure the disk/folder exists:
```bash
# Windows
mkdir D:\fast_ssd\wound_trajectories

# Linux/Mac
mkdir -p /mnt/fast_ssd/wound_trajectories
```

### Outputs appear in wrong location

Check your config syntax. Paths should be strings:

```yaml
# WRONG
trajectories_pickle_path: D:/path/to/file.pickle  # Missing quotes

# RIGHT
trajectories_pickle_path: "D:/path/to/file.pickle"  # Quoted string
```

### Performance still slow

Consider:
1. Is the SSD actually fast? (check with `hdparm -t` on Linux, Disk Manager on Windows)
2. Are other processes competing for I/O?
3. Are you reading/writing over network (NAS) during segmentation?

---

## Summary

- **Default behavior:** All outputs in subdirectories under `base_dir`
- **Multi-disk optimization:** Specify custom paths for trajectories (fast) vs. analysis (storage)
- **Backward compatible:** Omit custom paths to use defaults
- **Flexible:** Any path works — adjust per your storage setup

Ready to store your outputs efficiently! 🚀
