# Configuration Guide

## Quick Start

1. **Copy the template:**
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml`** with your experiment details:
   ```yaml
   input_excel: "path/to/your/experiments.xlsx"
   columns:
     condition: "your_treatment_column"
     experiment: "your_replicate_column"
     # ... rest of your columns
   ```

3. **Validate:**
   ```bash
   python -c "from library.config.pipeline_config import PipelineConfig; PipelineConfig.from_yaml('config.yaml').validate()"
   ```

4. **Run:**
   ```bash
   python -c "
   from library.config.pipeline_config import PipelineConfig
   from library.pipeline import Pipeline
   
   config = PipelineConfig.from_yaml('config.yaml')
   pipeline = Pipeline(config)
   results = pipeline.run()
   "
   ```

---

## Files

| File | Purpose |
|---|---|
| **`config.yaml`** | ← Your experiment config (EDIT THIS) |
| `config.example.yaml` | Template with all options (copy to make new configs) |
| `config/config.py` | ⚠️ Legacy hardcoded paths (backward compat only, don't use) |

---

## Config Structure

```yaml
# Where to read your data
input_excel: "path/to/experiments.xlsx"

columns:
  # Infrastructure (always required)
  image_path: "image_path"
  time_min: "time_min"
  
  # Trajectory identifiers (always required, FIXED)
  condition: "your_treatment_column"
  experiment: "your_replicate_column"
  sample_name: "your_sample_column"
  
  # Analysis factors (optional, CONFIGURABLE)
  factors:
    - name: "cell_line"
      column: "cell_line"
    - name: "concentration"
      column: "concentration_mm"
    # Add more factors as needed

# Segmentation settings
segmentation:
  n_workers: 10
  use_kalman: true
  process_missing: true

# Statistical analysis settings
analysis:
  control_condition: "dmso"
  stratify_by: ["cell_line", "concentration"]
  interaction_factors: ["concentration"]
  # ... more options

# Where to save results
output:
  base_dir: "./results"
```

---

## For Different Domains

**Cell Biology:**
```yaml
factors:
  - name: "cell_line"
    column: "cell_type"
  - name: "dose"
    column: "drug_dose_uM"
```

**Optics:**
```yaml
factors:
  - name: "wavelength"
    column: "wavelength_nm"
  - name: "laser_power"
    column: "power_mW"
```

**Materials Science:**
```yaml
factors:
  - name: "thickness"
    column: "thickness_nm"
  - name: "porosity"
    column: "porosity_percent"
```

**Same code works for all.** Just change the column names.

---

## Common Issues

### "Missing required columns: ..."
You referenced columns in config.yaml that don't exist in your Excel file.
- Check column names in Excel (case-sensitive)
- Update `columns:` section in config.yaml to match

### "Invalid factors in 'stratify_by': ..."
You used a factor name that wasn't defined in `columns.factors`.
- Add the factor to the `factors:` list
- Or remove it from `stratify_by`/`interaction_factors`

### "Control condition 'dmso' not found in data"
The value you set as `control_condition` doesn't exist in your data.
- Check the actual values in your condition column
- Update `analysis.control_condition` to match

---

## Full Documentation

For detailed explanations, see:
- `ARCHITECTURE_REFACTOR.md` — Design rationale
- `REFACTOR_VISUAL_SUMMARY.md` — Before/after comparison
- `config.example.yaml` — Inline comments for each option

---

## Help

```bash
# Validate your config
python -c "
from library.config.pipeline_config import PipelineConfig
PipelineConfig.from_yaml('config.yaml').validate('experiments.xlsx')
"

# Load and inspect config
python -c "
from library.config.pipeline_config import PipelineConfig
config = PipelineConfig.from_yaml('config.yaml')
print(config)
"
```
