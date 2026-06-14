#!/usr/bin/env python
"""
Verification App for Ablation Study Results
=============================================

Launch the verification GUI for the Kalman filter ablation study.

Automatically points to:
  Z:\\DATA\\elahi\\giocrm\\WoundHealingImgs\\results_06122026\\ablation\\kalman_hard\\

This is a quick launcher that skips config validation and directly loads
the segmentation results from the ablation study directory.

Usage
-----
    python run_ablation_verification.py

    # Custom port
    python run_ablation_verification.py --port 8080

    # Debug mode
    python run_ablation_verification.py --debug

Visit http://localhost:5000 in your browser.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)


def check_dependencies() -> bool:
    """Check that Flask is installed."""
    try:
        import flask  # noqa: F401
        return True
    except ImportError:
        print("\n[ERROR] Flask is not installed.")
        print("        Install with: pip install flask")
        return False


def launch_ablation_verification(
    ablation_dir: Path,
    port: int = 5000,
    debug: bool = False,
) -> bool:
    """Launch verification app for ablation results.

    Parameters
    ----------
    ablation_dir : Path
        Path to ablation results directory
    port : int, optional
        Port number (default: 5000)
    debug : bool, optional
        Run in debug mode

    Returns
    -------
    bool
        True if successful
    """
    try:
        from library.pipeline import Pipeline

        seg_dir = ablation_dir / "segmentation"
        trajectories_path = seg_dir / "trajectories.pickle"

        if not trajectories_path.exists():
            print(f"\n[ERROR] Trajectories not found: {trajectories_path}")
            return False

        print("\n" + "=" * 70)
        print("ABLATION STUDY VERIFICATION")
        print("=" * 70)
        print(f"\n[*] Loading segmentation results...")
        print(f"    Path: {trajectories_path}")

        # Create mock pipeline-like object to use get_verification_interface
        # Actually, let's just call the app creation directly
        from library.verification.app import create_app

        print(f"\n[*] Initializing Flask application...")
        app = create_app(
            trajectories_path=str(trajectories_path),
            output_dir=str(seg_dir),
        )

        print("[OK] Flask application created successfully")

        print("\n" + "=" * 70)
        print("VERIFICATION APP IS READY")
        print("=" * 70)
        print(f"\n[*] Dataset: Kalman Hard Ablation Study")
        print(f"    Location: {ablation_dir}")
        print(f"    Server: http://localhost:{port}")
        print(f"\n[*] Features available:")
        print(f"    - Review segmentation quality")
        print(f"    - Mark correct/incorrect")
        print(f"    - Draw polygons, compute metrics")
        print(f"    - Export results to Excel")
        print(f"\n    Press Ctrl+C to stop")
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
    # Hardcoded ablation path (using forward slashes to avoid escape issues)
    ablation_dir = Path(
        r"Z:\DATA\elahi\giocrm\WoundHealingImgs\results_06122026\ablation\kalman_hard"
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="Run Flask in debug mode",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=ablation_dir,
        help=f"Ablation results directory (default: {ablation_dir})",
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("ABLATION STUDY - VERIFICATION APP")
    print("=" * 70)

    # Check dependencies
    print("\n[*] Checking dependencies...")
    if not check_dependencies():
        return 1
    print("    [OK] Flask installed")

    # Check directory exists
    if not args.dir.exists():
        print(f"\n[ERROR] Directory not found: {args.dir}")
        return 1
    print(f"\n[OK] Directory found: {args.dir}")

    # Check trajectories exist
    trajectories = args.dir / "segmentation" / "trajectories.pickle"
    if not trajectories.exists():
        print(f"\n[ERROR] Trajectories not found: {trajectories}")
        return 1
    print(f"[OK] Trajectories found ({trajectories.stat().st_size / (1024**3):.1f} GB)")

    # Launch
    if not launch_ablation_verification(args.dir, args.port, args.debug):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
