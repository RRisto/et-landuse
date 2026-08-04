"""Statistical summaries for historical optimizer sensitivity experiments."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, t

from .config import GLOBAL_BOUNDS

_MIN_GLOBAL_SAMPLES = 8


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} are missing required columns: {missing}")


def _mean_interval(summary: pd.DataFrame) -> pd.DataFrame:
    critical_values = t.ppf(0.975, summary["n_seeds"] - 1)
    half_width = critical_values * summary["sd"] / np.sqrt(summary["n_seeds"])
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


def select_matched_baseline_runs(
    candidates: pd.DataFrame,
    reference_runs: pd.DataFrame,
    *,
    expected_scenarios: Sequence[str],
    expected_seeds: Sequence[int],
) -> pd.DataFrame:
    """Select one complete baseline cohort matching current code, data, and profile."""
    identity_columns = ["profile", "input_fingerprint", "code_fingerprint"]
    _require_columns(reference_runs, identity_columns, "Reference runs")
    _require_columns(
        candidates,
        ["scenario", "seed", *identity_columns],
        "Baseline candidates",
    )
    identity: dict[str, object] = {}
    for column in identity_columns:
        values = reference_runs[column].dropna().unique()
        if len(values) != 1:
            raise ValueError(
                f"Reference runs must identify exactly one {column}; got {len(values)}"
            )
        identity[column] = values[0]

    scenarios = tuple(str(scenario) for scenario in expected_scenarios)
    seeds = tuple(int(seed) for seed in expected_seeds)
    if not scenarios or not seeds:
        raise ValueError("Expected baseline scenarios and seeds must be non-empty")
    matched = candidates.copy()
    for column, value in identity.items():
        matched = matched.loc[matched[column].eq(value)]
    matched = matched.loc[
        matched["scenario"].astype(str).isin(scenarios)
        & matched["seed"].astype(int).isin(seeds)
    ].copy()
    key_columns = ["scenario", "seed"]
    if matched.duplicated(key_columns).any():
        duplicates = matched.loc[matched.duplicated(key_columns, keep=False), key_columns]
        raise ValueError(
            "Matched cohort contains duplicate baseline execution keys: "
            f"{duplicates.drop_duplicates().to_dict('records')}"
        )
    expected_keys = {(scenario, seed) for scenario in scenarios for seed in seeds}
    actual_keys = set(
        zip(matched["scenario"].astype(str), matched["seed"].astype(int), strict=True)
    )
    missing = sorted(expected_keys.difference(actual_keys))
    if missing:
        raise ValueError(f"Matched cohort is missing baseline execution keys: {missing}")
    scenario_order = {scenario: index for index, scenario in enumerate(scenarios)}
    seed_order = {seed: index for index, seed in enumerate(seeds)}
    matched["_scenario_order"] = matched["scenario"].astype(str).map(scenario_order)
    matched["_seed_order"] = matched["seed"].astype(int).map(seed_order)
    return (
        matched.sort_values(["_scenario_order", "_seed_order"])
        .drop(columns=["_scenario_order", "_seed_order"])
        .reset_index(drop=True)
    )


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


def summarize_interaction_noise(
    interaction_runs: pd.DataFrame,
    baseline_runs: pd.DataFrame,
    outcomes: Sequence[str],
) -> pd.DataFrame:
    """Compare tested interaction residual magnitude with matched baseline noise."""
    _require_columns(
        interaction_runs,
        [
            "scenario",
            "parameter_x",
            "parameter_y",
            "value_x",
            "value_y",
            *outcomes,
        ],
        "Interaction runs",
    )
    _require_columns(baseline_runs, ["scenario", *outcomes], "Baseline runs")
    rows: list[dict[str, object]] = []
    for (scenario, parameter_x, parameter_y), group in interaction_runs.groupby(
        ["scenario", "parameter_x", "parameter_y"], sort=False
    ):
        for outcome in outcomes:
            surface = estimate_interaction_surface(group, outcome)
            absolute_residuals = surface["interaction_residual"].abs()
            maximum = float(absolute_residuals.max())
            rms = float(np.sqrt(np.mean(np.square(surface["interaction_residual"]))))
            baseline_values = baseline_runs.loc[
                baseline_runs["scenario"].eq(scenario), outcome
            ]
            if baseline_values.count() < 2:
                raise ValueError(
                    f"Interaction noise comparison requires at least two matched "
                    f"baseline seeds for {scenario}/{outcome}"
                )
            baseline_sd = float(baseline_values.std())
            rows.append(
                {
                    "scenario": scenario,
                    "parameter_x": parameter_x,
                    "parameter_y": parameter_y,
                    "outcome": outcome,
                    "max_abs_interaction_residual": maximum,
                    "rms_interaction_residual": rms,
                    "baseline_sd": baseline_sd,
                    "max_abs_residual_to_noise": _effect_to_noise(maximum, baseline_sd),
                    "rms_residual_to_noise": _effect_to_noise(rms, baseline_sd),
                }
            )
    return pd.DataFrame(rows)


def _effect_to_noise(effect: float, noise: float) -> float:
    if noise != 0.0:
        return effect / noise
    return 0.0 if effect == 0.0 else np.inf
