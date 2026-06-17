# Architecture Refactor: Trajectory Identifiers vs. Analysis Factors

**Date:** 2026-06-12  
**Status:** ✅ COMPLETE AND TESTED  
**Backward Compatibility:** ✅ FULL (old configs migrate automatically)

---

## What Changed

The configuration structure now **separates concerns** between:

1. **Infrastructure columns** — read images and define temporal order
2. **Trajectory identifiers** — define which images form a sequence (FIXED)
3. **Analysis factors** — stratification/interaction variables (CONFIGURABLE)

---

## The Problem We Solved

**Previous design issue:** Configuration had mixed purposes:
- `condition` — needed for trajectory identity AND analysis grouping
- `cell_line` — optional field, but special-cased
- `extra_factors` — dict of arbitrary factors

This made it unclear what distinguished a **sequence-defining variable** from an **analysis factor**.

**Consequence:** Risk of accidentally mixing images from different conditions/experiments into one segmentation trajectory, corrupting Kalman filter state and results.

---

## New Design

```
INFRASTRUCTURE (always required, always named)
├─ image_path  → where to read the file
└─ time_min    → temporal order within a sequence

TRAJECTORY IDENTIFIERS (always required, defines sample identity)
├─ condition   → treatment variable (dmso, alk5i, media, etc.)
├─ experiment  → replicate ID (EXP1, EXP2) — independence assumption
└─ sample_name → individual well (A1, A2, etc.)

ANALYSIS FACTORS (optional, configurable, domain-specific)
├─ cell_line       → cell type
├─ concentration   → drug dose
├─ laser_power     → optical intensity
└─ substrate_type  → material (any factor you want)
```

---

## Why This Separation Matters

### Trajectory Identifiers (FIXED)

These **define which images belong together**:
```python
# During segmentation: group images into sequences
trajectories = measurements.groupby(['condition', 'experiment', 'sample_name'])
for trajectory_id, frames in trajectories:
    # Process frames[0], frames[1], ... in time order
    # Kalman filter state carries forward
    # If we mix conditions here → garbage results
```

**These CANNOT be changed without breaking the biology:**
- Mixing conditions → treatment signal contaminated
- Mixing experiments → pseudoreplication (violates independence)
- Mixing samples → temporal discontinuity (Kalman breaks)

### Analysis Factors (CONFIGURABLE)

These are used **after segmentation** to **group and compare results**:
```python
# After segmentation: compare effects across factors
for concentration in results.groupby('concentration'):
    run_statistical_test(concentration)
    # Order doesn't matter here
    # Results are already computed
```

**These ARE flexible:**
- Add a new factor? Just add to `factors:` list in YAML
- Different domain? Same code works
- No code changes needed

---

## Configuration Example

### Old Format (Still Works!)
```yaml
columns:
  image_path: "image_path"
  time_min: "time_min"
  condition: "sample_condition"
  experiment: "experiment"
  sample_name: "sample_name"
  cell_line: "cell_line"              # Named field (special-cased)
  extra_factors:
    concentration: "concentration_mm" # Dict (unclear purpose)
```

### New Format (Recommended)
```yaml
columns:
  # Infrastructure
  image_path: "image_path"
  time_min: "time_min"

  # Trajectory identifiers (fixed, always required)
  condition: "sample_condition"
  experiment: "experiment"
  sample_name: "sample_name"

  # Analysis factors (configurable, optional, list-based)
  factors:
    - name: "cell_line"
      column: "cell_line"
    - name: "concentration"
      column: "concentration_mm"
    - name: "laser_power"           # Different lab? Just change the column name
      column: "power_mW"
```

---

## For Different Research Domains

The new design makes it **obvious** how to adapt:

### Lab A: Cell Biology
```yaml
columns:
  condition: "treatment"
  experiment: "replicate"
  sample_name: "well"
  factors:
    - name: "cell_line"
      column: "cell_type"
    - name: "concentration"
      column: "dose_uM"
```

### Lab B: Optical Physics
```yaml
columns:
  condition: "substrate"
  experiment: "run"
  sample_name: "location"
  factors:
    - name: "wavelength"
      column: "wavelength_nm"
    - name: "laser_power"
      column: "power_mW"
    - name: "temperature"
      column: "temp_celsius"
```

### Lab C: Materials Science
```yaml
columns:
  condition: "coating"
  experiment: "batch"
  sample_name: "specimen"
  factors:
    - name: "thickness"
      column: "thickness_nm"
    - name: "porosity"
      column: "porosity_percent"
```

**All use the same code.**

---

## Code Changes

### Configuration (`library/config/pipeline_config.py`)

**New dataclass:**
```python
@dataclass
class AnalysisFactor:
    name: str        # Logical name (e.g., "concentration")
    column: str      # Excel column (e.g., "concentration_mm")
```

**Updated ColumnMapping:**
```python
@dataclass
class ColumnMapping:
    # Infrastructure
    image_path: str = "image_path"
    time_min: str = "time_min"

    # Trajectory identifiers (fixed)
    condition: str = "condition"
    experiment: str = "experiment"
    sample_name: str = "sample_name"

    # Analysis factors (configurable)
    factors: list[AnalysisFactor] = field(default_factory=list)
```

**New methods:**
- `trajectory_identifier_columns()` → returns [condition, experiment, sample_name]
- `analysis_factor_columns()` → returns {name: column} mapping
- `get_factor_column(factor_name)` → lookup helper

### Pipeline (`library/pipeline.py`)

**Before:**
```python
factor_cols = {}
if self.config.columns.cell_line:
    factor_cols["cell_line"] = self.config.columns.cell_line
for name, col in self.config.columns.extra_factors.items():
    factor_cols[name] = col
```

**After:**
```python
# Single line now
factor_cols = self.config.columns.analysis_factor_columns()
```

### Analysis (`library/core/analysis.py`)

No changes needed — already works with `factor_cols` dict and `stratify_by`/`interaction_factors` lists.

---

## Backward Compatibility

✅ **Old configs automatically migrate:**

```python
# Old format
extra_factors:
  concentration: "concentration_mm"
cell_line: "cell_line"

# Automatically converts to
factors:
  - name: "cell_line"
    column: "cell_line"
  - name: "concentration"
    column: "concentration_mm"
```

Migration happens in `PipelineConfig.from_yaml()` — users don't need to edit configs.

---

## Validation

Config validation now checks:

1. **Required trajectory columns exist** (condition, experiment, sample_name)
2. **Analysis factor columns exist** in the input Excel
3. **Factor references are valid** (stratify_by/interaction_factors reference defined factors)

```
Example error:
ValueError: Invalid factors in 'stratify_by': {'concentration', 'invalid_factor'}
Valid factors: {'cell_line', 'concentration', 'laser_power'}
Define missing factors in 'columns.factors'
```

---

## Impact Summary

| Aspect | Before | After |
|---|---|---|
| Trajectory concept | Implicit | Explicit (named methods) |
| Adding a factor | Multiple code edits | Config change only |
| Factor naming | Hardcoded + dict | Unified list |
| Domain flexibility | Limited | Universal |
| Backward compat | N/A | ✅ 100% |
| Code clarity | Mixed concerns | Separated concerns |

---

## Migration Guide for Users

### If you have an old config:

**No action needed.** It will automatically migrate on load.

To see the new format:
```python
from library.config.pipeline_config import PipelineConfig

config = PipelineConfig.from_yaml("old_config.yaml")
config.to_yaml("new_config.yaml")  # Saves in new format
```

### If writing a new config:

Copy `config.example.yaml` and follow the structure:
1. Define infrastructure columns (image_path, time_min)
2. Define trajectory identifiers (condition, experiment, sample_name)
3. Add analysis factors as needed in the `factors:` list

---

## Quality Checklist

- ✅ All required columns documented
- ✅ Trajectory identifiers clearly separated
- ✅ Analysis factors in unified list structure
- ✅ Backward compatibility tested (old format → new format)
- ✅ Validation catches missing/invalid factors
- ✅ Code simplified (factor_cols building is now one line)
- ✅ Domain-agnostic terminology throughout
- ✅ Docstrings explain why the separation matters

---

## Next Steps

1. Users can update their configs to new format (optional — old format works)
2. New users start with config.example.yaml template
3. Tool remains production-ready and fully backward compatible

---

**Summary:** The separation of trajectory identifiers (what defines a sequence) from analysis factors (what to compare) makes the pipeline safer, clearer, and more flexible. Same code works for any research domain.
