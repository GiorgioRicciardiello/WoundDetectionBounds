"""
Wound Healing Quantification Library

Production-ready, modular API for wound segmentation, analysis, and verification.

Quick Start:
    from library import Pipeline
    from library.config import PipelineConfig

    config = PipelineConfig.from_yaml("config.yaml")
    config.validate()

    pipeline = Pipeline(config)
    results = pipeline.run()
"""

from library.pipeline import Pipeline
from library.config.pipeline_config import PipelineConfig, ColumnMapping

__all__ = [
    "Pipeline",
    "PipelineConfig",
    "ColumnMapping",
]
