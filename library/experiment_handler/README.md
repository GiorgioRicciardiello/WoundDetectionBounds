# Experiment Handler Library

A Python library for organizing and standardizing experimental image files from ALK5i and Candesartan drug studies on CADASIL patient-derived induced mural cells (iMCs).

## Purpose

This library solves critical data organization challenges in multi-experiment wound healing studies:

- **File Renaming**: Standardizes filenames across experiments with consistent naming conventions
- **Time-Shift Corrections**: Applies +2 hour corrections to mislabeled Crop2 timepoints
- **Experiment Tagging**: Adds experiment identifiers (EXP1, EXP2) to track independent sessions
- **Folder Merging**: Combines Crop1 (0h) and Crop2 (2h+) files into unified experiment directories

## Experimental Context

### Study Design

**Objective**: Evaluate whether ALK5i and Candesartan drugs can prevent increased migration in CADASIL mutant induced mural cells.

**Cell Lines**:
- Mutant: R544C mutation
- Isogenic control

**Drugs Tested**:
- ALK5i
- Candesartan

**Experiments**: 2 independent sessions per drug (EXP1, EXP2)

### Data Organization Challenge

#### Experiment 1 Issue

Due to imaging acquisition problems, Experiment 1 data was split into two folders:

**Crop1**: Contains 0h timepoint images (correct labels)
- ALK5i prefix: `ALK2_` 
- Candesartan prefix: `C2_`

**Crop2**: Contains 2h+ timepoint images (mislabeled - need +2h correction)
- ALK5i prefix: `alk_`
- Candesartan prefix: `can_`
- **Problem**: `00d00h00m` should be `00d02h00m`, `00d01h00m` should be `00d03h00m`, etc.

#### Experiment 2

Single folder with correct timepoints:
- ALK5i prefix: `ALK_`
- Candesartan prefix: `CAN_`

## Installation
No installation required - the library is part of the WoundDetectionCells project.

## Usage

### Quick Start

Run the main organization script directly from your IDE:

```python
# File: scripts/organize_experiments.py
python src/organize_experiments.py
```

The script will:
1. Process all ALK5i experiments (EXP1 and EXP2)
2. Process all Candesartan experiments (EXP1 and EXP2)
3. Apply time-shift corrections to Crop2 files
4. Add experiment tags to all filenames
5. Generate processing reports

### Configuration

Edit the paths in `src/organize_experiments.py`:

```python
# Source directory (contains alk5i/ and candesartan/ folders)
source_base_dir = Path(r"C:\...\WoundHealing")

# Output directory for organized files
output_base_dir = Path(r"C:\...\processed_experiments")
```

### Programmatic Usage
The paths of experiment 1 and experiment 2 needs to be defined manually. Each crop now contains both an `images` path (folder) and a `sample` path (Excel file).

```python
from pathlib import Path
from library.experiment_handler import organize_drug_experiment

# Define experiment structure with nested dictionaries
alk5i_structure = {
    'EXP1': {
        'crop1': {
            'images': Path('Experiment 1_111425\\Timepoint 0_Crop1'),
            'sample': Path('Experiment 1_111425\\alk Sample.xls')
        },
        'crop2': {
            'images': Path('Experiment 1_111425\\Timepoint after 2h_Crop2'),
            'sample': Path('Experiment 1_111425\\ALK2 Sample.xls')
        }
    },
    'EXP2': {
        'crop1': {
            'images': Path('Experiment 2_112125\\Crop1'),
            'sample': Path('Experiment 2_112125\\ALK Sample.xls')
        },
        'crop2': None  # No Crop2 for EXP2
    }
}

# Organize experiments
reports = organize_drug_experiment(
    source_base_dir=Path("C:/path/to/source"),
    output_base_dir=Path("C:/path/to/output"),
    drug_name='alk5i',
    experiment_structure=alk5i_structure
)
```

**Note**: Only the sample table from Crop1 is used for processing. Crop2 sample tables are ignored.

## Renaming Logic

### Experiment 1 - Crop1 (0h timepoint, no shift)

**ALK5i**:
```
Input:  ALK2_A1_1_00d00h00m.tif_crop
Output: ALK2_A1_1_EXP1_00d00h00m.tif_crop -> It now has the tag "_EXP1_"
```

**Candesartan**:
```
Input:  C2_A1_1_00d00h00m.tif_crop
Output: C2_A1_1_EXP1_00d00h00m.tif_crop
```

### Experiment 1 - Crop2 (2h+ timepoint, +2h shift)

**ALK5i**:
```
Input:  alk_A1_1_00d00h00m.tif_crop  (mislabeled as 0h)
Output: alk_A1_1_EXP1_00d02h00m.tif_crop  (corrected to 2h) -> from Cop2 folder

Input:  alk_A1_1_00d01h00m.tif_crop  (mislabeled as 1h)
Output: alk_A1_1_EXP1_00d03h00m.tif_crop  (corrected to 3h) -> from Cop2 folder
```

**Candesartan**:
```
Input:  can_A1_1_00d00h00m.tif_crop
Output: can_A1_1_EXP1_00d02h00m.tif_crop

Input:  can_A1_1_00d01h00m.tif_crop
Output: can_A1_1_EXP1_00d03h00m.tif_crop
```

### Experiment 2 (correct timepoints, no shift)

**ALK5i**:
```
Input:  ALK_A3_1_00d00h00m.tif_crop
Output: ALK_A3_1_EXP2_00d00h00m.tif_crop
```

**Candesartan**:
```
Input:  CAN_A3_1_00d00h00m.tif_crop
Output: CAN_A3_1_EXP2_00d00h00m.tif_crop
```

## Output Structure

After running the organization script, files will be organized as follows:

```
data/processed_experiments/
├── alk5i/
│   ├── EXP1/
│   │   ├── ALK2_A1_1_EXP1_00d00h00m.tif_crop  # From Crop1 (0h)
│   │   ├── alk_A1_1_EXP1_00d02h00m.tif_crop   # From Crop2 (shifted from 0h to 2h)
│   │   ├── alk_A1_1_EXP1_00d03h00m.tif_crop   # From Crop2 (shifted from 1h to 3h)
│   │   ├── alk_A1_1_EXP1_00d04h00m.tif_crop   # From Crop2 (shifted from 2h to 4h)
│   │   ├── EXP1_sample_table.csv              # Processed sample table
│   │   └── ...
│   └── EXP2/
│       ├── ALK_A3_1_EXP2_00d00h00m.tif_crop
│       ├── ALK_A3_1_EXP2_00d01h00m.tif_crop
│       ├── EXP2_sample_table.csv              # Processed sample table
│       └── ...
├── candesartan/
│   ├── EXP1/
│   │   ├── C2_A1_1_EXP1_00d00h00m.tif_crop    # From Crop1 (0h)
│   │   ├── can_A1_1_EXP1_00d02h00m.tif_crop   # From Crop2 (shifted from 0h to 2h)
│   │   ├── can_A1_1_EXP1_00d03h00m.tif_crop   # From Crop2 (shifted from 1h to 3h)
│   │   ├── EXP1_sample_table.csv              # Processed sample table
│   │   └── ...
│   └── EXP2/
│       ├── CAN_A3_1_EXP2_00d00h00m.tif_crop
│       ├── EXP2_sample_table.csv              # Processed sample table
│       └── ...
└── processing_reports/
    ├── alk5i_EXP1_processing_report.csv
    ├── alk5i_EXP2_processing_report.csv
    ├── alk5i_comprehensive_report.csv
    ├── candesartan_EXP1_processing_report.csv
    ├── candesartan_EXP2_processing_report.csv
    └── candesartan_comprehensive_report.csv
```

## Processing Reports

Each experiment generates a CSV report with the following information:

| Column | Description |
|--------|-------------|
| `experiment` | Experiment identifier (EXP1, EXP2) |
| `original_file` | Original filename from source |
| `new_file` | Renamed filename with experiment tag and time shift |
| `source_folder` | Source folder (Crop1, Crop2) |
| `time_shift` | Time shift applied (0h, +2h) |
| `status` | Processing status (success, error) |

**Example Report**:
```csv
experiment,original_file,new_file,source_folder,time_shift,status
EXP1,ALK2_A1_1_00d00h00m.tif_crop,ALK2_A1_1_EXP1_00d00h00m.tif_crop,Crop1,0h,success
EXP1,alk_A1_1_00d00h00m.tif_crop,alk_A1_1_EXP1_00d02h00m.tif_crop,Crop2,+2h,success
EXP1,alk_A1_1_00d01h00m.tif_crop,alk_A1_1_EXP1_00d03h00m.tif_crop,Crop2,+2h,success
```

## Sample Tables

Each experiment also generates a processed sample table (`{EXP}_sample_table.csv`) with the following columns:

| Column | Description |
|--------|-------------|
| `Sample name` | Sample identifier matching the new_file naming convention (e.g., `ALK2_A1_1`) |
| `Cell line` | Cell line used (e.g., `iMC MUTR544C`) |
| `Sample condition` | Experimental condition (e.g., `Media`, `DMSO 0.1mM`, `10 uM`) |
| `experiment` | Experiment identifier (EXP1, EXP2) |

**Example Sample Table**:
```csv
Sample name,Cell line,Sample condition,experiment
ALK2_A1_1,iMC MUTR544C,Media,EXP1
ALK2_A2_1,iMC MUTR544C,Media,EXP1
ALK2_A3_1,iMC MUTR544C,DMSO 0.1mM,EXP1
```

**Note**: Sample tables are time-invariant (all time points for the same sample have the same cell line and sample condition). Only unique samples are included in the processed table.

## Library Modules

### `file_renamer.py`

Core renaming logic:
- `parse_filename()` - Extract components from filename
- `apply_time_shift()` - Add hours to timestamp
- `add_experiment_tag()` - Insert experiment identifier
- `rename_file()` - Complete renaming pipeline
- `auto_rename_file()` - Automatic renaming based on prefix detection

### `experiment_organizer.py`

High-level organization:
- `process_crop1()` - Handle 0h timepoint files (no shift)
- `process_crop2()` - Handle 2h+ files with +2h shift
- `merge_experiments()` - Combine Crop1 and Crop2 outputs
- `process_sample_table()` - Process sample Excel files and match with comprehensive report
- `organize_drug_experiment()` - Process entire drug folder with nested structure support

### `metadata_handler.py`

Metadata management:
- `read_sample_sheet()` - Parse Excel metadata files
- `get_available_conditions()` - List valid samples
- `generate_processing_report()` - Create summary CSV
- `validate_processed_files()` - Verify output integrity

## Prefix Mapping

The library automatically detects experiment and time shift based on filename prefix:

| Prefix | Drug | Experiment | Folder | Time Shift |
|--------|------|------------|--------|------------|
| `ALK2` | ALK5i | EXP1 | Crop1 | 0h |
| `alk` | ALK5i | EXP1 | Crop2 | +2h |
| `ALK` | ALK5i | EXP2 | Single | 0h |
| `C2` | Candesartan | EXP1 | Crop1 | 0h |
| `can` | Candesartan | EXP1 | Crop2 | +2h |
| `CAN` | Candesartan | EXP2 | Single | 0h |

## Validation

After processing, verify:

1. **File Counts**: Check that all source files were processed
2. **Time Shifts**: Confirm Crop2 files have +2h applied
3. **Experiment Tags**: Ensure all files contain `_EXP1_` or `_EXP2_`
4. **No Duplicates**: Verify no filename collisions within experiments
5. **Reports**: Review CSV reports for any errors

## Troubleshooting

### Files Not Found

**Problem**: Source folders don't exist

**Solution**: Verify paths in `organize_experiments.py` match your directory structure

### Parsing Errors

**Problem**: Filename doesn't match expected pattern

**Solution**: Check that filenames follow `PREFIX_WELL_REPLICATE_DDdHHhMMm.extension` format

### Unknown Prefix

**Problem**: Prefix not recognized (e.g., not ALK2, alk, ALK, C2, can, or CAN)

**Solution**: Update `get_experiment_info()` in `file_renamer.py` to add new prefix mappings

## Integration with Wound Detection

After organizing files, use them with the wound detection pipeline:

```python
from library.wound_segmentation.reader_files import group_and_sort_images
from main import segment_wound_video

# Load organized images
organized_dir = Path("data/processed_experiments/alk5i/EXP1")
image_paths = sorted(organized_dir.glob("*.tif_crop"))

# Group by cell line and condition
groups = group_and_sort_images(image_paths)

# Process each group
for key, paths in groups.items():
    results = segment_wound_video(paths, res_dir=output_dir)
```

## Future Enhancements

Potential improvements:
- Automatic detection of Crop1/Crop2 folders
- Support for additional experiment types
- Integration with sample spreadsheet validation
- Batch processing of multiple drug studies
- GUI for non-programmers

## Contact

For questions or issues with the experiment handler library, contact the lab.

---

**Built to standardize experimental data and enable reproducible wound healing analysis.**
