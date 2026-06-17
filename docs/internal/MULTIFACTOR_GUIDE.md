# Multi-Factor Analysis Guide

**Status:** ✅ COMPLETE AND TESTED

## Overview

The pipeline now supports **generic, domain-agnostic** stratification and interaction analysis. Instead of hardcoding "concentration," you can:

1. Define any extra factors using the `extra_factors` dictionary in your YAML config
2. Run **stratified analyses** (separate comparisons within each stratum)
3. Run **interaction analyses** (test condition × factor combinations separately)
4. Support any number of extra factors from any domain

---

## Your Data Structure

**File:** `experiments.xlsx` (7,486 records)

**Columns:**
- `sample_condition` → Primary condition (dmso, alk5i, media, candasertan)
- `cell_line` → Cell type (iMC ISOR544C, iMC MUTR544C)
- `concentration_mm` → Drug concentration (0.0, 0.01, 0.1, 1.0 mM)
- `experiment` → Biological replicate (EXP1, EXP2)
- `time_min` → Timepoint (0, 60, 120, ...)
- `image_path` → Image file location

---

## Configuration: Three Scenarios

### Scenario 1: Simple Analysis (No Stratification/Interaction)

```yaml
columns:
  condition: "sample_condition"
  cell_line: "cell_line"
  extra_factors:
    concentration: "concentration_mm"

analysis:
  control_condition: "dmso"
  stratify_by: []
  interaction_factors: []
```

**Result:** Single pooled comparison across all cell lines and concentrations.

---

### Scenario 2: Stratified Analysis (Option B)

Run **separate comparisons within each level** of specified factors.

```yaml
columns:
  condition: "sample_condition"
  cell_line: "cell_line"
  extra_factors:
    concentration: "concentration_mm"

analysis:
  control_condition: "dmso"
  stratify_by: ["cell_line", "concentration"]
  interaction_factors: []
```

**Result:** 
- 2 cell lines × 4 concentrations = **8 strata**
- Within each stratum: compare (alk5i, media, candasertan) vs. dmso
- **Output:** 8 separate Excel sheets or JSON blocks, each with its own summary and pairwise tests

**Example output row:**
```
cell_line           | concentration | treatment_condition | t_stat | p_value | effect_size
iMC MUTR544C        | 0.1           | alk5i               | -8.3   | <0.0001 | -2.1
iMC MUTR544C        | 0.1           | media               | -3.1   | 0.003   | -0.9
iMC ISOR544C        | 0.1           | alk5i               | -6.7   | <0.0001 | -1.8
```

---

### Scenario 3: Interaction Analysis (Option C)

Test each **condition × factor combination** separately against the control at that factor level.

```yaml
columns:
  condition: "sample_condition"
  cell_line: "cell_line"
  extra_factors:
    concentration: "concentration_mm"

analysis:
  control_condition: "dmso"
  stratify_by: []
  interaction_factors: ["concentration"]
```

**Result:**
- For each concentration level (0.01, 0.1, 1.0 mM):
  - Compare (alk5i @ 0.1mM vs dmso @ 0.1mM)
  - Compare (media @ 0.1mM vs dmso @ 0.1mM)
  - etc.

**Example output:**
```
concentration | treatment_condition | t_stat | p_value | effect_size
0.01          | alk5i              | -15.2  | <0.0001 | -2.3
0.01          | media              | -5.1   | <0.0001 | -0.7
0.10          | alk5i              | -27.6  | <0.0001 | -1.6
0.10          | media              | -12.3  | <0.0001 | -1.1
1.00          | alk5i              | -18.9  | <0.0001 | -1.9
1.00          | media              | -8.7   | <0.0001 | -0.8
```

---

## How to Use: Step-by-Step

### Step 1: Create Your Config

Copy the template and customize:

```bash
cp config.example.yaml my_experiment.yaml
```

Edit `my_experiment.yaml`:

```yaml
input_excel: "experiments.xlsx"

columns:
  image_path: "image_path"
  condition: "sample_condition"       # Your primary treatment variable
  experiment: "experiment"
  sample_name: "sample_name"
  time_min: "time_min"
  cell_line: "cell_line"

  # Define any extra factors (not hardcoded!)
  extra_factors:
    concentration: "concentration_mm"  # Or any other column name
    # my_factor: "actual_column_name"   # Add more as needed

analysis:
  control_condition: "dmso"
  
  # Choose stratification strategy:
  stratify_by: ["cell_line", "concentration"]  # Option B
  
  # Or choose interaction strategy:
  # interaction_factors: ["concentration"]      # Option C
  
  effect_size_metric: "cohens_d"
  output_formats: ["excel", "json"]
```

### Step 2: Validate

```python
from library import PipelineConfig

config = PipelineConfig.from_yaml("my_experiment.yaml")
config.validate()  # Catches typos and missing columns
```

### Step 3: Run Pipeline

```python
from library import Pipeline

pipeline = Pipeline(config)
results = pipeline.run()

# Access results
measurements = results["measurements"]
analysis = results["analysis"]

summary = analysis["summary_statistics"]
pairwise = analysis["pairwise_comparisons"]
```

### Step 4: Outputs

**Excel:** `analysis_results.xlsx`
- Sheet 1: Summary statistics (grouped by stratification factors if used)
- Sheet 2: Pairwise comparisons (with factor labels if stratified/interaction)

**JSON:** `analysis_results.json`
```json
{
  "metadata": {..., "stratify_by": ["cell_line", "concentration"]},
  "summary_statistics": [...],
  "pairwise_comparisons": [
    {"cell_line": "iMC MUTR544C", "concentration": 0.1, "treatment_condition": "alk5i", ...},
    {...}
  ]
}
```

---

## For Different Labs

The beauty of `extra_factors`: **no code changes needed for different experiments.**

### Lab A: Concentration-dependent study
```yaml
extra_factors:
  concentration: "drug_conc_uM"
stratify_by: ["concentration"]
```

### Lab B: Laser power study
```yaml
extra_factors:
  laser_power: "power_mW"
stratify_by: ["laser_power"]
```

### Lab C: Multi-substrate study
```yaml
extra_factors:
  substrate_type: "material"
  temperature: "temp_celsius"
stratify_by: ["substrate_type", "temperature"]
```

**The pipeline handles all of these identically.** No hardcoded names. Pure config-driven.

---

## Technical Details

### Stratification (`stratify_by`)

- Splits data into strata based on unique combinations of factor levels
- Runs **independent** pairwise comparisons within each stratum
- Summary statistics grouped by stratum
- Multiple comparison correction applied **within each stratum separately** (or globally—configurable)

### Interaction (`interaction_factors`)

- Creates composite conditions: `condition @ factor_level`
- Runs pairwise comparisons between all condition × factor combinations
- Useful when you want to test if the effect of a condition **changes across factor levels**
- More flexible than stratification in some research questions

### When to Use Which?

| Research Question | Strategy |
|---|---|
| "Does the effect differ across cell lines?" | `stratify_by: ["cell_line"]` |
| "Does drug potency vary with concentration?" | `interaction_factors: ["concentration"]` |
| "Is the effect consistent across all conditions?" | `stratify_by: ["cell_line", "concentration"]` |
| "Compare condition effects at each concentration separately" | `interaction_factors: ["concentration"]` |

---

## Column Naming: Why It Matters

Your data has `concentration_mm`. Another lab might use `drug_dose`, `exposure_level`, etc.

**Old hardcoded approach:**
```python
# Breaks if column isn't named "concentration"
df['concentration'].groupby(...)
```

**New generic approach:**
```yaml
extra_factors:
  concentration: "concentration_mm"  # Map logical name → actual column
```

```python
# Reads from config, works with any column name
for factor_name in config.analysis.stratify_by:
    actual_col = config.columns.extra_factors[factor_name]
    df.groupby(actual_col)
```

---

## Testing

All stratification and interaction logic has been tested with your actual data structure:

✅ Stratification by multiple factors (cell_line + concentration)
✅ Interaction analysis (condition × factor combinations)
✅ Stratified pairwise comparisons with factor labels
✅ Proper handling of NaN values in factor columns
✅ Config validation catches typos and missing columns

---

## Next: Run With Your Data

1. **Decide on analysis strategy:**
   - Pure pooled: `stratify_by: []`, `interaction_factors: []`
   - Stratified (B): `stratify_by: ["cell_line", "concentration"]`
   - Interaction (C): `interaction_factors: ["concentration"]`
   - Or both (separate strata with interactions within)

2. **Create and validate config:**
   ```bash
   cp config.example.yaml my_analysis.yaml
   python -c "from library import PipelineConfig; PipelineConfig.from_yaml('my_analysis.yaml').validate()"
   ```

3. **Run pipeline:**
   ```python
   from library import Pipeline
   config = PipelineConfig.from_yaml("my_analysis.yaml")
   results = Pipeline(config).run()
   ```

4. **Check outputs in `./results_multifactor/analysis/`:**
   - `analysis_results.xlsx` — formatted tables
   - `analysis_results.json` — structured data for downstream analysis

---

**Created:** 2026-06-12  
**Status:** Production Ready  
**Tested:** ✅ All features validated
