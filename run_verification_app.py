#!/usr/bin/env python
"""
Verification App Launcher
==========================

Launch the interactive web-based verification GUI for wound segmentation results.

This script provides a user-friendly interface to:
- Review segmentation quality at t=0 (initial timepoint)
- Mark segmentations as correct or incorrect
- Draw manual polygons to compute accuracy metrics (Dice, IoU, etc.)
- Export verification results to Excel
- Save progress for later review

Requirements
-----------
1. Configuration file (config.yaml) with valid input paths
2. Segmentation results (trajectories.pickle) from main.py or pipeline
3. Flask installed (pip install flask)

Usage
-----
    Basic launch:
        python run_verification_app.py

    With options:
        python run_verification_app.py --run-segmentation     # Segment first, then verify
        python run_verification_app.py --port 8080            # Use custom port
        python run_verification_app.py --help                 # Show all options

The app will be available at:
    http://localhost:5000 (default)
    http://localhost:<port> (if --port specified)

Exit the app with Ctrl+C in the terminal.

Author: Wound Healing Research Team
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

# Suppress non-critical warnings during startup
warnings.filterwarnings("ignore", category=UserWarning)


def check_dependencies() -> bool:
    """Check that required packages are installed.

    Returns
    -------
    bool
        True if all dependencies are satisfied, False otherwise.
    """
    try:
        import flask  # noqa: F401
        return True
    except ImportError:
        print("\n[ERROR] Flask is not installed.")
        print("        Install with: pip install flask")
        print("\n        Or activate your conda environment:")
        print("        conda activate imgai_env")
        return False


def check_config(config_path: Path = Path("config.yaml")) -> bool:
    """Validate that configuration file exists and is readable.

    Parameters
    ----------
    config_path : Path, optional
        Path to config file (default: config.yaml in current directory).

    Returns
    -------
    bool
        True if config is valid, False otherwise.
    """
    if not config_path.exists():
        print(f"\n[ERROR] Configuration file not found: {config_path}")
        print("\n        Create a config.yaml file or copy from config.example.yaml:")
        print("        cp config.example.yaml config.yaml")
        return False

    try:
        from library.config.pipeline_config import PipelineConfig
        config = PipelineConfig.from_yaml(config_path)
        config.validate()
        return True
    except FileNotFoundError as e:
        print(f"\n[ERROR] Config validation failed: {e}")
        print("\n        Update your config.yaml with valid paths:")
        print("        - input_excel: path to experiments.xlsx")
        print("        - output.base_dir: output directory")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error validating config: {e}")
        return False


def check_segmentation(config_path: Path = Path("config.yaml")) -> bool:
    """Check if segmentation results exist.

    Parameters
    ----------
    config_path : Path, optional
        Path to config file.

    Returns
    -------
    bool
        True if trajectories.pickle exists, False otherwise.
    """
    try:
        from library.config.pipeline_config import PipelineConfig

        config = PipelineConfig.from_yaml(config_path)
        seg_dir = Path(config.output.get_segmentation_dir())
        trajectories_path = seg_dir / "trajectories.pickle"

        if trajectories_path.exists():
            # Check file size to ensure it's not corrupted
            size_mb = trajectories_path.stat().st_size / (1024 * 1024)
            print(f"\n[OK] Found segmentation results")
            print(f"     Location: {trajectories_path}")
            print(f"     Size: {size_mb:.1f} MB")
            return True
        else:
            return False
    except Exception as e:
        print(f"\n[ERROR] Failed to check segmentation: {e}")
        return False


def run_segmentation(config_path: Path = Path("config.yaml")) -> bool:
    """Run the quantification segmentation pipeline.

    Parameters
    ----------
    config_path : Path, optional
        Path to config file.

    Returns
    -------
    bool
        True if segmentation succeeds, False otherwise.
    """
    print("\n" + "=" * 70)
    print("RUNNING SEGMENTATION")
    print("=" * 70)

    try:
        from library.pipeline import Pipeline
        from library.config.pipeline_config import PipelineConfig

        config = PipelineConfig.from_yaml(config_path)
        pipeline = Pipeline(config)

        print(f"\n[*] Segmenting {len(pd.read_excel(config.input_excel))} images...")
        print(f"    Workers: {config.segmentation.n_workers}")
        print(f"    Kalman filtering: {config.segmentation.temporal_mode}")

        results = pipeline.run(stages=["segmentation"])

        print(f"\n[OK] Segmentation complete")
        print(f"     Trajectories saved to:")
        print(f"     {results['trajectories_path']}")
        return True

    except Exception as e:
        print(f"\n[ERROR] Segmentation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def launch_verification_app(
    config_path: Path = Path("config.yaml"),
    port: int = 5000,
    debug: bool = False,
) -> bool:
    """Launch the verification app.

    Parameters
    ----------
    config_path : Path, optional
        Path to config file.
    port : int, optional
        Port number (default: 5000).
    debug : bool, optional
        Run in debug mode (default: False).

    Returns
    -------
    bool
        True if app starts successfully.
    """
    try:
        from library.pipeline import Pipeline
        from library.config.pipeline_config import PipelineConfig

        print("\n" + "=" * 70)
        print("LAUNCHING VERIFICATION APP")
        print("=" * 70)

        config = PipelineConfig.from_yaml(config_path)
        pipeline = Pipeline(config)

        print("\n[*] Initializing Flask application...")
        app = pipeline.get_verification_interface()

        if app is None:
            print("\n[ERROR] Failed to create Flask app")
            print("        Check that Flask is installed: pip install flask")
            return False

        print("[OK] Flask application created successfully")

        print("\n" + "=" * 70)
        print("VERIFICATION APP IS READY")
        print("=" * 70)
        print(f"\n[*] Server running on http://localhost:{port}")
        print(f"    Open this URL in your web browser to start reviewing")
        print(f"\n    Features:")
        print(f"    - Review wound segmentation at t=0 (initial frame)")
        print(f"    - Mark segmentations as correct or incorrect")
        print(f"    - Draw polygons to compute accuracy metrics")
        print(f"    - Export verification results to Excel")
        print(f"    - Session auto-saves (resume anytime)")
        print(f"\n    Press Ctrl+C to stop the server")
        print("\n" + "=" * 70)

        # Start the server
        app.run(debug=debug, port=port, host="0.0.0.0")

        return True

    except KeyboardInterrupt:
        print("\n\n[*] Server stopped by user")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to launch app: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port number (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask in debug mode (auto-reload on changes)",
    )
    parser.add_argument(
        "--run-segmentation",
        action="store_true",
        help="Run segmentation pipeline before launching verification app",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip prerequisite checks (for advanced users)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("WOUND HEALING VERIFICATION APP")
    print("=" * 70)

    # Step 1: Check dependencies
    if not args.skip_checks:
        print("\n[*] Checking dependencies...")
        if not check_dependencies():
            return 1

        print("    [OK] Flask installed")

        # Step 2: Validate configuration
        print("\n[*] Validating configuration...")
        if not check_config(args.config):
            return 1
        print("    [OK] Configuration valid")

    # Step 3: Check segmentation or run it
    print("\n[*] Checking segmentation results...")
    has_segmentation = check_segmentation(args.config)

    if not has_segmentation:
        if args.run_segmentation:
            print("    [*] Segmentation not found, running now...")
            if not run_segmentation(args.config):
                return 1
        else:
            print("    [WARN] Segmentation not found")
            print("\n    Options:")
            print("    1. Run segmentation first:")
            print("       python main.py")
            print("    2. Or use this script to run both:")
            print("       python run_verification_app.py --run-segmentation")
            response = input("\n    Run segmentation now? (y/n): ").strip().lower()
            if response != "y":
                print("\n[*] Exiting. Run segmentation first, then try again.")
                return 0
            if not run_segmentation(args.config):
                return 1

    # Step 4: Launch the app
    if not launch_verification_app(args.config, args.port, args.debug):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
