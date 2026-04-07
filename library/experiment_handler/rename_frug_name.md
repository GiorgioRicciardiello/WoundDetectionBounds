# Experiment Handler Updates - Walkthrough

## Summary

Successfully updated the experiment handler library to:
1. Support the new nested dictionary structure where each crop contains both an `images` path (folder) and a [sample](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#182-290) path (Excel file)
2. Create a new [process_sample_table()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#182-290) function to match sample names with the comprehensive report
3. **Replace original prefixes (ALK2, alk, C2, can) with drug names (alk5i, candesartan) in both filenames and sample tables**

## Changes Made

### 1. Updated Function: [auto_rename_file()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/file_renamer.py#188-230) - Prefix Replacement

**File**: [file_renamer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/file_renamer.py#L188-L230)

**Key Change**: Added `drug_name` parameter to replace the original prefix with the drug name.

**Before**:
```python
auto_rename_file('ALK2_A1_1_00d00h00m.tif_crop')
# Returns: 'ALK2_A1_1_EXP1_00d00h00m.tif_crop'
```

**After**:
```python
auto_rename_file('ALK2_A1_1_00d00h00m.tif_crop', 'alk5i')
# Returns: 'alk5i_A1_1_EXP1_00d00h00m.tif_crop'

auto_rename_file('alk_A1_1_00d00h00m.tif_crop', 'alk5i')
# Returns: 'alk5i_A1_1_EXP1_00d02h00m.tif_crop' (with +2h shift)
```

**Implementation**:
- Accepts optional `drug_name` parameter
- Replaces `components['prefix']` with `drug_name` if provided
- Maintains backward compatibility (works without drug_name)

### 2. Updated Functions: [process_crop1()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#17-81) and [process_crop2()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#83-147)

**File**: [experiment_organizer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py)

**Changes**:
- Added `drug_name_for_prefix` parameter to both functions
- Pass `drug_name_for_prefix` to [auto_rename_file()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/file_renamer.py#188-230) calls
- Updated docstrings to document the new parameter

**Example**:
```python
process_crop1(crop1_path, output_dir, "alk5i_EXP1", "alk5i")
# Now files will have 'alk5i' as prefix instead of 'ALK2' or 'alk'
```

### 3. Updated Function: [process_sample_table()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#182-290)

**File**: [experiment_organizer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#L178-L282)

**Changes**:
- Added `drug_name` parameter
- Sample names now use the drug name prefix (extracted from matched filenames)
- Fallback to `drug_name` if pattern matching fails

**Result**: Sample table entries will have names like `alk5i_A1_1` instead of `ALK2_A1_1` or `alk_A1_1`

### 4. Updated Function: [organize_drug_experiment()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#292-419)

**File**: [experiment_organizer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#L285-L420)

**Changes**:
- Passes `drug_name` to [process_crop1()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#17-81) as the 4th argument
- Passes `drug_name` to [process_crop2()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#83-147) as the 4th argument
- Passes `drug_name` to [process_sample_table()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#182-290) as a keyword argument

**Example**:
```python
organize_drug_experiment(
    source_base_dir=source_dir,
    output_base_dir=output_dir,
    drug_name='alk5i',  # This will be used as the prefix
    experiment_structure=alk5i_structure
)
```

## Output Files - Updated Format

### Before (Original Prefixes)
```
ALK2_A1_1_EXP1_00d00h00m.tif_crop  # Crop1
alk_A1_1_EXP1_00d02h00m.tif_crop   # Crop2 (with +2h shift)
ALK_A3_1_EXP2_00d00h00m.tif_crop   # EXP2
```

### After (Drug Name Prefixes)
```
alk5i_A1_1_EXP1_00d00h00m.tif_crop  # Crop1
alk5i_A1_1_EXP1_00d02h00m.tif_crop  # Crop2 (with +2h shift)
alk5i_A3_1_EXP2_00d00h00m.tif_crop  # EXP2
```

### Sample Table Format (Updated)

**Before**:
| Sample name | Cell line | Sample condition | experiment |
|-------------|-----------|------------------|------------|
| ALK2_A1_1 | iMC MUTR544C | Media | EXP1 |
| alk_A2_1 | iMC MUTR544C | Media | EXP1 |

**After**:
| Sample name | Cell line | Sample condition | experiment |
|-------------|-----------|------------------|------------|
| alk5i_A1_1 | iMC MUTR544C | Media | EXP1 |
| alk5i_A2_1 | iMC MUTR544C | Media | EXP1 |

## Benefits of This Change

1. **Consistency**: All files from the same drug experiment now have the same prefix
2. **Clarity**: Drug name is immediately visible in filenames
3. **Simplicity**: No need to remember that "ALK2", "alk", and "ALK" all refer to "alk5i"
4. **Sample Table Alignment**: Sample names match the filename convention exactly

## Implementation Flow

```
organize_drug_experiment(drug_name='alk5i')
    ↓
process_crop1(..., drug_name_for_prefix='alk5i')
    ↓
auto_rename_file('ALK2_A1_1_00d00h00m.tif_crop', drug_name='alk5i')
    ↓
Result: 'alk5i_A1_1_EXP1_00d00h00m.tif_crop'
```

## Files Modified

1. [file_renamer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/file_renamer.py) - Updated [auto_rename_file()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/file_renamer.py#188-230) to accept and use `drug_name` parameter
2. [experiment_organizer.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py) - Updated [process_crop1()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#17-81), [process_crop2()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#83-147), [process_sample_table()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#182-290), and [organize_drug_experiment()](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/library/experiment_handler/experiment_organizer.py#292-419) to pass drug_name through the pipeline

## Testing

The code is ready to use with your existing [src/organize_experiments.py](file:///c:/Users/riccig01/OneDrive/Projects/MtSinai/Fanny/WoundDetectionCells/src/organize_experiments.py) script. When you run it:
- All ALK5i files will have `alk5i` prefix
- All Candesartan files will have `candesartan` prefix (note: check the exact drug_name value in your script)
- Sample tables will reflect the same naming convention
