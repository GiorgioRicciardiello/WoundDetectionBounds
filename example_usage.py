"""
Example: Using the Production-Ready API

This script demonstrates how to use the new sklearn-style API
for wound healing quantification.
"""

from library import Pipeline, PipelineConfig
from pathlib import Path
import pandas as pd


def example_1_quick_start():
    """Basic usage: load config and run pipeline."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Quick Start")
    print("="*60)

    # Load configuration from YAML
    config = PipelineConfig.from_yaml("config.example.yaml")

    # Validate (checks columns, paths, etc.)
    config.validate()
    print("✓ Config validated")

    # Create pipeline and run
    pipeline = Pipeline(config)
    results = pipeline.run()

    # Access results
    measurements = results["measurements"]
    trajectories = results["trajectories"]

    print(f"✓ Segmented {len(trajectories)} trajectories")
    print(f"✓ Generated {len(measurements)} measurements")

    return results


def example_2_segmentation_only():
    """Run only segmentation, skip analysis."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Segmentation Only")
    print("="*60)

    config = PipelineConfig.from_yaml("config.example.yaml")
    config.validate()

    # Skip analysis
    pipeline = Pipeline(config)
    results = pipeline.run(stages=["segmentation"])

    measurements = results["measurements"]
    print(f"✓ Saved segmentation to {config.output.get_segmentation_dir()}")
    print(f"✓ {len(measurements)} rows in measurements")

    return results


def example_3_custom_config():
    """Create config programmatically (no YAML file)."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Programmatic Config")
    print("="*60)

    from library import PipelineConfig, ColumnMapping, SegmentationConfig

    # Create config from scratch
    config = PipelineConfig(
        input_excel="/path/to/experiments.xlsx",
        columns=ColumnMapping(
            image_path="ImagePath",
            exposure="Treatment",
            experiment="Batch",
            sample_name="SampleID",
            time_min="TimeMinutes",
            cell_line="CellType",
        ),
        segmentation=SegmentationConfig(
            n_workers=8,
            use_kalman=True,
            save_debug_images=False,
        ),
        output_dir="./my_results",
        verbose=True,
    )

    # Validate
    try:
        config.validate()
        print("✓ Config created and validated")
    except FileNotFoundError as e:
        print(f"✗ Config error (expected in example): {e}")

    return config


def example_4_reuse_segmentation():
    """Segment once, then reuse results for multiple analyses."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Reuse Segmentation Results")
    print("="*60)

    config = PipelineConfig.from_yaml("config.example.yaml")
    config.validate()

    pipeline = Pipeline(config)

    # First run: segmentation only
    print("Run 1: Segmentation...")
    results_seg = pipeline.run(stages=["segmentation"])

    # Later: load cached results
    print("Run 2: Load cached results (no re-segmentation)...")
    config.segmentation.process_missing = False  # Load cached only
    results_cached = pipeline.load_results(stage="segmentation")

    measurements = results_cached["measurements"]
    print(f"✓ Loaded {len(measurements)} cached measurements")

    # Can now do custom analysis on the cached results
    print("✓ Ready for custom analysis...")

    return results_cached


def example_5_verification():
    """Optional: Launch verification GUI for manual review."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Verification GUI (Manual Review)")
    print("="*60)

    config = PipelineConfig.from_yaml("config.example.yaml")
    config.validate()

    pipeline = Pipeline(config)

    # Run segmentation first
    print("Segmenting...")
    results = pipeline.run(stages=["segmentation"])

    # Get verification interface
    app = pipeline.get_verification_interface()

    if app:
        print("\n✓ Launching verification GUI...")
        print("  Visit http://localhost:5000 in your browser")
        print("  Review t=0 images and mark correct/incorrect")
        print("  Optionally draw polygons for quantitative metrics")
        print("\nTo start (in production):")
        print("  app.run(debug=False, port=5000)")

        # Uncomment to actually run:
        # app.run(debug=False, port=5000)
    else:
        print("✗ Verification GUI not available (missing Flask)")

    return results


def example_6_component_reuse():
    """Use individual library components for custom workflows."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Component Reuse (Custom Analysis)")
    print("="*60)

    config = PipelineConfig.from_yaml("config.example.yaml")
    config.validate()

    pipeline = Pipeline(config)
    results = pipeline.run(stages=["segmentation"])

    # Access individual components
    trajectories = results["trajectories"]
    measurements = results["measurements"]

    print(f"✓ Loaded {len(trajectories)} trajectories")
    print(f"✓ {len(measurements)} measurements\n")

    # Example: custom filtering
    print("Custom analysis:")
    print("-" * 60)

    # Filter by QC status
    measurements_valid = measurements[measurements["qc_valid"] == True]
    print(f"  QC-valid trajectories: {len(measurements_valid)}")

    # Group by exposure
    by_exposure = measurements.groupby(
        config.columns.exposure,
        as_index=False,
    ).agg({
        "wound_area": ["mean", "std", "count"],
    })
    print(f"  Mean wound area by exposure:\n{by_exposure}\n")

    # Can now use any analysis library (scipy, statsmodels, etc.)
    from scipy.stats import ttest_ind

    dmso = measurements[measurements[config.columns.exposure] == "DMSO"]["wound_area"]
    alk5i = measurements[measurements[config.columns.exposure] == "Alk5i"]["wound_area"]

    if len(dmso) > 0 and len(alk5i) > 0:
        t_stat, p_val = ttest_ind(dmso, alk5i)
        print(f"  t-test (DMSO vs Alk5i):")
        print(f"    t = {t_stat:.3f}, p = {p_val:.4f}")

    return measurements


def example_7_reproducibility():
    """Demonstrate reproducibility through saved config."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Reproducibility")
    print("="*60)

    config = PipelineConfig.from_yaml("config.example.yaml")
    config.validate()

    pipeline = Pipeline(config)
    results = pipeline.run()

    # Config is automatically saved with results
    config_path = Path(config.output.base_dir) / "config_used.yaml"
    print(f"✓ Config saved to: {config_path}")

    # Anyone can reproduce the exact run:
    print("\nTo reproduce this run in the future:")
    print(f"  config = PipelineConfig.from_yaml('{config_path}')")
    print(f"  pipeline = Pipeline(config)")
    print(f"  results = pipeline.run()")

    return results


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("WOUND HEALING QUANTIFICATION - EXAMPLE USAGE")
    print("="*60)

    # Run examples
    # (Comment/uncomment as needed)

    try:
        example_3_custom_config()
    except Exception as e:
        print(f"Note: Example requires valid input file: {e}")

    print("\n" + "="*60)
    print("See PRODUCTION_API.md for complete documentation")
    print("="*60)
