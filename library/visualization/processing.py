from __future__ import annotations

from typing import Iterable, Tuple, Optional, List
import pandas as pd

from library.visualization.utils import (
    compute_fractional_closure,
    compute_closure_rate,
    enforce_smooth_monotonic_curve,
    align_times_within_identifiers,
    add_time_hours,
)


class WoundHealingPipeline:
    """
    Modular wound-healing preprocessing pipeline.

    Each stage can be run independently or chained via `run_all`.
    All methods return a DataFrame to allow flexible composition.
    """

    def __init__(
        self,
        area_col: str = "wound_area",
        corrected_area_col: str = "wound_area_corrected",
        healing_ratio_col: str = "healing_ratio",
        time_col: str = "time_min",
        group_col: str = "identifier",
    ):
        self.area_col = area_col
        self.corrected_area_col = corrected_area_col
        self.healing_ratio_col = healing_ratio_col
        self.time_col = time_col
        self.group_col = group_col

    # ------------------------------------------------------------------
    # Stage 1: enforce smooth monotonic closure
    # ------------------------------------------------------------------
    def smooth_monotonic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce smooth, monotonic wound closure per identifier.
        """
        return enforce_smooth_monotonic_curve(
            df=df,
            area_col=self.area_col,
            time_col=self.time_col,
            group_col=self.group_col,
        )

    # ------------------------------------------------------------------
    # Stage 2: compute healing ratio
    # ------------------------------------------------------------------
    def compute_healing_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute healing ratio from corrected wound area.
        """
        return compute_fractional_closure(
            df=df,
            area_col=self.corrected_area_col,
            time_col=self.time_col,
            group_col=self.group_col,
        )

    # ------------------------------------------------------------------
    # Stage 3: time alignment within identifiers
    # ------------------------------------------------------------------
    def align_time(
        self,
        df: pd.DataFrame,
        value_cols: Tuple[str, ...] = ("wound_area_corrected", "healing_ratio"),
        method: str = "nearest",
    ) -> pd.DataFrame:
        """
        Align timepoints within each identifier.
        """
        return align_times_within_identifiers(
            df=df,
            time_col=self.time_col,
            group_col=self.group_col,
            value_cols=value_cols,
            method=method,
        )

    # ------------------------------------------------------------------
    # Stage 4: add time in hours
    # ------------------------------------------------------------------
    def add_time_hours(
        self,
        df: pd.DataFrame,
        round_to: Optional[float] = 0.5,
    ) -> pd.DataFrame:
        """
        Convert time (minutes) to hours, optionally rounding.
        """
        return add_time_hours(
            df=df,
            time_col=self.time_col,
            round_to=round_to,
        )

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    def run_all(
        self,
        df: pd.DataFrame,
        align_method: str = "nearest",
        value_cols: Tuple[str, ...] = ("wound_area_corrected", "healing_ratio"),
        round_to_hours: Optional[float] = 0.5,
    ) -> pd.DataFrame:
        """
        Run full pipeline end-to-end.
        """
        df = self.smooth_monotonic(df)
        df = self.compute_healing_ratio(df)
        df = self.align_time(df, value_cols=value_cols, method=align_method)
        df = self.add_time_hours(df, round_to=round_to_hours)
        return df

    def run_selection(
        self,
        df: pd.DataFrame,
        steps: List[str],
        align_method: str = "nearest",
        round_to_hours: Optional[float] = 0.5,
    ) -> pd.DataFrame:
        """
        Run selected pipeline stages.

        The function dynamically adapts inputs so that steps can be
        executed independently without assuming previous stages ran.
        """

        # Track which area column is currently valid
        current_area_col = self.area_col

        # --------------------------------------------------------------
        # Stage 1: smooth monotonic
        # --------------------------------------------------------------
        if "smooth_monotonic" in steps:
            print("→ smooth_monotonic")
            df = self.smooth_monotonic(df)
            current_area_col = self.corrected_area_col

        # --------------------------------------------------------------
        # Stage 2: compute healing ratio
        # --------------------------------------------------------------
        if "compute_fractional_closure" in steps:
            print("→ compute_fractional_closure")
            df = compute_fractional_closure(
                df=df,
                area_col=current_area_col,
                time_col=self.time_col,
                group_col=self.group_col,
            )

        # --------------------------------------------------------------
        # Stage 3: align time
        # --------------------------------------------------------------
        if "align_time" in steps:
            print("→ align_time")

            value_cols = []

            if current_area_col in df.columns:
                value_cols.append(current_area_col)

            if self.healing_ratio_col in df.columns:
                value_cols.append(self.healing_ratio_col)

            if not value_cols:
                raise ValueError(
                    "align_time requested but no valid value columns are available."
                )

            df = align_times_within_identifiers(
                df=df,
                time_col=self.time_col,
                group_col=self.group_col,
                value_cols=tuple(value_cols),
                method=align_method,
            )

        # --------------------------------------------------------------
        # Stage 4: add time hours
        # --------------------------------------------------------------
        if "add_time_hours" in steps:
            print("→ add_time_hours")
            df = add_time_hours(
                df=df,
                time_col=self.time_col,
                round_to=round_to_hours,
            )

        return df
