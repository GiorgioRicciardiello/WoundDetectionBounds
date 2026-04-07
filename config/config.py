from pathlib import Path
project_root_path = Path(__file__).resolve().parents[1]
res_dir = project_root_path.joinpath('results')


data_root = Path(r'C:\Users\riccig01\OneDrive - The Mount Sinai Hospital\Projects\fanny\WoundHealing')

# Model identifier used as subfolder name under output_dir
MODEL_KEY: str = 'Quantification_kalman'

_output_dir = data_root.joinpath('results_quantification_updated')
_model_output_dir = _output_dir / MODEL_KEY

config = {
    'root_path': project_root_path,
    'data_in_dir': data_root,

    # This the output of images structured by experiments and the input for the wound quantification, duality I/O folder
    'data_in_organized': data_root.joinpath('processed_experiments'),

    'output_dir': _output_dir,
    'res_dir': res_dir,
    'static': project_root_path.joinpath('static'),

    # Model-specific output directory
    'model_output_dir': _model_output_dir,

    # Segmentation pipeline outputs
    'trajectories_pickle': _model_output_dir / 'trajectories.pickle',
    'final_legacy_table': _model_output_dir / 'final_legacy_table.xlsx',
    'aligned_legacy_table': _model_output_dir / 'aligned_legacy_table.xlsx',

    # Manual verification results (human ground-truth annotations at t=0)
    'verification_results': _output_dir / 'verification_results.xlsx',

    # Publication output directory
    # 'publication_dir': project_root_path / 'paper_publication',
    'publication_dir': project_root_path / 'manuscript',
}
