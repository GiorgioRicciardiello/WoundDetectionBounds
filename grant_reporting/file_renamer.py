"""
File Renamer Module

Core renaming logic for experimental image files including:
- Filename parsing
- Time-shift corrections
- Experiment tag insertion
"""

import re
from pathlib import Path
from typing import Tuple, Optional, Dict


def parse_filename(filename: str) -> Dict[str, str]:
    """
    Parse filename components from experimental image files.
    
    Expected pattern: PREFIX_WELL_REPLICATE_DDdHHhMMm.tif_crop
    Examples:
        - ALK2_A1_1_00d00h00m.tif_crop
        - alk_A1_1_00d05h30m.tif_crop
        - C2_B3_2_00d12h00m.tif_crop
    
    Args:
        filename: Filename string to parse
    
    Returns:
        Dictionary with components:
            - prefix: Cell line prefix (e.g., 'ALK2', 'alk', 'C2', 'can')
            - well: Well identifier (e.g., 'A1', 'B3')
            - replicate: Replicate number (e.g., '1', '2')
            - days: Days component of timestamp
            - hours: Hours component of timestamp
            - minutes: Minutes component of timestamp
            - extension: File extension (e.g., '.tif_crop')
    
    Raises:
        ValueError: If filename doesn't match expected pattern
    """
    # Pattern: PREFIX_WELL_REPLICATE_DDdHHhMMm.extension
    pattern = r'^([A-Za-z0-9]+)_([A-Z]\d+)_(\d+)_(\d+)d(\d+)h(\d+)m(\..+)$'
    
    match = re.match(pattern, filename)
    
    if not match:
        raise ValueError(f"Filename '{filename}' doesn't match expected pattern: PREFIX_WELL_REPLICATE_DDdHHhMMm.extension")
    
    return {
        'prefix': match.group(1),
        'well': match.group(2),
        'replicate': match.group(3),
        'days': match.group(4),
        'hours': match.group(5),
        'minutes': match.group(6),
        'extension': match.group(7)
    }


def apply_time_shift(hours: str, shift_hours: int) -> str:
    """
    Apply time shift to hours component.
    
    Args:
        hours: Original hours as string (e.g., '00', '05')
        shift_hours: Number of hours to add (e.g., 2)
    
    Returns:
        New hours value as zero-padded string (e.g., '02', '07')
    """
    original_hours = int(hours)
    new_hours = original_hours + shift_hours
    return f"{new_hours:02d}"


def add_experiment_tag(components: Dict[str, str], experiment_tag: str) -> str:
    """
    Build new filename with experiment tag inserted.
    
    Args:
        components: Parsed filename components from parse_filename()
        experiment_tag: Experiment identifier (e.g., 'EXP1', 'EXP2')
    
    Returns:
        New filename with format: PREFIX_WELL_REPLICATE_TAG_DDdHHhMMm.extension
        Example: ALK2_A1_1_EXP1_00d00h00m.tif_crop
    """
    return (
        f"{components['prefix']}_"
        f"{components['well']}_"
        f"{components['replicate']}_"
        f"{experiment_tag}_"
        f"{components['days']}d"
        f"{components['hours']}h"
        f"{components['minutes']}m"
        f"{components['extension']}"
    )


def rename_file(
    filename: str,
    experiment_tag: str,
    time_shift_hours: int = 0
) -> str:
    """
    Complete renaming pipeline: parse, shift time, add tag.
    
    Args:
        filename: Original filename
        experiment_tag: Experiment identifier (e.g., 'EXP1', 'EXP2')
        time_shift_hours: Hours to add to timestamp (default: 0)
    
    Returns:
        New filename with experiment tag and time shift applied
    
    Examples:
        >>> rename_file('ALK2_A1_1_00d00h00m.tif_crop', 'EXP1', 0)
        'ALK2_A1_1_EXP1_00d00h00m.tif_crop'
        
        >>> rename_file('alk_A1_1_00d00h00m.tif_crop', 'EXP1', 2)
        'alk_A1_1_EXP1_00d02h00m.tif_crop'
        
        >>> rename_file('alk_A1_1_00d01h00m.tif_crop', 'EXP1', 2)
        'alk_A1_1_EXP1_00d03h00m.tif_crop'
    """
    # Parse filename
    components = parse_filename(filename)
    
    # Apply time shift if needed
    if time_shift_hours != 0:
        components['hours'] = apply_time_shift(components['hours'], time_shift_hours)
    
    # Build new filename with experiment tag
    new_filename = add_experiment_tag(components, experiment_tag)
    
    return new_filename


def get_experiment_info(prefix: str) -> Tuple[str, int]:
    """
    Determine experiment number and crop type from filename prefix.
    
    Args:
        prefix: Filename prefix (e.g., 'ALK2', 'alk', 'ALK', 'C2', 'can', 'CAN')
    
    Returns:
        Tuple of (experiment_tag, time_shift_hours)
        
    Examples:
        >>> get_experiment_info('ALK2')  # EXP1, Crop1 (0h)
        ('EXP1', 0)
        
        >>> get_experiment_info('alk')   # EXP1, Crop2 (2h+)
        ('EXP1', 2)
        
        >>> get_experiment_info('ALK')   # EXP2
        ('EXP2', 0)
        
        >>> get_experiment_info('C2')    # EXP1, Crop1 (0h)
        ('EXP1', 0)
        
        >>> get_experiment_info('can')   # EXP1, Crop2 (2h+)
        ('EXP1', 2)
        
        >>> get_experiment_info('CAN')   # EXP2
        ('EXP2', 0)
    """
    # ALK5i experiment mapping
    if prefix == 'ALK2':  # EXP1, Crop1 (0h timepoint)
        return ('EXP1', 0)
    elif prefix == 'alk':  # EXP1, Crop2 (2h+ timepoint, needs shift)
        return ('EXP1', 2)
    elif prefix == 'ALK':  # EXP2
        return ('EXP2', 0)
    
    # Candesartan experiment mapping
    elif prefix == 'C2':   # EXP1, Crop1 (0h timepoint)
        return ('EXP1', 0)
    elif prefix == 'can':  # EXP1, Crop2 (2h+ timepoint, needs shift)
        return ('EXP1', 2)
    elif prefix == 'CAN':  # EXP2
        return ('EXP2', 0)
    
    else:
        raise ValueError(f"Unknown prefix '{prefix}'. Expected: ALK2, alk, ALK, C2, can, or CAN")


def auto_rename_file(filename: str, drug_name: Optional[str] = None) -> str:
    """
    Automatically rename file based on prefix detection.
    
    Determines experiment and time shift automatically from the filename prefix.
    Optionally replaces the original prefix with the drug name.
    
    Args:
        filename: Original filename
        drug_name: Optional drug name to replace the prefix (e.g., 'alk5i', 'candesartan')
    
    Returns:
        New filename with appropriate experiment tag and time shift
    
    Examples:
        >>> auto_rename_file('ALK2_A1_1_00d00h00m.tif_crop')
        'ALK2_A1_1_EXP1_00d00h00m.tif_crop'
        
        >>> auto_rename_file('ALK2_A1_1_00d00h00m.tif_crop', 'alk5i')
        'alk5i_A1_1_EXP1_00d00h00m.tif_crop'
        
        >>> auto_rename_file('alk_A1_1_00d00h00m.tif_crop', 'alk5i')
        'alk5i_A1_1_EXP1_00d02h00m.tif_crop'
        
        >>> auto_rename_file('ALK_A3_1_00d00h00m.tif_crop', 'alk5i')
        'alk5i_A3_1_EXP2_00d00h00m.tif_crop'
    """
    components = parse_filename(filename)
    experiment_tag, time_shift = get_experiment_info(components['prefix'])
    
    # Replace prefix with drug name if provided
    if drug_name:
        components['prefix'] = drug_name
    
    # Apply time shift if needed
    if time_shift != 0:
        components['hours'] = apply_time_shift(components['hours'], time_shift)
    
    # Build new filename with experiment tag
    new_filename = add_experiment_tag(components, experiment_tag)
    
    return new_filename

