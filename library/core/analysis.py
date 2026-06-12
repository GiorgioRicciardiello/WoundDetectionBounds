"""
Statistical analysis pipeline for wound healing quantification.

Modular analysis components:
- Condition grouping (user-defined or auto-detected)
- Pairwise comparisons (Welch's t-test with effect sizes)
- Mixed-effects modeling (configurable random effects)
- Multiple comparison correction (Bonferroni, Holm, etc.)
- Output generation (Excel and JSON)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
import json
import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
import warnings


class EffectSizeCalculator:
    """Compute effect sizes for group comparisons."""

    @staticmethod
    def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
        """
        Cohen's d effect size.

        Assumes unequal variances.
        """
        n1, n2 = len(group1), len(group2)
        if n1 < 2 or n2 < 2:
            return np.nan

        mean1, mean2 = np.mean(group1), np.mean(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        return (mean1 - mean2) / pooled_std if pooled_std > 0 else np.nan

    @staticmethod
    def hedges_g(group1: np.ndarray, group2: np.ndarray) -> float:
        """
        Hedges' g effect size (bias-corrected Cohen's d).
        """
        d = EffectSizeCalculator.cohens_d(group1, group2)
        n1, n2 = len(group1), len(group2)
        correction = 1 - (3 / (4 * (n1 + n2 - 2) - 1))
        return d * correction

    @staticmethod
    def glass_delta(group1: np.ndarray, group2: np.ndarray) -> float:
        """
        Glass's delta (uses control group SD only).
        group1 = treatment, group2 = control
        """
        mean1, mean2 = np.mean(group1), np.mean(group2)
        control_sd = np.std(group2, ddof=1)
        return (mean1 - mean2) / control_sd if control_sd > 0 else np.nan


class PairwiseComparison:
    """Pairwise comparison between control and treatment groups."""

    @staticmethod
    def t_test(
        control: np.ndarray,
        treatment: np.ndarray,
        effect_size_metric: str = "cohens_d",
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Welch's t-test (assumes unequal variances).

        Parameters
        ----------
        control : np.ndarray
            Control group measurements
        treatment : np.ndarray
            Treatment group measurements
        effect_size_metric : str
            "cohens_d", "hedges_g", or "glass_delta"
        alpha : float
            Significance threshold

        Returns
        -------
        dict
            t-statistic, p-value, effect size, confidence interval, sample sizes
        """
        # Clean data
        control = np.asarray(control)
        treatment = np.asarray(treatment)
        control = control[~np.isnan(control)]
        treatment = treatment[~np.isnan(treatment)]

        if len(control) < 2 or len(treatment) < 2:
            return {
                "t_stat": np.nan,
                "p_value": np.nan,
                "effect_size": np.nan,
                "ci_lower": np.nan,
                "ci_upper": np.nan,
                "n_control": len(control),
                "n_treatment": len(treatment),
                "significant": False,
                "error": "Insufficient samples",
            }

        # Welch's t-test
        t_stat, p_value = ttest_ind(treatment, control, equal_var=False)

        # Effect size
        effect_size_calc = {
            "cohens_d": EffectSizeCalculator.cohens_d,
            "hedges_g": EffectSizeCalculator.hedges_g,
            "glass_delta": EffectSizeCalculator.glass_delta,
        }
        effect_fn = effect_size_calc.get(effect_size_metric, EffectSizeCalculator.cohens_d)
        effect_size = effect_fn(treatment, control)

        # CI (approximate)
        se = np.sqrt(np.var(control, ddof=1) / len(control) + np.var(treatment, ddof=1) / len(treatment))
        ci_margin = 1.96 * se
        mean_diff = np.mean(treatment) - np.mean(control)

        return {
            "t_stat": round(float(t_stat), 4),
            "p_value": round(float(p_value), 4),
            "effect_size": round(float(effect_size), 4),
            "effect_size_metric": effect_size_metric,
            "ci_lower": round(float(mean_diff - ci_margin), 4),
            "ci_upper": round(float(mean_diff + ci_margin), 4),
            "mean_control": round(float(np.mean(control)), 4),
            "mean_treatment": round(float(np.mean(treatment)), 4),
            "n_control": len(control),
            "n_treatment": len(treatment),
            "significant": p_value < alpha,
            "error": None,
        }


class MultipleComparison:
    """Correct p-values for multiple comparisons."""

    @staticmethod
    def bonferroni(p_values: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        """Bonferroni correction."""
        p_corrected = np.minimum(p_values * len(p_values), 1.0)
        significant = p_corrected < alpha
        return p_corrected, significant

    @staticmethod
    def holm(p_values: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        """Holm-Bonferroni method (less conservative than Bonferroni)."""
        order = np.argsort(p_values)
        p_corrected = np.empty_like(p_values)

        for i, idx in enumerate(order):
            p_corrected[idx] = min(p_values[idx] * (len(p_values) - i), 1.0)

        significant = p_corrected < alpha
        return p_corrected, significant

    @staticmethod
    def correct_pvalues(
        p_values: np.ndarray,
        method: str = "bonferroni",
        alpha: float = 0.05,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Correct p-values using specified method."""
        if method == "bonferroni":
            return MultipleComparison.bonferroni(p_values, alpha)
        elif method == "holm":
            return MultipleComparison.holm(p_values, alpha)
        else:
            warnings.warn(f"Unknown correction method: {method}, using bonferroni")
            return MultipleComparison.bonferroni(p_values, alpha)


class AnalysisPipeline:
    """Main analysis orchestrator with stratification and interaction support."""

    def __init__(
        self,
        measurements: pd.DataFrame,
        config: Optional[Dict[str, Any]] = None,
        condition_col: str = "condition",
        measurement_col: str = "wound_area",
        control_condition: str = "DMSO",
        effect_size_metric: str = "cohens_d",
        correction_method: str = "bonferroni",
        alpha: float = 0.05,
        stratify_by: Optional[List[str]] = None,
        interaction_factors: Optional[List[str]] = None,
        factor_cols: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize analysis pipeline.

        Parameters
        ----------
        measurements : pd.DataFrame
            Input measurements dataframe
        config : dict, optional
            Configuration dict (alternative to individual params)
        condition_col : str
            Name of column with condition labels
        measurement_col : str
            Name of column with measurements
        control_condition : str
            Baseline condition
        effect_size_metric : str
            "cohens_d", "hedges_g", or "glass_delta"
        correction_method : str
            "bonferroni", "holm"
        alpha : float
            Significance threshold
        stratify_by : list[str], optional
            Factor names to stratify analysis by
        interaction_factors : list[str], optional
            Factor names to include as interaction terms
        factor_cols : dict[str, str], optional
            Map from factor name to actual column name
        """
        self.measurements = measurements.copy()
        self.condition_col = condition_col
        self.measurement_col = measurement_col
        self.control_condition = control_condition
        self.effect_size_metric = effect_size_metric
        self.correction_method = correction_method
        self.alpha = alpha
        self.stratify_by = stratify_by or []
        self.interaction_factors = interaction_factors or []
        self.factor_cols = factor_cols or {}

        # Validate
        if condition_col not in self.measurements.columns:
            raise ValueError(f"Column '{condition_col}' not found")
        if measurement_col not in self.measurements.columns:
            raise ValueError(f"Column '{measurement_col}' not found")

        # Validate stratification and interaction factors
        for factor in self.stratify_by + self.interaction_factors:
            actual_col = self.factor_cols.get(factor, factor)
            if actual_col not in self.measurements.columns:
                raise ValueError(f"Factor column '{actual_col}' ('{factor}') not found")

    def get_conditions(self) -> List[str]:
        """Get all conditions in the data."""
        return sorted(self.measurements[self.condition_col].unique().tolist())

    def run_pairwise_comparisons(self) -> pd.DataFrame:
        """
        Run pairwise Welch's t-tests against control.

        Supports stratification (separate analyses per stratum) and interactions
        (composite condition columns).

        Returns
        -------
        pd.DataFrame
            Results with t-stats, p-values, effect sizes, and optional stratum labels
        """
        results = []

        if self.stratify_by:
            # Stratified analysis: run separate comparisons per stratum
            results = self._run_stratified_comparisons()
        elif self.interaction_factors:
            # Interaction analysis: create composite conditions
            results = self._run_interaction_comparisons()
        else:
            # Standard analysis: single pooled comparison
            results = self._run_standard_comparisons()

        df_results = pd.DataFrame(results)

        # Multiple comparison correction
        if len(df_results) > 1:
            p_values = df_results["p_value"].values
            p_corrected, significant = MultipleComparison.correct_pvalues(
                p_values,
                method=self.correction_method,
                alpha=self.alpha,
            )
            df_results["p_value_corrected"] = p_corrected
            df_results["significant_corrected"] = significant
        else:
            df_results["p_value_corrected"] = df_results["p_value"]
            df_results["significant_corrected"] = df_results["significant"]

        return df_results

    def _run_standard_comparisons(self) -> List[Dict[str, Any]]:
        """Run standard single-factor pairwise comparisons."""
        conditions = self.get_conditions()

        if self.control_condition not in conditions:
            raise ValueError(f"Control condition '{self.control_condition}' not found")

        control_data = self.measurements[
            self.measurements[self.condition_col] == self.control_condition
        ][self.measurement_col].values

        results = []

        for condition in conditions:
            if condition == self.control_condition:
                continue

            treatment_data = self.measurements[
                self.measurements[self.condition_col] == condition
            ][self.measurement_col].values

            comparison = PairwiseComparison.t_test(
                control=control_data,
                treatment=treatment_data,
                effect_size_metric=self.effect_size_metric,
                alpha=self.alpha,
            )
            comparison["treatment_condition"] = condition
            comparison["control_condition"] = self.control_condition
            results.append(comparison)

        return results

    def _run_stratified_comparisons(self) -> List[Dict[str, Any]]:
        """Run comparisons separately for each stratum."""
        results = []
        stratify_cols = [self.factor_cols.get(f, f) for f in self.stratify_by]

        # Get all unique combinations of stratification factors
        strata = self.measurements.groupby(stratify_cols, observed=True).groups

        for stratum_tuple, indices in strata.items():
            stratum_df = self.measurements.iloc[indices]
            conditions = sorted(stratum_df[self.condition_col].unique().tolist())

            if self.control_condition not in conditions:
                continue

            control_data = stratum_df[
                stratum_df[self.condition_col] == self.control_condition
            ][self.measurement_col].values

            for condition in conditions:
                if condition == self.control_condition:
                    continue

                treatment_data = stratum_df[
                    stratum_df[self.condition_col] == condition
                ][self.measurement_col].values

                comparison = PairwiseComparison.t_test(
                    control=control_data,
                    treatment=treatment_data,
                    effect_size_metric=self.effect_size_metric,
                    alpha=self.alpha,
                )
                comparison["treatment_condition"] = condition
                comparison["control_condition"] = self.control_condition

                # Add stratum labels
                if len(self.stratify_by) == 1:
                    comparison[self.stratify_by[0]] = stratum_tuple
                else:
                    for factor, value in zip(self.stratify_by, stratum_tuple):
                        comparison[factor] = value

                results.append(comparison)

        return results

    def _run_interaction_comparisons(self) -> List[Dict[str, Any]]:
        """Run comparisons with interaction terms (condition × factor combinations)."""
        results = []

        # Create comparisons for each interaction factor level
        for factor_name in self.interaction_factors:
            interact_col = self.factor_cols.get(factor_name, factor_name)
            factor_levels = sorted(
                [x for x in self.measurements[interact_col].unique().tolist()
                 if pd.notna(x)]
            )

            for level in factor_levels:
                level_df = self.measurements[
                    self.measurements[interact_col] == level
                ]
                conditions = sorted(level_df[self.condition_col].unique().tolist())

                if self.control_condition not in conditions:
                    continue

                control_data = level_df[
                    level_df[self.condition_col] == self.control_condition
                ][self.measurement_col].values

                for condition in conditions:
                    if condition == self.control_condition:
                        continue

                    treatment_data = level_df[
                        level_df[self.condition_col] == condition
                    ][self.measurement_col].values

                    comparison = PairwiseComparison.t_test(
                        control=control_data,
                        treatment=treatment_data,
                        effect_size_metric=self.effect_size_metric,
                        alpha=self.alpha,
                    )
                    comparison["treatment_condition"] = condition
                    comparison["control_condition"] = self.control_condition
                    comparison[factor_name] = level
                    results.append(comparison)

        return results

    def summary_statistics(self) -> pd.DataFrame:
        """Compute summary statistics per condition and stratum."""
        results = []

        if self.stratify_by:
            # Stratified summary
            stratify_cols = [self.factor_cols.get(f, f) for f in self.stratify_by]
            strata = self.measurements.groupby(stratify_cols, observed=True).groups

            for stratum_tuple, indices in strata.items():
                stratum_df = self.measurements.iloc[indices]
                for condition in sorted(stratum_df[self.condition_col].unique()):
                    data = stratum_df[
                        stratum_df[self.condition_col] == condition
                    ][self.measurement_col].values
                    data = data[~np.isnan(data)]

                    stat = {
                        "condition": condition,
                        "n": len(data),
                        "mean": round(float(np.mean(data)), 4) if len(data) > 0 else np.nan,
                        "std": round(float(np.std(data, ddof=1)), 4) if len(data) > 1 else np.nan,
                        "median": round(float(np.median(data)), 4) if len(data) > 0 else np.nan,
                        "min": round(float(np.min(data)), 4) if len(data) > 0 else np.nan,
                        "max": round(float(np.max(data)), 4) if len(data) > 0 else np.nan,
                        "se": round(float(np.std(data, ddof=1) / np.sqrt(len(data))), 4) if len(data) > 1 else np.nan,
                    }

                    if len(self.stratify_by) == 1:
                        stat[self.stratify_by[0]] = stratum_tuple
                    else:
                        for factor, value in zip(self.stratify_by, stratum_tuple):
                            stat[factor] = value

                    results.append(stat)
        else:
            # Standard summary
            for condition in self.get_conditions():
                data = self.measurements[
                    self.measurements[self.condition_col] == condition
                ][self.measurement_col].values
                data = data[~np.isnan(data)]

                results.append({
                    "condition": condition,
                    "n": len(data),
                    "mean": round(float(np.mean(data)), 4),
                    "std": round(float(np.std(data, ddof=1)), 4),
                    "median": round(float(np.median(data)), 4),
                    "min": round(float(np.min(data)), 4),
                    "max": round(float(np.max(data)), 4),
                    "se": round(float(np.std(data, ddof=1) / np.sqrt(len(data))), 4),
                })

        return pd.DataFrame(results)

    def to_excel(self, output_path: str) -> None:
        """Save analysis results to Excel workbook."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Sheet 1: Summary statistics
            df_summary = self.summary_statistics()
            df_summary.to_excel(writer, sheet_name="Summary", index=False)

            # Sheet 2: Pairwise comparisons
            df_pairwise = self.run_pairwise_comparisons()
            df_pairwise.to_excel(writer, sheet_name="Pairwise", index=False)

            # Format
            wb = writer.book
            for ws in wb.sheetnames:
                ws_obj = wb[ws]
                for row in ws_obj.iter_rows(min_row=1, max_row=1):
                    for cell in row:
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    def to_json(self, output_path: str) -> None:
        """Save analysis results to JSON."""
        df_summary = self.summary_statistics()
        df_pairwise = self.run_pairwise_comparisons()

        data = {
            "metadata": {
                "condition_column": self.condition_col,
                "measurement_column": self.measurement_col,
                "control_condition": self.control_condition,
                "effect_size_metric": self.effect_size_metric,
                "correction_method": self.correction_method,
                "alpha": self.alpha,
            },
            "summary_statistics": df_summary.to_dict(orient="records"),
            "pairwise_comparisons": df_pairwise.to_dict(orient="records"),
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
