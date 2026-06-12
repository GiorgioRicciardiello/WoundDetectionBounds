"""
Production-grade configuration system for wound healing pipeline.

Loads YAML config, validates against input data, and provides safe defaults.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
import pandas as pd


@dataclass
class AnalysisFactor:
    """Definition of an analysis factor (stratification/interaction variable).

    Example: concentration_mm column named as "concentration" for use in
    stratify_by and interaction_factors lists.
    """
    name: str
    column: str


@dataclass
class ColumnMapping:
    """Configurable column name mapping for input data.

    Separates trajectory identifiers (fixed: condition, experiment, sample_name)
    from analysis factors (configurable: any domain-specific variables).

    Trajectory identifiers define which images belong to the same temporal sequence.
    Analysis factors are used for statistical comparisons (stratification/interaction).
    """

    # Infrastructure (always required)
    image_path: str = "image_path"
    time_min: str = "time_min"

    # Trajectory identifiers (always required, define sample identity)
    condition: str = "condition"
    experiment: str = "experiment"
    sample_name: str = "sample_name"

    # Analysis factors (configurable, optional, domain-specific)
    factors: list[AnalysisFactor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return all non-None column mappings."""
        data = {
            "image_path": self.image_path,
            "time_min": self.time_min,
            "condition": self.condition,
            "experiment": self.experiment,
            "sample_name": self.sample_name,
        }
        if self.factors:
            data["factors"] = [asdict(f) for f in self.factors]
        return data

    def required_columns(self) -> list[str]:
        """Return required column names in the input Excel."""
        return [
            self.image_path,
            self.condition,
            self.experiment,
            self.sample_name,
            self.time_min,
        ]

    def trajectory_identifier_columns(self) -> list[str]:
        """Return columns that define a unique trajectory/sequence."""
        return [self.condition, self.experiment, self.sample_name]

    def analysis_factor_columns(self) -> Dict[str, str]:
        """Return mapping of analysis factor names to Excel columns."""
        return {factor.name: factor.column for factor in self.factors}

    def get_factor_column(self, factor_name: str) -> str:
        """Get Excel column name for a factor by its logical name.

        Parameters
        ----------
        factor_name : str
            Logical factor name (e.g., "concentration")

        Returns
        -------
        str
            Excel column name (e.g., "concentration_mm")

        Raises
        ------
        ValueError
            If factor_name not found in factors list
        """
        for factor in self.factors:
            if factor.name == factor_name:
                return factor.column
        raise ValueError(f"Factor '{factor_name}' not defined in config")


@dataclass
class SegmentationConfig:
    """Segmentation pipeline parameters."""

    n_workers: int = 10
    save_debug_images: bool = False
    use_kalman: bool = True
    kalman_Q: Optional[float] = None
    kalman_R_base: Optional[float] = None
    process_missing: bool = True


@dataclass
class AnalysisConfig:
    """Statistical analysis parameters.

    Supports flexible stratification and interaction analysis using factor names
    defined in ColumnMapping.extra_factors.
    """

    control_condition: str = "DMSO"
    statistical_tests: list[str] = field(default_factory=lambda: ["t_test", "mixed_effects"])
    stratify_by: list[str] = field(default_factory=list)
    interaction_factors: list[str] = field(default_factory=list)
    multiple_comparison_correction: str = "bonferroni"
    effect_size_metric: str = "cohens_d"
    random_effects_structure: str = "both"
    alpha: float = 0.05
    output_formats: list[str] = field(default_factory=lambda: ["excel", "json"])


@dataclass
class OutputConfig:
    """Output directory and file structure."""

    base_dir: str
    segmentation_subdir: str = "segmentation"
    verification_subdir: str = "verification"
    analysis_subdir: str = "analysis"
    figures_subdir: str = "figures"

    def get_segmentation_dir(self) -> Path:
        return Path(self.base_dir) / self.segmentation_subdir

    def get_verification_dir(self) -> Path:
        return Path(self.base_dir) / self.verification_subdir

    def get_analysis_dir(self) -> Path:
        return Path(self.base_dir) / self.analysis_subdir

    def get_figures_dir(self) -> Path:
        return Path(self.base_dir) / self.figures_subdir


@dataclass
class PipelineConfig:
    """
    Complete pipeline configuration with validation.

    Load from YAML:
        config = PipelineConfig.from_yaml("config.yaml")
        config.validate(input_excel="experiments.xlsx")
    """

    # Input
    input_excel: str
    columns: ColumnMapping = field(default_factory=ColumnMapping)

    # Pipeline stages
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    output: OutputConfig = field(default_factory=lambda: OutputConfig(base_dir="./results"))

    # Caching and reproducibility
    overwrite_existing: bool = False
    save_config_with_results: bool = True
    verbose: bool = True

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> PipelineConfig:
        """
        Load configuration from YAML file.

        Parameters
        ----------
        config_path : str | Path
            Path to YAML configuration file.

        Returns
        -------
        PipelineConfig
            Validated configuration object.

        Raises
        ------
        FileNotFoundError
            If config file does not exist.
        ValueError
            If YAML is malformed or missing required fields.
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError("Config file is empty")

        # Parse nested structures
        if "columns" in data and isinstance(data["columns"], dict):
            cols_data = data["columns"]
            # Support backward compatibility: exposure -> condition
            if "exposure" in cols_data and "condition" not in cols_data:
                cols_data["condition"] = cols_data.pop("exposure")

            # Convert factors list (if present) to AnalysisFactor objects
            if "factors" in cols_data and isinstance(cols_data["factors"], list):
                cols_data["factors"] = [
                    AnalysisFactor(**f) if isinstance(f, dict) else f
                    for f in cols_data["factors"]
                ]

            # Backward compatibility: convert old extra_factors dict to factors list
            if "extra_factors" in cols_data and cols_data["extra_factors"]:
                old_extra = cols_data.pop("extra_factors")
                # Also handle old cell_line field
                if "cell_line" in cols_data:
                    cell_line_col = cols_data.pop("cell_line")
                    old_extra["cell_line"] = cell_line_col

                new_factors = [
                    AnalysisFactor(name=name, column=col)
                    for name, col in old_extra.items()
                ]
                cols_data["factors"] = new_factors

            data["columns"] = ColumnMapping(**cols_data)
        else:
            data["columns"] = ColumnMapping()

        if "segmentation" in data and isinstance(data["segmentation"], dict):
            data["segmentation"] = SegmentationConfig(**data["segmentation"])
        else:
            data["segmentation"] = SegmentationConfig()

        if "analysis" in data and isinstance(data["analysis"], dict):
            data["analysis"] = AnalysisConfig(**data["analysis"])
        else:
            data["analysis"] = AnalysisConfig()

        if "output" in data and isinstance(data["output"], dict):
            data["output"] = OutputConfig(**data["output"])
        else:
            if "base_dir" not in data:
                raise ValueError("'output.base_dir' is required in config")
            data["output"] = OutputConfig(base_dir=data.pop("base_dir", "./results"))

        return cls(**data)

    def validate(self, input_excel: Optional[str] = None) -> None:
        """
        Validate configuration against input data.

        Parameters
        ----------
        input_excel : str, optional
            Path to input Excel file. If not provided, uses self.input_excel.

        Raises
        ------
        FileNotFoundError
            If input Excel or output directory cannot be created.
        ValueError
            If column names don't match or data types are invalid.
        """
        excel_path = Path(input_excel or self.input_excel)

        # Check input file exists
        if not excel_path.exists():
            raise FileNotFoundError(f"Input Excel not found: {excel_path}")

        # Load and validate columns
        try:
            df = pd.read_excel(excel_path, sheet_name=0, nrows=5)
        except Exception as e:
            raise ValueError(f"Failed to read input Excel: {e}")

        missing_cols = []
        for required_col in self.columns.required_columns():
            if required_col not in df.columns:
                missing_cols.append(required_col)

        if missing_cols:
            available = list(df.columns)
            raise ValueError(
                f"Missing required columns: {missing_cols}\n"
                f"Available columns: {available}\n\n"
                f"Check your config column mappings:\n{self.columns.to_dict()}"
            )

        # Check output directory can be created
        output_dir = Path(self.output.base_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"Cannot create output directory {output_dir}: {e}")

        # Validate control condition exists in data
        if self.analysis.control_condition not in df[self.columns.condition].values:
            available_conditions = list(df[self.columns.condition].unique())
            warnings.warn(
                f"Control condition '{self.analysis.control_condition}' not found in data.\n"
                f"Available conditions: {available_conditions}\n"
                f"This will be caught during analysis, but please verify your config."
            )

        # Validate analysis factor columns exist in data
        missing_factor_cols = []
        for factor in self.columns.factors:
            if factor.column not in df.columns:
                missing_factor_cols.append((factor.name, factor.column))

        if missing_factor_cols:
            raise ValueError(
                f"Missing analysis factor columns:\n"
                + "\n".join([f"  {name} -> {col}" for name, col in missing_factor_cols])
                + f"\nAvailable columns: {list(df.columns)}"
            )

        # Validate stratify_by and interaction_factors reference defined factors
        valid_factor_names = {factor.name for factor in self.columns.factors}
        invalid_stratify = set(self.analysis.stratify_by) - valid_factor_names
        invalid_interact = set(self.analysis.interaction_factors) - valid_factor_names

        if invalid_stratify:
            raise ValueError(
                f"Invalid factors in 'stratify_by': {invalid_stratify}\n"
                f"Valid factors: {valid_factor_names}\n"
                f"Define missing factors in 'columns.factors'"
            )

        if invalid_interact:
            raise ValueError(
                f"Invalid factors in 'interaction_factors': {invalid_interact}\n"
                f"Valid factors: {valid_factor_names}\n"
                f"Define missing factors in 'columns.factors'"
            )

        if self.verbose:
            print(f"[OK] Config validation passed")
            print(f"  Input: {excel_path}")
            print(f"  Samples: {len(df)}")
            print(f"  Output: {output_dir}")

    def to_yaml(self, output_path: str | Path) -> None:
        """
        Save configuration to YAML file for reproducibility.

        Parameters
        ----------
        output_path : str | Path
            Path where to save the YAML config.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert dataclasses to dicts
        data = {
            "input_excel": self.input_excel,
            "columns": asdict(self.columns),
            "segmentation": asdict(self.segmentation),
            "analysis": asdict(self.analysis),
            "output": asdict(self.output),
            "overwrite_existing": self.overwrite_existing,
            "save_config_with_results": self.save_config_with_results,
            "verbose": self.verbose,
        }

        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def __repr__(self) -> str:
        return (
            f"PipelineConfig(\n"
            f"  input: {self.input_excel}\n"
            f"  output: {self.output.base_dir}\n"
            f"  exposures: dynamic\n"
            f"  control: {self.analysis.control_condition}\n"
            f"  workers: {self.segmentation.n_workers}\n"
            f")"
        )
