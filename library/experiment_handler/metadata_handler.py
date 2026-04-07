"""
Metadata Handler Module

Handles metadata and sample spreadsheet management for experimental data.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional


def read_sample_sheet(excel_path: Path) -> pd.DataFrame:
    """
    Read sample spreadsheet containing experiment metadata.
    
    Args:
        excel_path: Path to Excel file (e.g., 'alk Sample.xls')
    
    Returns:
        DataFrame with sample information
    """
    try:
        df = pd.read_excel(excel_path)
        print(f"✓ Loaded sample sheet: {excel_path.name}")
        print(f"  Rows: {len(df)}, Columns: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"⚠ Error reading {excel_path}: {e}")
        return pd.DataFrame()


def get_available_conditions(df: pd.DataFrame, experiment_filter: Optional[str] = None) -> List[str]:
    """
    Extract available conditions from sample spreadsheet.
    
    Args:
        df: Sample DataFrame
        experiment_filter: Optional filter for specific experiment (e.g., 'EXP1', 'EXP2')
    
    Returns:
        List of available condition identifiers
    """
    # This is a placeholder - actual implementation depends on spreadsheet structure
    # User should customize based on their specific Excel format
    
    if df.empty:
        return []
    
    # Example: if spreadsheet has 'Sample' column
    if 'Sample' in df.columns:
        conditions = df['Sample'].dropna().unique().tolist()
        return conditions
    
    return []


def generate_processing_report(
    processing_logs: Dict[str, pd.DataFrame],
    output_dir: Path,
    drug_name: str
) -> Path:
    """
    Generate comprehensive processing report for all experiments.
    
    Args:
        processing_logs: Dictionary of experiment reports
        output_dir: Directory to save the report
        drug_name: Name of drug
    
    Returns:
        Path to generated report
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Combine all experiment reports
    all_reports = []
    for exp_name, df in processing_logs.items():
        df_copy = df.copy()
        df_copy['experiment'] = exp_name
        all_reports.append(df_copy)
    
    if all_reports:
        combined_df = pd.concat(all_reports, ignore_index=True)
        
        # Reorder columns
        cols = ['experiment', 'original_file', 'new_file', 'source_folder', 'time_shift', 'status']
        combined_df = combined_df[cols]
        
        # Save comprehensive report
        report_path = output_dir / f"{drug_name}_comprehensive_report.csv"
        combined_df.to_csv(report_path, index=False)
        
        # Print summary
        print(f"\n📊 Comprehensive Report: {report_path}")
        print(f"   Total files processed: {len(combined_df)}")
        print(f"   Successful: {sum(combined_df['status'] == 'success')}")
        print(f"   Errors: {sum(combined_df['status'] != 'success')}")
        
        return report_path
    
    return None


def validate_processed_files(
    output_dir: Path,
    expected_prefixes: List[str]
) -> Dict[str, int]:
    """
    Validate processed files in output directory.
    
    Args:
        output_dir: Directory containing processed files
        expected_prefixes: List of expected filename prefixes
    
    Returns:
        Dictionary with validation statistics
    """
    stats = {
        'total_files': 0,
        'by_prefix': {},
        'missing_exp_tag': 0
    }
    
    if not output_dir.exists():
        return stats
    
    # Count files
    image_files = list(output_dir.glob("*.tif_crop")) + list(output_dir.glob("*.tif"))
    stats['total_files'] = len(image_files)
    
    # Count by prefix
    for prefix in expected_prefixes:
        count = len([f for f in image_files if f.name.startswith(prefix)])
        stats['by_prefix'][prefix] = count
    
    # Check for experiment tags
    for img_file in image_files:
        if 'EXP' not in img_file.name:
            stats['missing_exp_tag'] += 1
    
    return stats
