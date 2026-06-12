# DEPRECATED: Image Organization Tools

**Status**: ⚠️ DEPRECATED — Do not use in production code

**Reason**: The new YAML-based pipeline (`library/pipeline.py`) works directly with flat Excel files containing absolute image paths. No directory organization is needed.

## Historical Context

These tools were used in the original workflow:
```
Raw Incucyte images → organize_experiments() → directory structure → pipeline processes
```

The new workflow simplifies this:
```
experiments.xlsx (flat, absolute paths) → Pipeline (processes directly)
```

## Files in This Archive

- `organize_experiments.py` — Main organization function (legacy)
- `experiment_organizer.py` — Supporting utilities
- `file_renamer.py` — Image file handling
- `metadata_handler.py` — Metadata extraction
- `__init__.py` — Module imports

## Why Deprecated

1. **No longer needed** — Pipeline accepts flat Excel with absolute paths
2. **Extra I/O** — Creating intermediate directory structure added unnecessary disk operations
3. **Complexity** — Required maintaining two different input formats
4. **Reproducibility** — Direct paths are more transparent and auditable

## If You Need Directory Structure

If your workflow still requires organized directories (e.g., for non-pipeline processing):

```python
# DON'T import from production code
# Use this archived copy instead
from grant_reporting.organize_experiments import organize_experiments

organize_experiments(
    source_base_dir="/path/to/raw/images",
    output_base_dir="/path/to/organized"
)
```

## Migration Guide

If you're updating old code that called `organize_experiments()`:

**Old approach:**
```python
from library.experiment_handler.organize_experiments import organize_experiments

organize_experiments(source_base_dir, output_base_dir)
# Then: run_quantification_pipeline(image_folder=output_base_dir, ...)
```

**New approach:**
```python
from library.pipeline import Pipeline

pipeline = Pipeline("config.yaml")
results = pipeline.run(stages=["segmentation"])
```

## Archive Date

Moved to deprecated: 2026-06-12

## Future

If these tools are needed again for any reason:
1. Keep this archive
2. Never import into production code
3. Create a separate "legacy tools" module if needed
4. Document any usage thoroughly
