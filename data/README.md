# Input Data Format

The pipeline accepts a single flat Excel file (`.xlsx`) where **each row is one image**.
Images belonging to the same temporal sequence (trajectory) share the same
`condition`, `experiment`, and `sample_name` values and are ordered by `time_min`.

---

## Required Columns

| Column name (default) | Type | Description |
|-----------------------|------|-------------|
| `image_path` | string | Absolute path to the `.tif` image file |
| `time_min` | int / float | Timepoint in minutes; defines temporal order within a trajectory |
| `sample_condition` | string | Treatment condition (`DMSO`, `Alk5i`, `Media`, etc.) |
| `experiment` | string | Biological replicate identifier (`EXP1`, `EXP2`, ...) |
| `sample_name` | string | Individual well or sample identifier (`A1`, `A2`, ...) |

## Optional Factor Columns

Additional columns can be added for statistical stratification or interaction analysis.
They are declared in `config.yaml` under `columns.factors`.

| Column name (example) | Type | Description |
|-----------------------|------|-------------|
| `cell_line` | string | Cell line name (`iMC ISOR544C`, `iMC MUTR544C`, ...) |
| `concentration_mm` | float | Drug concentration in mM |

---

## Trajectory Identifier

A trajectory is uniquely identified by the combination:

```
(sample_condition, experiment, sample_name)
```

All images sharing these three values form one wound-healing time series.
Do not mix images from different conditions, experiments, or samples.

---

## Column Name Mapping

If your Excel file uses different column names, map them in `config.yaml`:

```yaml
columns:
  image_path: "file_path"          # your column name → pipeline internal
  time_min: "elapsed_minutes"
  condition: "treatment"
  experiment: "batch"
  sample_name: "well_id"
  factors:
    - name: "cell_line"
      column: "cell_type"
```

---

## Example Row

| image_path | time_min | sample_condition | experiment | sample_name | cell_line |
|---|---|---|---|---|---|
| C:\data\exp1\A1_t00.tif | 0 | DMSO | EXP1 | A1 | iMC ISOR544C |
| C:\data\exp1\A1_t01.tif | 120 | DMSO | EXP1 | A1 | iMC ISOR544C |
| C:\data\exp1\A1_t02.tif | 240 | DMSO | EXP1 | A1 | iMC ISOR544C |

See `experiments.xlsx` in the project root for a complete real-data example.

---

## Notes

- Image paths must be **absolute** (the pipeline reads images directly from disk).
- Timepoints must be **monotonically increasing** within each trajectory.
- Candesartan-treated samples are automatically excluded from publication analyses
  via `filter_candesartan()` in the figure-generation scripts.
