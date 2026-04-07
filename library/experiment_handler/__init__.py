"""
Experiment Handler Library

A library for organizing and standardizing experimental image files from ALK5i and 
Candesartan drug studies. Handles file renaming, time-shift corrections, and 
experiment tagging.
"""

from .file_renamer import (
    parse_filename,
    apply_time_shift,
    add_experiment_tag,
    rename_file
)

from .experiment_organizer import (
    process_crop1,
    process_crop2,
    merge_experiments,
    organize_drug_experiment
)

from .metadata_handler import (
    read_sample_sheet,
    get_available_conditions,
    generate_processing_report
)

__version__ = "1.0.0"
__all__ = [
    'parse_filename',
    'apply_time_shift',
    'add_experiment_tag',
    'rename_file',
    'process_crop1',
    'process_crop2',
    'merge_experiments',
    'organize_drug_experiment',
    'read_sample_sheet',
    'get_available_conditions',
    'generate_processing_report'
]
