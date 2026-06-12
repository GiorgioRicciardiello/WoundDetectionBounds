"""
Organize Experiments Script

Main execution script for organizing ALK5i and Candesartan experimental image files.
Handles file renaming, time-shift corrections, and experiment tagging.

Configure the paths below and run directly from your IDE.
"""

from pathlib import Path
import sys

# Add library to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from library.experiment_handler.experiment_organizer import organize_drug_experiment
from library.experiment_handler.metadata_handler import generate_processing_report
from config.config import config


def organize_experiments(source_base_dir:Path=config.get('data_in_dir'),
                         output_base_dir:Path=config.get('data_in_organized')):
    """
    Organizes experimental data files into structured directories and processes experiment
    reports based on predefined drug-specific configurations. This function handles both `ALK5i`
    and `Candesartan` experiment datasets by reading the input data structure, processing files
    accordingly, and generating reports.

    Main function to organize experimental files.

    Configure the parameters below and run this script directly from your IDE.

    :param source_base_dir: Base directory containing the raw experimental data. Defaults to the
        value defined in `config.get('data_in_dir')`.
    :type source_base_dir: Path

    :param output_base_dir: Base directory for saving the organized files and processing
        reports. Defaults to the value defined in `config.get('data_in_organized')`.
    :type output_base_dir: Path

    :return: None
    """
    # ============================================
    # CONFIGURATION - Edit these parameters
    # ============================================
    
    # Source directory containing raw experimental data
    # This should point to the folder containing 'alk5i' and 'candesartan' subdirectories
    # source_base_dir:Path = config.get('data_in_dir')

    # Output directory for organized files
    # output_base_dir:Path = config.get('data_in_organized') # .joinpath(r"data/processed_experiments")
    
    # ============================================
    
    print("\n" + "="*70)
    print("EXPERIMENT FILE ORGANIZATION SCRIPT")
    print("="*70)
    print(f"\nSource: {source_base_dir}")
    print(f"Output: {output_base_dir}")
    
    # Define experiment structure for ALK5i
    alk5i_structure = {
        'EXP1': {
            'crop1': {
                    'images':  Path(r'Experiment 1_111425\Timepoint 0_Crop1'), # 0h timepoint (ALK2 prefix)
                    'sample': Path(r'Experiment 1_111425\alk Sample.xls')  # configuration table of experiments
            },
            'crop2': {'images':  Path(r'Experiment 1_111425\Timepoint after 2h_Crop2'),  # 2h+ timepoint (alk prefix, needs +2h shift)
                      'sample': Path(r'Experiment 1_111425\ALK2 Sample.xls'),  # configuration table of experiments
                      }
        },
        'EXP2': {
            'crop1': {
                'images': Path(r'Experiment 2_112125\Crop1'),
                'sample': Path(r'Experiment 2_112125\ALK Sample.xls')
            },  # All timepoints (ALK prefix)
            'crop2': {
                'images': None,  # No Crop2 for EXP2
                'sample': None
            }
        }
    }
    
    # Define experiment structure for Candesartan
    candesartan_structure = {
        'EXP1': {
            'crop1': {
                'images': Path(r'Experiment 1_111425\Timepoint 0_Crop1'),
                'sample': Path(r'Experiment 1_111425\can Sample.xls')
            },      # 0h timepoint (C2 prefix)
            'crop2':{
                'images': Path(r'Experiment 1_111425\Timepoint after 2h_Crop2'),
                'sample': Path(r'Experiment 1_111425\CAN2 Sample.xls')
            }     # 2h+ timepoint (can prefix, needs +2h shift)
        },
        'EXP2': {
            'crop1': {
                'images': Path(r'Experiment 2_112125\Crop1'),
                'sample': Path(r'Experiment 2_112125\CAN Sample.xls')
            },      # 0h timepoint (C2 prefix)
        },
    }
    # Process ALK5i experiments
    print("\n" + "="*70)
    print("PROCESSING ALK5i")
    print("="*70)

    try:
        alk5i_reports = organize_drug_experiment(
            source_base_dir=source_base_dir,
            output_base_dir=output_base_dir,
            drug_name='alk5i',
            experiment_structure=alk5i_structure
        )

        # Generate comprehensive report for ALK5i
        if alk5i_reports:
            report_dir = output_base_dir / "processing_reports"
            generate_processing_report(alk5i_reports, report_dir, 'alk5i')

    except Exception as e:
        print(f"\n⚠ Error processing ALK5i: {e}")
        import traceback
        traceback.print_exc()

    # Process Candesartan experiments
    print("\n" + "="*70)
    print("PROCESSING CANDASARTAN")
    print("="*70)

    # Process Candasertan experiments

    try:
        candesartan_reports = organize_drug_experiment(
            source_base_dir=source_base_dir,
            output_base_dir=output_base_dir,
            drug_name='Candasertan',
            experiment_structure=candesartan_structure
        )
        
        # Generate comprehensive report for Candesartan
        if candesartan_reports:
            report_dir = output_base_dir / "processing_reports"
            generate_processing_report(candesartan_reports, report_dir, 'candasertan')
    
    except Exception as e:
        print(f"\n⚠ Error processing Candesartan: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("ORGANIZATION COMPLETE")
    print("="*70)
    print(f"\nOrganized files saved to: {output_base_dir}")
    print(f"Processing reports saved to: {output_base_dir / 'processing_reports'}")


if __name__ == "__main__":
    # import argparse
    # parser = argparse.ArgumentParser(description='Organize experimental image files')
    # parser.add_argument('--test', action='store_true',
    #                     help='Run in test mode using data_in_organized_test output directory')
    # args = parser.parse_args()
    #
    # if args.test:
    #     print("\n" + "="*70)
    #     print("RUNNING IN TEST MODE")
    #     print("="*70)
    #     output_dir = config.get('data_in_organized_test')
    #     print(f"Test output directory: {output_dir}")
    # else:
    #     output_dir = config.get('data_in_organized')

    output_dir = config.get('data_in_organized_test')
    organize_experiments(source_base_dir=config.get('data_in_dir'),
                         output_base_dir=output_dir)

