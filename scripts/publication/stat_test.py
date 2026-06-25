import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.integrate import trapezoid
from typing import Dict, Any

def analyze_migration_dynamics(
    df: pd.DataFrame,
    distance_col: str = "distance_mean",
    time_col: str = "t",
    id_col: str = "identifier",
    treatment_col: str = "sample_condition",
    cellline_col: str = "cell_line",
) -> Dict[str, Any]:
    """
    Perform full migration analysis:
        - Mixed effects model
        - Per-trajectory slope
        - Per-trajectory AUC
        - Group comparisons
        - Effect sizes
        - p-values
        - Sample counts

    Returns dictionary with:
        model_summary
        slope_table
        auc_table
        slope_stats
        auc_stats
    """

    df = df.copy()

    # ---------------------------------------------------
    # Ensure categorical variables
    # ---------------------------------------------------
    df[treatment_col] = df[treatment_col].astype("category")
    df[cellline_col] = df[cellline_col].astype("category")

    # ---------------------------------------------------
    # 1️⃣ Mixed Effects Model
    # Drop factors with only one level to avoid singular design matrices.
    # ---------------------------------------------------
    n_treatments = df[treatment_col].nunique()
    n_celllines  = df[cellline_col].nunique()

    if n_celllines > 1 and n_treatments > 1:
        formula = (
            f"{distance_col} ~ {time_col} * {treatment_col} * {cellline_col}"
        )
    elif n_celllines == 1 and n_treatments > 1:
        formula = f"{distance_col} ~ {time_col} * {treatment_col}"
    elif n_celllines > 1 and n_treatments == 1:
        formula = f"{distance_col} ~ {time_col} * {cellline_col}"
    else:
        formula = f"{distance_col} ~ {time_col}"

    model = smf.mixedlm(
        formula=formula,
        data=df,
        groups=df[id_col],
        re_formula=f"~{time_col}",
    )

    # NOTE: the default "lbfgs" optimizer fails to converge on the random-slope
    # (re_formula="~t") specification for this cohort (Hessian not positive
    # definite), which silently inflates the time-effect SE and collapses its
    # p-value. "bfgs"/"cg"/"powell" all converge cleanly and agree to 4 d.p.;
    # we pass a ladder so statsmodels falls through to the first that converges.
    mixed_result = model.fit(method=["bfgs", "cg", "powell", "lbfgs"])

    model_summary = {
        "params": mixed_result.params,
        "pvalues": mixed_result.pvalues,
        "conf_int": mixed_result.conf_int(),
        "n_obs": mixed_result.nobs,
        "n_groups": df[id_col].nunique(),
        "aic": mixed_result.aic,
        "bic": mixed_result.bic,
    }

    # ---------------------------------------------------
    # 2️⃣ Compute slope per trajectory
    # ---------------------------------------------------
    slope_records = []

    for ident, subdf in df.groupby(id_col):
        if len(subdf) < 2:
            continue

        coef = np.polyfit(
            subdf[time_col],
            subdf[distance_col],
            1,
        )[0]

        slope_records.append({
            id_col: ident,
            "slope": coef,
            treatment_col: subdf[treatment_col].iloc[0],
            cellline_col: subdf[cellline_col].iloc[0],
        })

    slope_df = pd.DataFrame(slope_records)

    # ---------------------------------------------------
    # 3️⃣ Compute AUC per trajectory
    # ---------------------------------------------------
    auc_records = []

    for ident, subdf in df.groupby(id_col):
        subdf = subdf.sort_values(time_col)

        auc = trapezoid(
            y=subdf[distance_col],
            x=subdf[time_col],
        )

        auc_records.append({
            id_col: ident,
            "auc": auc,
            treatment_col: subdf[treatment_col].iloc[0],
            cellline_col: subdf[cellline_col].iloc[0],
        })

    auc_df = pd.DataFrame(auc_records)

    # ---------------------------------------------------
    # 4️⃣ Group statistics (slope + AUC)
    # ---------------------------------------------------
    def compute_group_stats(metric_df, metric_name):

        grouped = (
            metric_df
            .groupby([treatment_col, cellline_col], observed=True)[metric_name]
            .agg(["mean", "std", "count"])
            .reset_index()
        )

        grouped["sem"] = grouped["std"] / np.sqrt(grouped["count"])

        return grouped

    slope_stats = compute_group_stats(slope_df, "slope")
    auc_stats = compute_group_stats(auc_df, "auc")

    # ---------------------------------------------------
    # 5️⃣ Effect size vs control (DMSO)
    # ---------------------------------------------------
    def compute_effect_size(stats_df, metric_name):

        control = stats_df[stats_df[treatment_col] == "DMSO"]

        effect_records = []

        for _, row in stats_df.iterrows():

            if row[treatment_col] == "DMSO":
                continue

            ctrl_row = control[
                control[cellline_col] == row[cellline_col]
            ]

            if ctrl_row.empty:
                continue

            ctrl_mean = ctrl_row["mean"].values[0]
            effect = row["mean"] - ctrl_mean

            effect_records.append({
                treatment_col: row[treatment_col],
                cellline_col: row[cellline_col],
                "effect_size": effect,
                "control_mean": ctrl_mean,
                "treated_mean": row["mean"],
            })

        return pd.DataFrame(effect_records)

    slope_effects = compute_effect_size(slope_stats, "slope")
    auc_effects = compute_effect_size(auc_stats, "auc")

    # ---------------------------------------------------
    # Final output
    # ---------------------------------------------------
    return {
        "mixed_model": model_summary,
        "slope_table": slope_df,
        "auc_table": auc_df,
        "slope_stats": slope_stats,
        "auc_stats": auc_stats,
        "slope_effects": slope_effects,
        "auc_effects": auc_effects,
    }

# %%
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
import statsmodels.api as sm
from scipy import stats
from typing import Dict, Any


def analyze_final_timepoint(
    df: pd.DataFrame,
    distance_col: str = "distance_mean",
    time_col: str = "t",
    id_col: str = "identifier",
    treatment_col: str = "sample_condition",
    cellline_col: str = "cell_line",
) -> Dict[str, Any]:
    """
    Analyze final timepoint distance only.

    Returns:
        - anova_table
        - model_params
        - group_stats
        - effect_sizes_vs_DMSO
        - final_df (per trajectory final values)
    """

    df = df.copy()

    # --------------------------------------------------
    # 1️⃣ Extract final timepoint per trajectory
    # --------------------------------------------------
    final_df = (
        df.sort_values(time_col)
          .groupby(id_col)
          .tail(1)
          .reset_index(drop=True)
    )

    final_df[treatment_col] = final_df[treatment_col].astype("category")
    final_df[cellline_col] = final_df[cellline_col].astype("category")

    # --------------------------------------------------
    # 2️⃣ Fit linear model
    # Drop factors with only one level: a constant factor produces a
    # singular design matrix and makes anova_lm raise a constraint error.
    # --------------------------------------------------
    n_treatments = final_df[treatment_col].nunique()
    n_celllines = final_df[cellline_col].nunique()

    if n_celllines > 1 and n_treatments > 1:
        formula = f"{distance_col} ~ {treatment_col} * {cellline_col}"
    elif n_celllines == 1 and n_treatments > 1:
        formula = f"{distance_col} ~ {treatment_col}"
    elif n_celllines > 1 and n_treatments == 1:
        formula = f"{distance_col} ~ {cellline_col}"
    else:
        # Single group: intercept-only model, no ANOVA possible
        formula = f"{distance_col} ~ 1"

    model = smf.ols(formula, data=final_df).fit()

    anova_table = sm.stats.anova_lm(model, typ=2)

    # --------------------------------------------------
    # 3️⃣ Group summary stats
    # --------------------------------------------------
    group_stats = (
        final_df
        .groupby([treatment_col, cellline_col], observed=True)[distance_col]
        .agg(["mean", "std", "count"])
        .reset_index()
    )

    group_stats["sem"] = group_stats["std"] / np.sqrt(group_stats["count"])

    # --------------------------------------------------
    # 4️⃣ Effect sizes vs DMSO (within cell line)
    # --------------------------------------------------
    effect_records = []

    for cl in final_df[cellline_col].unique():

        df_cl = final_df[final_df[cellline_col] == cl]

        control = df_cl[df_cl[treatment_col] == "DMSO"]

        if control.empty:
            continue

        control_vals = control[distance_col]
        control_mean = control_vals.mean()
        control_std = control_vals.std()
        n_control = len(control_vals)

        for tr in df_cl[treatment_col].unique():

            if tr == "DMSO":
                continue

            treated = df_cl[df_cl[treatment_col] == tr]
            treated_vals = treated[distance_col]

            if treated.empty:
                continue

            treated_mean = treated_vals.mean()
            treated_std = treated_vals.std()
            n_treated = len(treated_vals)

            # Cohen's d
            pooled_sd = np.sqrt(
                ((n_control - 1) * control_std**2 +
                 (n_treated - 1) * treated_std**2)
                / (n_control + n_treated - 2)
            )

            cohens_d = (treated_mean - control_mean) / pooled_sd

            # t-test
            t_stat, p_val = stats.ttest_ind(
                treated_vals,
                control_vals,
                equal_var=False,
            )

            effect_records.append({
                "cell_line": cl,
                "treatment": tr,
                "control_mean": control_mean,
                "treated_mean": treated_mean,
                "mean_difference": treated_mean - control_mean,
                "cohens_d": cohens_d,
                "p_value": p_val,
                "n_control": n_control,
                "n_treated": n_treated,
            })

    effects_df = pd.DataFrame(effect_records)

    # --------------------------------------------------
    # Output
    # --------------------------------------------------
    return {
        "anova_table": anova_table,
        "model_params": model.summary(),
        "group_stats": group_stats,
        "effect_sizes_vs_DMSO": effects_df,
        "final_df": final_df,
    }


