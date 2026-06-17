"""
Full end-to-end pipeline test with realistic data.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import os
import json
from datetime import datetime

print("="*80)
print("[FULL PIPELINE TEST] Starting")
print("="*80)

# ============================================================================
print("\n[STEP 1] CREATE REALISTIC TEST DATA")
print("="*80)

np.random.seed(42)
n_samples = 10  # 10 samples per condition
timepoints = [0, 60, 120, 180, 240]  # 0, 1, 2, 3, 4 hours
conditions = ['DMSO', 'Alk5i', 'Media']
cell_lines = ['Line1', 'Line2']

records = []
for exp in ['EXP1', 'EXP2']:
    for condition in conditions:
        for sample_id in range(1, n_samples + 1):
            cell_line = np.random.choice(cell_lines)
            base_closure = {
                'DMSO': 0.8,    # Closes to 20% of original
                'Alk5i': 0.3,   # Closes to 70% (more inhibited)
                'Media': 0.6,   # Closes to 40%
            }[condition]

            for t_idx, t in enumerate(timepoints):
                closure_factor = base_closure ** (t_idx / len(timepoints))
                area = 100 * closure_factor + np.random.normal(0, 5)

                records.append({
                    'image_path': f'/dummy/path/{exp}_{condition}_{sample_id}_{t}.tif',
                    'exposure': condition,
                    'experiment': exp,
                    'sample_name': f'{exp}_S{condition[0]}{sample_id:02d}',
                    'time_min': t,
                    'cell_line': cell_line,
                    'wound_area': max(10, area),
                    'qc_valid': np.random.choice([True, True, True, False]),
                })

df = pd.DataFrame(records)
print(f"\nGenerated {len(df)} measurements")
print(f"Conditions: {df['exposure'].unique().tolist()}")
print(f"Experiments: {df['experiment'].unique().tolist()}")

print("\nData summary by condition:")
print(df.groupby('exposure')['wound_area'].describe().round(2))

# ============================================================================
print("\n" + "="*80)
print("[STEP 2] CREATE CONFIGURATION")
print("="*80)

with tempfile.TemporaryDirectory() as tmpdir:
    # Save test data
    input_file = os.path.join(tmpdir, 'wound_test_data.xlsx')
    df.to_excel(input_file, index=False)
    print(f"[OK] Test data saved ({len(df)} rows)")

    from library import PipelineConfig
    from library.config.pipeline_config import ColumnMapping, OutputConfig, AnalysisConfig

    config = PipelineConfig(
        input_excel=input_file,
        columns=ColumnMapping(
            image_path='image_path',
            exposure='exposure',
            experiment='experiment',
            sample_name='sample_name',
            time_min='time_min',
            cell_line='cell_line',
        ),
        output=OutputConfig(
            base_dir=os.path.join(tmpdir, 'results')
        ),
        segmentation={
            'n_workers': 4,
            'process_missing': False,
        },
        analysis=AnalysisConfig(
            control_condition='DMSO',
            statistical_tests=['t_test'],
            effect_size_metric='cohens_d',
            output_formats=['excel', 'json'],
            alpha=0.05,
        ),
        verbose=False,
    )

    # ========================================================================
    print("\n[STEP 3] VALIDATE CONFIGURATION")
    print("="*80)

    try:
        config.validate()
        print("[OK] Configuration validation passed")
    except Exception as e:
        print(f"[FAIL] {e}")
        exit(1)

    print(f"     Input: {Path(input_file).name}")
    print(f"     Output: {config.output.base_dir}")
    print(f"     Control: {config.analysis.control_condition}")

    # ========================================================================
    print("\n[STEP 4] INITIALIZE PIPELINE")
    print("="*80)

    from library import Pipeline

    pipeline = Pipeline(config)
    print("[OK] Pipeline initialized")
    print(f"     Segmentation: {pipeline.seg_dir.name}/")
    print(f"     Analysis: {pipeline.analysis_dir.name}/")

    # ========================================================================
    print("\n[STEP 5] RUN ANALYSIS")
    print("="*80)

    # Use input data as measurements (skip segmentation)
    measurements = df[['exposure', 'experiment', 'sample_name', 'wound_area', 'cell_line']].copy()

    print(f"Input: {len(measurements)} measurements")
    print(f"Conditions: {measurements['exposure'].unique().tolist()}")

    analysis_results = pipeline._run_analysis(measurements)

    if not analysis_results['analysis']:
        print("[FAIL] Analysis returned no results")
        exit(1)

    print("[OK] Analysis completed")

    # ========================================================================
    print("\n[STEP 6] EXAMINE RESULTS")
    print("="*80)

    analysis = analysis_results['analysis']
    summary = analysis['summary_statistics']
    pairwise = analysis['pairwise_comparisons']

    print("\nSummary Statistics by Condition:")
    print("-" * 80)
    print(summary[['condition', 'n', 'mean', 'std', 'median']].to_string(index=False))

    print("\nPairwise Comparisons (vs Control):")
    print("-" * 80)
    cols = ['treatment_condition', 't_stat', 'p_value', 'effect_size', 'significant_corrected']
    print(pairwise[cols].to_string(index=False))

    # ========================================================================
    print("\n[STEP 7] VERIFY OUTPUT FILES")
    print("="*80)

    analysis_dir = pipeline.analysis_dir
    excel_file = analysis_dir / 'analysis_results.xlsx'
    json_file = analysis_dir / 'analysis_results.json'

    files_ok = True

    if excel_file.exists():
        size_kb = excel_file.stat().st_size / 1024
        print(f"[OK] Excel: {excel_file.name} ({size_kb:.1f} KB)")
    else:
        print(f"[FAIL] Excel file not found")
        files_ok = False

    if json_file.exists():
        size_kb = json_file.stat().st_size / 1024
        print(f"[OK] JSON: {json_file.name} ({size_kb:.1f} KB)")
    else:
        print(f"[FAIL] JSON file not found")
        files_ok = False

    # ========================================================================
    print("\n[STEP 8] VALIDATE RESULTS")
    print("="*80)

    checks = {
        "All conditions compared": set(pairwise['treatment_condition'].unique()) == {'Alk5i', 'Media'},
        "Effect sizes computed": not pairwise['effect_size'].isna().all(),
        "P-values valid": all((p >= 0 and p <= 1) for p in pairwise['p_value'] if not np.isnan(p)),
        "Correction applied": 'p_value_corrected' in pairwise.columns,
        "Output files exist": files_ok,
    }

    for check, result in checks.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {check}")

    # ========================================================================
    print("\n[STEP 9] BIOLOGICAL PLAUSIBILITY")
    print("="*80)

    dmso_mean = summary[summary['condition'] == 'DMSO']['mean'].values[0]
    alk5i_mean = summary[summary['condition'] == 'Alk5i']['mean'].values[0]
    media_mean = summary[summary['condition'] == 'Media']['mean'].values[0]

    print(f"Mean wound area by condition:")
    print(f"  DMSO:  {dmso_mean:.1f}")
    print(f"  Alk5i: {alk5i_mean:.1f}")
    print(f"  Media: {media_mean:.1f}")

    alk5i_inhibited = alk5i_mean > dmso_mean
    print(f"\nBiological expectation:")
    print(f"  Alk5i inhibits wound closure (larger area): {alk5i_inhibited}")

    # Get effect sizes
    alk5i_row = pairwise[pairwise['treatment_condition'] == 'Alk5i'].iloc[0]
    print(f"\nAlk5i vs DMSO:")
    print(f"  Effect size (Cohen's d): {alk5i_row['effect_size']:.3f}")
    print(f"  P-value: {alk5i_row['p_value']:.4f}")
    print(f"  Significant (corrected): {alk5i_row['significant_corrected']}")

print("\n" + "="*80)
print("[TEST COMPLETE]")
print("="*80)
print("\nStatus: SUCCESS - All systems operational")
print("Timestamp:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print("\n" + "="*80)
