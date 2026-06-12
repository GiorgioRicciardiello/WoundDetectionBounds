"""
Production-grade Pipeline orchestrator for wound healing quantification.

Modular, sklearn-style API:
    config = PipelineConfig.from_yaml("config.yaml")
    config.validate()

    pipeline = Pipeline(config)
    results = pipeline.run()
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional, Dict, Any
import json
import pickle
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from library.config.pipeline_config import PipelineConfig
from library.core.types import WoundDetectorConfig
from library.core.segmentation import run_quantification_pipeline, pickle_io


class SegmentationCache:
    """Manage segmentation results caching with overwrite prompts."""

    def __init__(self, output_dir: Path, overwrite_existing: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.output_dir / "segmentation_log.json"
        self.overwrite_existing = overwrite_existing
        self.log = self._load_log()

    def _load_log(self) -> Dict[str, Any]:
        """Load segmentation log if it exists."""
        if self.log_file.exists():
            try:
                with open(self.log_file) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def has_segmentation(self, identifier: str) -> bool:
        """Check if segmentation exists for identifier."""
        return identifier in self.log and self.log[identifier].get("completed")

    def mark_completed(self, identifier: str, metadata: Dict[str, Any]) -> None:
        """Record completion of segmentation."""
        self.log[identifier] = {
            "completed": True,
            "timestamp": datetime.now().isoformat(),
            **metadata,
        }
        self._save_log()

    def _save_log(self) -> None:
        """Save log to disk."""
        with open(self.log_file, "w") as f:
            json.dump(self.log, f, indent=2)

    def check_and_prompt_overwrite(self, n_existing: int, n_total: int) -> bool:
        """
        Check if results exist and prompt user.

        Returns
        -------
        bool
            True if should proceed (either no existing or user approved), False otherwise.
        """
        if n_existing == 0:
            return True

        if self.overwrite_existing:
            return True

        message = (
            f"\n⚠️  Found {n_existing}/{n_total} existing segmentations.\n"
            f"Proceed with overwrite? (y/n): "
        )
        response = input(message).strip().lower()
        return response == "y"


class Pipeline:
    """
    Main pipeline orchestrator.

    Modular design — researchers can use individual components or the full pipeline.
    """

    def __init__(self, config: PipelineConfig | str | Path):
        """
        Initialize pipeline.

        Parameters
        ----------
        config : PipelineConfig, str, or Path
            Configuration object or path to YAML config file.
        """
        if isinstance(config, (str, Path)):
            self.config = PipelineConfig.from_yaml(config)
        else:
            self.config = config

        # Validate on init
        self.config.validate()

        # Setup directories
        self.output_base = Path(self.config.output.base_dir)
        self.seg_dir = self.config.output.get_segmentation_dir()
        self.analysis_dir = self.config.output.get_analysis_dir()
        self.verification_dir = self.config.output.get_verification_dir()

        self.seg_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.verification_dir.mkdir(parents=True, exist_ok=True)

        # Initialize cache
        self.cache = SegmentationCache(
            self.seg_dir,
            overwrite_existing=self.config.overwrite_existing,
        )

        if self.config.verbose:
            print(f"\n{'='*60}")
            print("WOUND HEALING QUANTIFICATION PIPELINE")
            print(f"{'='*60}")
            print(self.config)
            print(f"{'='*60}\n")

    def run(
        self,
        stages: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full pipeline or specified stages.

        Parameters
        ----------
        stages : list[str], optional
            Which stages to run: ["segmentation", "analysis", "verification"].
            If None, runs all available stages.

        Returns
        -------
        dict
            Results dictionary with keys:
            - 'trajectories': Raw trajectory objects
            - 'measurements': Final measurements DataFrame
            - 'analysis': Statistical analysis results
            - 'config': Configuration used
            - 'metadata': Timing, counts, paths
        """
        if stages is None:
            stages = ["segmentation", "analysis"]

        results = {}

        if "segmentation" in stages:
            results.update(self._run_segmentation())

        if "analysis" in stages and "measurements" in results:
            results.update(self._run_analysis(results["measurements"]))

        # Save config for reproducibility
        if self.config.save_config_with_results:
            config_path = self.output_base / "config_used.yaml"
            self.config.to_yaml(config_path)
            if self.config.verbose:
                print(f"✓ Config saved: {config_path}")

        return results

    def _run_segmentation(self) -> Dict[str, Any]:
        """Run the segmentation pipeline."""
        if self.config.verbose:
            print("\n[STAGE 1/2] SEGMENTATION")
            print("-" * 60)

        # Load input data
        df_input = pd.read_excel(self.config.input_excel)

        # Map column names
        col_map = self.config.columns.to_dict()
        df_input = df_input.rename(columns=col_map)

        # Group by exposure × experiment (dynamics)
        exposures = df_input[self.config.columns.exposure].unique().tolist()
        experiments = df_input[self.config.columns.experiment].unique().tolist()

        if self.config.verbose:
            print(f"Exposures: {exposures}")
            print(f"Experiments: {experiments}")
            print(f"Total samples: {len(df_input)}")

        # Create detector config from pipeline config
        detector_cfg = WoundDetectorConfig(
            use_kalman=self.config.segmentation.use_kalman,
            kalman_Q=self.config.segmentation.kalman_Q,
            kalman_R_base=self.config.segmentation.kalman_R_base,
        )

        # Run quantification pipeline
        df_measurements, trajectories = run_quantification_pipeline(
            image_folder=Path(self.config.input_excel).parent,  # Adjust as needed
            output_root=self.seg_dir,
            exposures=exposures,
            experiments=experiments,
            process_missing=self.config.segmentation.process_missing,
            save_debug=self.config.segmentation.save_debug_images,
            n_workers=self.config.segmentation.n_workers,
            detector_config=detector_cfg,
        )

        # Save outputs (using configurable paths)
        traj_path = self.config.output.get_trajectories_pickle_path()
        meas_path = self.config.output.get_measurements_xlsx_path()

        # Ensure parent directories exist
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        meas_path.parent.mkdir(parents=True, exist_ok=True)

        pickle_io(traj_path, obj=trajectories, save=True)
        df_measurements.to_excel(meas_path, index=False)

        if self.config.verbose:
            print(f"[OK] Trajectories: {len(trajectories)}")
            print(f"[OK] Saved: {traj_path}")
            print(f"[OK] Saved: {meas_path}")

        return {
            "trajectories": trajectories,
            "measurements": df_measurements,
        }

    def _run_analysis(self, measurements: pd.DataFrame) -> Dict[str, Any]:
        """Run statistical analysis on measurements."""
        from library.core.analysis import AnalysisPipeline

        if self.config.verbose:
            print("\n[STAGE 2/2] ANALYSIS")
            print("-" * 60)

        # Get condition column and clean data
        condition_col = self.config.columns.condition
        measurement_col = "wound_area"

        if measurement_col not in measurements.columns:
            if self.config.verbose:
                print(f"[WARN] Measurement column '{measurement_col}' not found")
            return {"analysis": None}

        # Build factor columns mapping from analysis factors
        factor_cols = self.config.columns.analysis_factor_columns()

        # Initialize analysis
        pipeline = AnalysisPipeline(
            measurements=measurements,
            condition_col=condition_col,
            measurement_col=measurement_col,
            control_condition=self.config.analysis.control_condition,
            effect_size_metric=self.config.analysis.effect_size_metric,
            correction_method=self.config.analysis.multiple_comparison_correction,
            alpha=self.config.analysis.alpha,
            stratify_by=self.config.analysis.stratify_by,
            interaction_factors=self.config.analysis.interaction_factors,
            factor_cols=factor_cols,
        )

        # Get conditions
        conditions = pipeline.get_conditions()
        if self.config.verbose:
            print(f"[OK] Conditions: {conditions}")
            print(f"[OK] Control: {self.config.analysis.control_condition}")
            print(f"[OK] Samples: {len(measurements)}")

        # Run analysis
        df_summary = pipeline.summary_statistics()
        df_pairwise = pipeline.run_pairwise_comparisons()

        if self.config.verbose:
            print(f"[OK] Summary statistics computed")
            print(f"[OK] Pairwise comparisons completed")

        # Save outputs (Excel and/or JSON) to configurable paths
        output_formats = self.config.analysis.output_formats or ["excel", "json"]

        if "excel" in output_formats:
            excel_path = self.config.output.get_analysis_results_xlsx_path()
            excel_path.parent.mkdir(parents=True, exist_ok=True)
            pipeline.to_excel(str(excel_path))
            if self.config.verbose:
                print(f"[OK] Saved: {excel_path}")

        if "json" in output_formats:
            json_path = self.config.output.get_analysis_results_json_path()
            json_path.parent.mkdir(parents=True, exist_ok=True)
            pipeline.to_json(str(json_path))
            if self.config.verbose:
                print(f"[OK] Saved: {json_path}")

        return {
            "analysis": {
                "summary_statistics": df_summary,
                "pairwise_comparisons": df_pairwise,
                "control_condition": self.config.analysis.control_condition,
                "effect_size_metric": self.config.analysis.effect_size_metric,
                "n_conditions": len(conditions),
                "conditions": conditions,
            }
        }

    def get_verification_interface(self):
        """
        Get the verification GUI interface (optional).

        Returns
        -------
        object
            Flask app or URL for verification interface.
        """
        try:
            from library.verification.app import create_app

            trajectories_path = self.seg_dir / "trajectories.pickle"
            output_dir = self.verification_dir

            if not trajectories_path.exists():
                raise FileNotFoundError("Run segmentation first")

            app = create_app(
                trajectories_path=str(trajectories_path),
                output_dir=str(output_dir),
            )
            return app
        except ImportError:
            warnings.warn("Verification GUI requires Flask. Install with: pip install flask")
            return None

    def load_results(
        self,
        stage: str = "segmentation",
    ) -> Dict[str, Any] | pd.DataFrame:
        """
        Load previously computed results.

        Parameters
        ----------
        stage : str
            Which stage to load: "segmentation", "analysis", "verification".

        Returns
        -------
        dict or DataFrame
            Loaded results or measurements.
        """
        if stage == "segmentation":
            traj_path = self.seg_dir / "trajectories.pickle"
            meas_path = self.seg_dir / "experiments.xlsx"

            if not traj_path.exists() or not meas_path.exists():
                raise FileNotFoundError("Segmentation results not found")

            trajectories = pickle_io(traj_path, save=False)
            measurements = pd.read_excel(meas_path)

            return {
                "trajectories": trajectories,
                "measurements": measurements,
            }

        elif stage == "analysis":
            # Load analysis results
            raise NotImplementedError("Analysis loading in progress")

        else:
            raise ValueError(f"Unknown stage: {stage}")
