"""Statistical summaries for historical optimizer sensitivity experiments."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import GLOBAL_BOUNDS

_MIN_GLOBAL_SAMPLES = 8


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} are missing required columns: {missing}")


def _mean_interval(summary: pd.DataFrame) -> pd.DataFrame:
    half_width = 1.96 * summary["sd"] / np.sqrt(summary["n_seeds"])
    return summary.assign(
        ci95_low=summary["mean"] - half_width,
        ci95_high=summary["mean"] + half_width,
    )


def summarize_baseline(
    runs: pd.DataFrame, outcomes: Sequence[str]
) -> pd.DataFrame:
    """Summarize seed variation with empirical means, SDs, and 95% mean CIs."""
    _require_columns(runs, ["scenario", "seed", *outcomes], "Baseline runs")
    long = runs.melt(
        id_vars=["scenario", "seed"],
        value_vars=list(outcomes),
        var_name="outcome",
        value_name="result",
    )
    summary = (
        long.groupby(["scenario", "outcome"], as_index=False)["result"]
        .agg(mean="mean", sd="std", n_seeds="count")
    )
    if summary.empty or summary["n_seeds"].lt(2).any():
        raise ValueError("Baseline summaries require at least two seeds per scenario and outcome")
    return _mean_interval(summary)


def summarize_oat(
    runs: pd.DataFrame,
    baseline_runs: pd.DataFrame,
    outcomes: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return OAT response curves and ranges relative to baseline seed noise."""
    oat_columns = ["scenario", "parameter", "value", "seed", *outcomes]
    _require_columns(runs, oat_columns, "OAT runs")
    _require_columns(
        baseline_runs, ["scenario", "seed", *outcomes], "Baseline runs"
    )
    long = runs.melt(
        id_vars=["scenario", "parameter", "value", "seed"],
        value_vars=list(outcomes),
        var_name="outcome",
        value_name="result",
    )
    curves = (
        long.groupby(["scenario", "parameter", "value", "outcome"], as_index=False)[
            "result"
        ]
        .agg(mean="mean", sd="std", n_seeds="count")
        .sort_values(["scenario", "parameter", "outcome", "value"], ignore_index=True)
    )
    if curves.empty or curves["n_seeds"].lt(2).any():
        raise ValueError("OAT summaries require at least two seeds per parameter value")
    curves = _mean_interval(curves)

    baseline = summarize_baseline(baseline_runs, outcomes)[
        ["scenario", "outcome", "sd"]
    ].rename(columns={"sd": "baseline_sd"})
    effects = (
        curves.groupby(["scenario", "parameter", "outcome"], as_index=False)["mean"]
        .agg(minimum_mean="min", maximum_mean="max")
        .assign(effect_range=lambda frame: frame["maximum_mean"] - frame["minimum_mean"])
        .merge(baseline, on=["scenario", "outcome"], how="left", validate="many_to_one")
    )
    if effects["baseline_sd"].isna().any():
        raise ValueError("Baseline runs do not cover every OAT scenario and outcome")
    effects["effect_to_noise"] = np.divide(
        effects["effect_range"],
        effects["baseline_sd"],
        out=np.where(effects["effect_range"].eq(0.0), 0.0, np.inf),
        where=effects["baseline_sd"].ne(0.0),
    )
    return curves, effects


def _parameter_sample_means(runs: pd.DataFrame, outcome: str) -> pd.DataFrame:
    parameters = list(GLOBAL_BOUNDS)
    _require_columns(
        runs,
        ["sample_id", *parameters, outcome],
        "Global sensitivity runs",
    )
    group_columns = ["sample_id", *parameters]
    if "scenario" in runs:
        group_columns.insert(0, "scenario")
    return runs.groupby(group_columns, as_index=False)[outcome].mean()


def rank_parameter_importance(
    runs: pd.DataFrame, outcome: str, *, random_state: int = 42
) -> pd.DataFrame:
    """Rank seed-averaged global samples with Spearman and forest importance."""
    if "scenario" in runs and runs["scenario"].nunique() > 1:
        tables: list[pd.DataFrame] = []
        diagnostics: dict[str, float] = {}
        means: list[pd.DataFrame] = []
        for scenario, group in runs.groupby("scenario", sort=False):
            ranked = rank_parameter_importance(group, outcome, random_state=random_state)
            ranked.insert(0, "scenario", scenario)
            diagnostics[str(scenario)] = ranked.attrs["held_out_r2"]
            means.append(ranked.attrs["parameter_sample_means"])
            tables.append(ranked)
        combined = pd.concat(tables, ignore_index=True)
        combined.attrs["held_out_r2_by_scenario"] = diagnostics
        combined.attrs["parameter_sample_means"] = pd.concat(means, ignore_index=True)
        return combined

    means = _parameter_sample_means(runs, outcome)
    if len(means) < _MIN_GLOBAL_SAMPLES:
        raise ValueError(
            f"Global importance requires at least eight parameter samples; got {len(means)}"
        )
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.inspection import permutation_importance
        from sklearn.model_selection import train_test_split
    except ImportError as exc:  # pragma: no cover - exercised only in minimal installs
        raise ImportError(
            "Random-forest importance requires scikit-learn; install the project "
            "with the 'pipeline' or 'all' optional dependency extra"
        ) from exc

    parameters = list(GLOBAL_BOUNDS)
    features = means[parameters]
    targets = means[outcome]
    train_x, test_x, train_y, test_y = train_test_split(
        features, targets, test_size=0.25, random_state=random_state
    )
    forest = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=1,
        random_state=random_state,
        n_jobs=1,
    ).fit(train_x, train_y)
    held_out_r2 = float(forest.score(test_x, test_y))
    permutation = permutation_importance(
        forest,
        test_x,
        test_y,
        n_repeats=20,
        random_state=random_state,
        n_jobs=1,
    )
    ranked = pd.DataFrame(
        {
            "parameter": parameters,
            "spearman_rho": [
                spearmanr(features[parameter], targets).statistic
                for parameter in parameters
            ],
            "random_forest_importance": forest.feature_importances_,
            "permutation_importance_mean": permutation.importances_mean,
            "permutation_importance_sd": permutation.importances_std,
        }
    ).sort_values("permutation_importance_mean", ascending=False, ignore_index=True)
    ranked.attrs["held_out_r2"] = held_out_r2
    ranked.attrs["parameter_sample_means"] = means
    return ranked


def estimate_interaction_surface(
    runs: pd.DataFrame,
    outcome: str,
    parameter_x: str = "value_x",
    parameter_y: str = "value_y",
) -> pd.DataFrame:
    """Remove additive main effects from a seed-averaged two-factor grid."""
    _require_columns(
        runs, [parameter_x, parameter_y, outcome], "Interaction runs"
    )
    surface = (
        runs.groupby([parameter_x, parameter_y], as_index=False)[outcome]
        .agg(mean="mean", sd="std", n_seeds="count")
        .rename(columns={parameter_x: "x", parameter_y: "y"})
        .sort_values(["x", "y"], ignore_index=True)
    )
    expected_cells = surface["x"].nunique() * surface["y"].nunique()
    if surface.empty or len(surface) != expected_cells:
        raise ValueError("Interaction analysis requires a complete two-factor grid")
    if surface["x"].nunique() < 2 or surface["y"].nunique() < 2:
        raise ValueError("Interaction analysis requires at least two levels per factor")

    grand_mean = surface["mean"].mean()
    x_effect = surface.groupby("x")["mean"].mean() - grand_mean
    y_effect = surface.groupby("y")["mean"].mean() - grand_mean
    surface["interaction_residual"] = (
        surface["mean"]
        - grand_mean
        - surface["x"].map(x_effect)
        - surface["y"].map(y_effect)
    )
    return surface[["x", "y", "mean", "sd", "n_seeds", "interaction_residual"]]
