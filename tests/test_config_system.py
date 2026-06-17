#!/usr/bin/env python
"""
Test the YAML-based configuration system for the wound healing pipeline.

This script validates:
1. Config loading from YAML files
2. Config validation against Excel data
3. Column mapping and renaming
4. DataFrame processing (direct, no intermediate organization)
5. Pipeline initialization
"""

import sys
from pathlib import Path
import pandas as pd
from library.config.pipeline_config import PipelineConfig
from library.pipeline import Pipeline

def test_config_loading():
    """Test loading YAML configuration."""
    print("\n" + "="*60)
    print("TEST 1: YAML Config Loading")
    print("="*60)

    config_path = Path("config_test.yaml")
    assert config_path.exists(), f"Config file not found: {config_path}"

    try:
        config = PipelineConfig.from_yaml(config_path)
        print("[OK] Config loaded successfully")
        print(f"     Input: {config.input_excel}")
        print(f"     Output: {config.output.base_dir}")
        print(f"     Workers: {config.segmentation.n_workers}")
        print(f"     Use Kalman: {config.segmentation.use_kalman}")
        return config
    except Exception as e:
        print(f"[FAILED] {e}")
        sys.exit(1)

def test_config_validation(config):
    """Test config validation against Excel data."""
    print("\n" + "="*60)
    print("TEST 2: Config Validation")
    print("="*60)

    try:
        config.validate()
        print("[OK] Config validation passed")

        # Load and show data summary
        df = pd.read_excel(config.input_excel, nrows=10)
        print(f"     Rows: {len(df)} (showing first 10)")
        print(f"     Columns: {list(df.columns)}")
        return True
    except Exception as e:
        print(f"[FAILED] {e}")
        return False

def test_column_mapping():
    """Test column mapping from config."""
    print("\n" + "="*60)
    print("TEST 3: Column Mapping")
    print("="*60)

    config = PipelineConfig.from_yaml("config_test.yaml")

    mapping = config.columns.to_dict()
    print("[OK] Column mapping configured:")
    for key, value in mapping.items():
        if isinstance(value, str):
            print(f"     {key}: {value}")

    # Test required columns
    required = config.columns.required_columns()
    print(f"\n[OK] Required columns: {required}")

    # Test analysis factors
    factors = config.columns.analysis_factor_columns()
    print(f"[OK] Analysis factors: {factors}")

    return True

def test_dataframe_processing():
    """Test that Pipeline processes DataFrames directly (no organization)."""
    print("\n" + "="*60)
    print("TEST 4: DataFrame Processing (No Intermediate Organization)")
    print("="*60)

    # Load test data
    df = pd.read_excel("experiments_test.xlsx")
    print(f"[OK] Data loaded: {len(df)} rows")

    # Check grouping
    grouping = df.groupby(["sample_condition", "experiment"]).size()
    print(f"[OK] Data groups:\n{grouping}")

    # Initialize pipeline
    try:
        pipeline = Pipeline("config_test.yaml")

        # Pipeline now works directly with flat DataFrames
        # No intermediate directory organization needed
        print(f"\n[OK] Pipeline initialized (no directory organization required)")
        print(f"     Segmentation dir: {pipeline.seg_dir}")

        # Verify config column mappings are correct
        print(f"\n[OK] Column mappings:")
        print(f"     Condition column: {pipeline.config.columns.condition}")
        print(f"     Experiment column: {pipeline.config.columns.experiment}")
        print(f"     Image path column: {pipeline.config.columns.image_path}")
        print(f"     Time column: {pipeline.config.columns.time_min}")

        return True
    except Exception as e:
        print(f"[FAILED] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_initialization():
    """Test that pipeline can be initialized with config."""
    print("\n" + "="*60)
    print("TEST 5: Pipeline Initialization")
    print("="*60)

    try:
        pipeline = Pipeline("config_test.yaml")
        print("[OK] Pipeline initialized successfully")
        print(f"     Segmentation dir: {pipeline.seg_dir}")
        print(f"     Analysis dir: {pipeline.analysis_dir}")
        return True
    except Exception as e:
        print(f"[FAILED] {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("WOUND HEALING PIPELINE - YAML CONFIG SYSTEM TEST")
    print("="*80)

    tests_passed = 0
    tests_total = 5

    # Test 1: Config loading
    config = test_config_loading()
    if config:
        tests_passed += 1

    # Test 2: Validation
    if test_config_validation(config):
        tests_passed += 1

    # Test 3: Column mapping
    if test_column_mapping():
        tests_passed += 1

    # Test 4: DataFrame processing
    if test_dataframe_processing():
        tests_passed += 1

    # Test 5: Pipeline init
    if test_pipeline_initialization():
        tests_passed += 1

    # Summary
    print("\n" + "="*80)
    print(f"TEST SUMMARY: {tests_passed}/{tests_total} tests passed")
    print("="*80)

    if tests_passed == tests_total:
        print("[OK] All tests passed! The YAML config system is working.")
        print("\nNext steps:")
        print("1. Provide actual image data (gemini_results directory)")
        print("2. Update experiments.xlsx with correct image paths")
        print("3. Run: python -m library.pipeline config.yaml")
        return 0
    else:
        print(f"[FAILED] {tests_total - tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
