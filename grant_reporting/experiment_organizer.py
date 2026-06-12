"""
Experiment Organizer Module

High-level organization logic for processing experimental image files:
- Process Crop1 folders (0h timepoint, no shift)
- Process Crop2 folders (2h+ timepoint, +2h shift)
- Merge files into unified output directory
"""

import shutil
from tabulate import tabulate
from pathlib import Path
from typing import List, Dict, Optional
from .file_renamer import auto_rename_file, parse_filename
import pandas as pd
import numpy as np
import re


def process_crop1(
    input_dir: Path,
    output_dir: Path,
    drug_name: str = "unknown",
    drug_name_for_prefix: str = None,
    overwrite: bool = False
) -> List[Dict[str, str]]:
    """
    Process Crop1 folder (0h timepoint images, no time shift needed).
    
    Args:
        input_dir: Path to Crop1 folder containing original images
        output_dir: Path to output directory for renamed files
        drug_name: Name of drug for logging (e.g., 'alk5i', 'candesartan')
        drug_name_for_prefix: Drug name to use as prefix replacement (e.g., 'alk5i', 'candesartan')
    
    Returns:
        List of processing records with original and new filenames
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processing_log = []
    
    # Find all image files
    image_files = (list(input_dir.glob("*.tif_crop")) +
                   list(input_dir.glob("*.tif")) +
                   list(input_dir.glob("*.jpg")) +
                   list(input_dir.glob("*.png")))
    
    print(f"\n[{drug_name}] Processing Crop1 (0h timepoint)")
    print(f"  Input: {input_dir}")
    print(f"  Found {len(image_files)} files")
    
    for img_file in image_files:
        try:
            # Auto-rename based on prefix detection, include the EXP in the new_filename
            new_filename = auto_rename_file(img_file.name, drug_name_for_prefix)
            
            # Copy file with new name
            output_path = output_dir / new_filename
            
            # Skip if file exists and overwrite is False
            if output_path.exists() and not overwrite:
                processing_log.append({
                    'original_file': img_file.name,
                    'new_file': new_filename,
                    'source_folder': 'Crop1',
                    'time_shift': '0h',
                    'status': 'skipped (exists)'
                })
                continue
            
            shutil.copy2(img_file, output_path)
            
            # Log the processing
            processing_log.append({
                'original_file': img_file.name,
                'new_file': new_filename,
                'source_folder': 'Crop1',
                'time_shift': '0h',
                'status': 'success'
            })
            
        except Exception as e:
            processing_log.append({
                'original_file': img_file.name,
                'new_file': '',
                'source_folder': 'Crop1',
                'time_shift': '0h',
                'status': f'error: {str(e)}'
            })
            print(f"  ⚠ Error processing {img_file.name}: {e}")
    
    successful = sum(1 for log in processing_log if log['status'] == 'success')
    print(f"  ✓ Successfully processed {successful}/{len(image_files)} files")
    
    return processing_log


def process_crop2(
    input_dir: Path,
    output_dir: Path,
    drug_name: str = "unknown",
    drug_name_for_prefix: str = None,
    overwrite: bool = False
) -> List[Dict[str, str]]:
    """
    Process Crop2 folder (2h+ timepoint images, +2h time shift needed).
    
    Args:
        input_dir: Path to Crop2 folder containing original images
        output_dir: Path to output directory for renamed files
        drug_name: Name of drug for logging (e.g., 'alk5i', 'candesartan')
        drug_name_for_prefix: Drug name to use as prefix replacement (e.g., 'alk5i', 'candesartan')
    
    Returns:
        List of processing records with original and new filenames
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processing_log = []
    
    # Find all image files
    image_files = (list(input_dir.glob("*.tif_crop")) +
                   list(input_dir.glob("*.tif")) +
                   list(input_dir.glob("*.jpg")) +
                   list(input_dir.glob("*.png")))

    print(f"\n[{drug_name}] Processing Crop2 (2h+ timepoint with +2h shift)")
    print(f"  Input: {input_dir}")
    print(f"  Found {len(image_files)} files")
    
    for img_file in image_files:
        try:
            # Auto-rename (includes +2h shift for Crop2 prefixes)
            new_filename = auto_rename_file(img_file.name, drug_name_for_prefix)
            
            # Copy file with new name
            output_path = output_dir / new_filename
            
            # Skip if file exists and overwrite is False
            if output_path.exists() and not overwrite:
                processing_log.append({
                    'original_file': img_file.name,
                    'new_file': new_filename,
                    'source_folder': 'Crop2',
                    'time_shift': '+2h',
                    'status': 'skipped (exists)'
                })
                continue
            
            shutil.copy2(img_file, output_path)
            
            # Log the processing
            processing_log.append({
                'original_file': img_file.name,
                'new_file': new_filename,
                'source_folder': 'Crop2',
                'time_shift': '+2h',
                'status': 'success'
            })
            
        except Exception as e:
            processing_log.append({
                'original_file': img_file.name,
                'new_file': '',
                'source_folder': 'Crop2',
                'time_shift': '+2h',
                'status': f'error: {str(e)}'
            })
            print(f"  ⚠ Error processing {img_file.name}: {e}")
    
    successful = sum(1 for log in processing_log if log['status'] == 'success')
    print(f"  ✓ Successfully processed {successful}/{len(image_files)} files")
    
    return processing_log


def verify_processed_files(
    processing_log: List[Dict[str, str]],
    output_dir: Path,
    report_dir: Path = None,
    experiment_name: str = "unknown"
) -> Dict[str, any]:
    """
    Verify that all processed files actually exist in the output directory.
    
    Args:
        processing_log: List of processing records from process_crop1/crop2
        output_dir: Directory where files should have been copied
        report_dir: Optional directory to save verification report
        experiment_name: Name of experiment for report naming
    
    Returns:
        Dictionary with verification results:
            - total: Total files processed
            - verified: Files that exist
            - missing: Files that don't exist
            - missing_files: List of missing filenames
    """
    verified = 0
    missing = 0
    missing_files = []
    
    # Only check files with success status
    success_logs = [log for log in processing_log if log['status'] == 'success']
    
    for log in success_logs:
        file_path = output_dir / log['new_file']
        if file_path.exists():
            verified += 1
        else:
            missing += 1
            missing_files.append(log['new_file'])
    
    # Print verification summary
    print(f"\n  🔍 Verification for {experiment_name}:")
    print(f"     Total successful copies: {len(success_logs)}")
    print(f"     Verified existing: {verified}")
    if missing > 0:
        print(f"     ⚠ MISSING files: {missing}")
        for f in missing_files[:5]:  # Show first 5 missing
            print(f"        - {f}")
        if len(missing_files) > 5:
            print(f"        ... and {len(missing_files) - 5} more")
    else:
        print(f"     ✓ All files verified!")
    
    # Save verification report if report_dir provided
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"verification_{experiment_name}.txt"
        with open(report_path, 'w') as f:
            f.write(f"Verification Report: {experiment_name}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Total successful copies: {len(success_logs)}\n")
            f.write(f"Verified existing: {verified}\n")
            f.write(f"Missing files: {missing}\n\n")
            if missing_files:
                f.write("Missing files:\n")
                for mf in missing_files:
                    f.write(f"  - {mf}\n")
        print(f"     Report saved: {report_path}")
    
    return {
        'total': len(success_logs),
        'verified': verified,
        'missing': missing,
        'missing_files': missing_files
    }


def merge_experiments(
    crop1_log: List[Dict[str, str]],
    crop2_log: List[Dict[str, str]],
    output_dir: Path,
    experiment_name: str
) -> pd.DataFrame:
    """
    Merge processing logs from Crop1 and Crop2 into a single report.
    
    Args:
        crop1_log: Processing log from Crop1
        crop2_log: Processing log from Crop2
        output_dir: Directory to save the merged report
        experiment_name: Name of experiment (e.g., 'alk5i_EXP1')
    
    Returns:
        DataFrame with merged processing information
    """
    # Combine logs
    all_logs = crop1_log + crop2_log
    
    # Create DataFrame
    df = pd.DataFrame(all_logs)
    
    # Save to CSV
    report_path = output_dir / f"{experiment_name}_processing_report.csv"
    df.to_csv(report_path, index=False)
    
    print(f"\n  📊 Processing report saved: {report_path}")
    
    return df


def process_sample_table(
    sample_path: Path,
    comprehensive_report: pd.DataFrame,
    experiment_name: str,
    output_dir: Path,
    drug_name: str = None
) -> pd.DataFrame:
    """
    Process sample table and match with comprehensive report.
    The report helps to identify which sample condition and concentration are available for each experiment based
    on the expected sample experiment and availabel images.
    
    Args:
        sample_path: Path to sample Excel file
        comprehensive_report: DataFrame with comprehensive report containing new_file column
        experiment_name: Experiment identifier (e.g., 'EXP1', 'EXP2')
        output_dir: Directory to save processed sample table
        drug_name: Drug name to use as prefix in sample names (e.g., 'alk5i', 'candesartan')
    
    Returns:
        Processed sample DataFrame with experiment column and matched sample names
    """

    def normalize_sample_name(filename):
        """Extract sample name without time component and lowercase it."""
        # Remove time component (e.g., _00d00h00m) and file extension
        # Pattern: anything before the time pattern DDdHHhMMm
        match = re.match(r'(.+?)_\d{2}d\d{2}h\d{2}m', filename.lower())
        if match:
            return match.group(1)
        return filename.lower().split('.')[0]

    def extract_time(fname):
        m = re.search(r"_(\d+d\d+h\d+m)\.", fname)
        return m.group(1) if m else None

    def time_to_minutes(t):
        d, h, m = map(int, re.match(r"(\d+)d(\d+)h(\d+)m", t).groups())
        return d * 1440 + h * 60 + m


    def format_sample_table(df_sample: pd.DataFrame, drug_name: str) -> pd.DataFrame:
        """
        Standardize sample names and extract concentration information.

        Rules
        -----
        - Media samples → concentration = 0, sample name = 'media'
        - DMSO samples → extract concentration, sample name = 'dmso'
        - Drug samples → extract concentration, sample name = drug_name
        """


        df = df_sample.copy()

        col_concentration = "concentration_mm"
        sample_col = "Sample condition"

        df[col_concentration] = np.nan

        # --------------------------------------------------
        # Replace sample names with normalize version using the full drug name
        # --------------------------------------------------
        df["Sample name"] = df["Sample name"].str.replace(r"^[^_]+", drug_name, regex=True).str.lower()
        df["Sample name"] = df["Sample name"].str.lower()

        # --------------------------------------------------
        # Media
        # --------------------------------------------------
        is_media = df[sample_col].str.contains("media", case=False, na=False)
        df.loc[is_media, col_concentration] = 0.0
        df.loc[is_media, sample_col] = "media"

        # --------------------------------------------------
        # Extract concentration (ONLY where present)
        # --------------------------------------------------
        conc_pattern = r"([\d\.]+)\s*(uM|µM|mM)"
        extracted = df[sample_col].str.extract(conc_pattern, flags=re.IGNORECASE)

        has_conc = extracted[0].notna()

        # assign numeric value
        df.loc[has_conc, col_concentration] = extracted.loc[has_conc, 0].astype(float)

        # normalize units → mM
        units = extracted.loc[has_conc, 1].str.lower()
        is_um = units.isin(["um", "µm"])
        df.loc[has_conc & is_um, col_concentration] /= 1000  # µM → mM

        # --------------------------------------------------
        # DMSO
        # --------------------------------------------------
        is_dmso = df[sample_col].str.contains("dmso", case=False, na=False)
        df.loc[is_dmso, sample_col] = "dmso"

        # --------------------------------------------------
        # Drug samples
        # --------------------------------------------------
        is_drug = (
                ~is_media &
                ~is_dmso &
                df[col_concentration].notna()
        )
        df.loc[is_drug, sample_col] = drug_name.lower()
        return df


    if not sample_path or not sample_path.exists():
        print(f"  ⚠ Sample file not found: {sample_path}")
        return None
    
    try:
        # Read sample table
        df_sample = pd.read_excel(sample_path)

        # Verify required columns exist
        required_cols = ['Sample name', 'Cell line', 'Sample condition']
        if not all(col in df_sample.columns for col in required_cols):
            print(f"  ⚠ Sample table missing required columns: {required_cols}")
            return None

        # Input table with the planned analysis, not count of images files,
        df_sample = format_sample_table(df_sample=df_sample, drug_name=drug_name)

        # Comprehensive report has the count of files in a proper mapping
        # Create a mapping from normalized sample names to new_file names
        # Extract unique sample names from comprehensive report (remove time component)
        comprehensive_report['file_name_norm'] = comprehensive_report['new_file'].apply(normalize_sample_name)
        # remove the exp from the name
        comprehensive_report["file_name_norm"] = (comprehensive_report["file_name_norm"]
                                                  .str.replace(r"_exp.*$", "", regex=True))

        comprehensive_report.sort_values(by=["new_file"], inplace=True)

        comprehensive_report["time"] = comprehensive_report["new_file"].apply(extract_time)

        comprehensive_report["time_min"] = comprehensive_report["time"].apply(time_to_minutes)


        # these should be zero but currently we do not have all the images for all the samples
        # set(comprehensive_report["file_name_norm"]) ^ set(df_sample["Sample name"])

        # merge the sample (experiment configuration) with the available images for that config
        df_merge = pd.merge(left=comprehensive_report,
                 right=df_sample,
                 left_on='file_name_norm',
                 right_on='Sample name',
                 how='inner')
        df_merge.drop(columns=['file_name_norm'], inplace=True)
        # create the time format
        df_merge["time"] = df_merge["new_file"].apply(extract_time)
        df_merge["time_min"] = df_merge["time"].apply(time_to_minutes)
        df_merge = df_merge.sort_values(by=["Sample name", "time_min"])

        # Compute aggregates for reporting
        cat_col1: str = 'Cell line'
        cat_col2: str = 'Sample condition'
        cat_col3: str = 'concentration_mm'
        cat_col4: str = 'time_min'
        group_cols = [cat_col1, cat_col2, cat_col3, cat_col4]

        # aggregates the sample plan with the available data
        agg_df = df_merge.groupby(group_cols)['source_folder'].agg(['count']).reset_index()
        # assign a code to each photo grouping, this should match with the file name
        df_merge['photo_code'] = (
            df_merge
            .groupby([cat_col1, cat_col2, cat_col3], sort=False)
            .ngroup()
        )

        # Lets count how many files are available for each sample combination
        agg_merge_df = df_merge.groupby([cat_col1, cat_col2, cat_col3])['Sample name'].agg(['count']).reset_index()
        agg_merge_df.sort_values(by=['Cell line',
                                      "Sample condition",
                                      'concentration_mm'], inplace=True)
        agg_merge_df.rename(columns={'count': 'File Count'}, inplace=True)

        # now lets include how manye samples we have per each from the sample table
        agg_sample_df = df_sample.groupby([cat_col1, cat_col2, cat_col3])['Sample name'].agg(['count']).reset_index()
        agg_sample_df.rename(columns={'count': 'Sample Count'}, inplace=True)

        agg_merge_sample = pd.merge(left=agg_merge_df,
                                    right=agg_sample_df,
                                    right_on=[cat_col1, cat_col2, cat_col3],
                                    left_on=[cat_col1, cat_col2, cat_col3],
                                    how='inner')
        # the column Sample Count is the same as dividing the File Count by the number of unique time instances
        agg_merge_sample['time_instances'] = agg_df[cat_col4].nunique()


        # Save processed sample table

        df_merge.to_excel(output_dir / f"{drug_name}_{experiment_name}_sample_file.xlsx", index=False)
        agg_df.to_csv(output_dir / f"{drug_name}_{experiment_name}_agg_report_sample_table.csv", index=False)
        agg_merge_sample.to_excel(output_dir / f"{drug_name}_{experiment_name}_sample_file_counts.xlsx", index=False)
        print(f"  ✓ Report table saved")
        print(tabulate(agg_merge_sample, headers="keys", tablefmt="psql"))

        return df_merge

        
    except Exception as e:
        print(f"  ⚠ Error processing sample table: {e}")
        import traceback
        traceback.print_exc()
        return None


def organize_drug_experiment(
    source_base_dir: Path,
    output_base_dir: Path,
    drug_name: str,
    experiment_structure: Dict[str, Dict[str, Optional[Dict[str, Optional[Path]]]]]
) -> Dict[str, pd.DataFrame]:
    """
    Organize all experiments for a specific drug.
    
    Args:
        source_base_dir: Base directory containing source data
        output_base_dir: Base directory for organized output
        drug_name: Name of drug ('alk5i' or 'candesartan')
        experiment_structure: Dictionary defining folder structure
            Example:
            {
                'EXP1': {
                    'crop1': {
                        'images': Path('Crop1'),
                        'sample': Path('Sample.xls')
                    },
                    'crop2': {
                        'images': Path('Crop2'),
                        'sample': Path('Sample2.xls')
                    }
                },
                'EXP2': {
                    'crop1': {
                        'images': Path('Experiment2'),
                        'sample': Path('Sample.xls')
                    },
                    'crop2': None  # No Crop2 for EXP2
                }
            }
    
    Returns:
        Dictionary of processing reports per experiment
    """
    print(f"\n{'='*60}")
    print(f"ORGANIZING {drug_name.upper()} EXPERIMENTS")
    print(f"{'='*60}")
    
    reports = {}
    
    for exp_name, folders in experiment_structure.items():
        print(f"\n--- Processing {exp_name} ---")
        
        # Create output directory for this experiment
        exp_output_dir = output_base_dir / drug_name / exp_name
        exp_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process Crop1 if exists
        crop1_log = []
        crop1_sample_path = None
        if folders.get('crop1') and folders['crop1'] is not None:
            crop1_data = folders['crop1']
            
            # Extract images path
            if isinstance(crop1_data, dict):
                crop1_images_path = crop1_data.get('images')
                crop1_sample_path = crop1_data.get('sample')
            else:
                # Backward compatibility: if it's just a Path, treat it as images path
                crop1_images_path = crop1_data
                crop1_sample_path = None
            
            if crop1_images_path:
                crop1_path = source_base_dir / drug_name / crop1_images_path
                if crop1_path.exists():
                    crop1_log = process_crop1(crop1_path, exp_output_dir, f"{drug_name}_{exp_name}", drug_name)
                else:
                    print(f"  ⚠ Crop1 folder not found: {crop1_path}")
        
        # Process Crop2 if exists
        crop2_log = []
        if folders.get('crop2') and folders['crop2'] is not None:
            crop2_data = folders['crop2']
            
            # Extract images path
            if isinstance(crop2_data, dict):
                crop2_images_path = crop2_data.get('images')
                # Note: We don't use crop2 sample path as per user requirement
            else:
                # Backward compatibility: if it's just a Path, treat it as images path
                crop2_images_path = crop2_data
            
            if crop2_images_path:
                crop2_path = source_base_dir / drug_name / crop2_images_path
                if crop2_path.exists():
                    crop2_log = process_crop2(crop2_path, exp_output_dir, f"{drug_name}_{exp_name}", drug_name)
                else:
                    print(f"  ⚠ Crop2 folder not found: {crop2_path}")
        
        # Merge and create report
        if crop1_log or crop2_log:
            report_output_dir = output_base_dir / "processing_reports"
            report_output_dir.mkdir(parents=True, exist_ok=True)
            
            df_report = merge_experiments(
                crop1_log,
                crop2_log,
                report_output_dir,
                f"{drug_name}_{exp_name}"
            )
            
            # Verify all files were successfully copied
            all_logs = crop1_log + crop2_log
            verify_processed_files(
                processing_log=all_logs,
                output_dir=exp_output_dir,
                report_dir=report_output_dir,
                experiment_name=f"{drug_name}_{exp_name}"
            )
            
            # Add experiment column to the report
            df_report['experiment'] = exp_name
            
            reports[exp_name] = df_report

            # Process sample table if crop1 sample path exists
            if crop1_sample_path:
                sample_full_path = source_base_dir / drug_name / crop1_sample_path
                print(f"\n  Processing sample table: {sample_full_path}")
                _  = process_sample_table(
                    sample_path=sample_full_path,
                    comprehensive_report=df_report,
                    experiment_name=exp_name,
                    output_dir=exp_output_dir,
                    drug_name=drug_name
                )
    
    print(f"\n{'='*60}")
    print(f"COMPLETED {drug_name.upper()} ORGANIZATION")
    print(f"{'='*60}\n")

    return reports

