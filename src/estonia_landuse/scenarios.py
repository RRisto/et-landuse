"""Pure helpers for scenario feasibility and summary reporting."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .optimizer.nsga2 import CONSTRAINT_TOLERANCE

SUMMARY_COLUMNS = [
    "Scenario",
    "Status",
    "Selection rule",
    "Policy ID",
    "Biodiversity gain",
    "Carbon gain",
    "Cost",
    "Changed land",
    "Agriculture loss",
    "Wetland gain",
    "Constraint violation",
    "Feasible solutions",
    "Front size",
    "Time (s)",
]

REQUIRED_METRIC_COLUMNS = [
    "id",
    "biodiversity_gain",
    "carbon_gain",
    "cost",
    "changed_pct",
    "agriculture_loss_pct",
    "wetland_gain_pct",
    "constraint_penalty",
]

SELECTION_RULES = {
    "green_maximum",
    "food_security",
    "low_budget",
    "wetland_priority",
    "balanced",
}


def annotate_feasibility(
    metrics: pd.DataFrame,
    *,
    violation_column: str = "constraint_penalty",
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> pd.DataFrame:
    """Return a copy with machine- and human-readable feasibility columns."""
    if violation_column not in metrics.columns:
        raise ValueError(f"metrics is missing required column: {violation_column}")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    result = metrics.copy()
    violations = pd.to_numeric(result[violation_column], errors="coerce").to_numpy(float)
    feasible = np.isfinite(violations) & (violations <= tolerance)
    result["is_feasible"] = feasible
    result["feasibility"] = np.where(feasible, "feasible", "infeasible")
    return result


def _normalized_loss(values: pd.Series, *, maximize: bool) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    span = numeric.max() - numeric.min()
    if not np.isfinite(span) or span <= 0:
        return pd.Series(0.0, index=values.index)
    if maximize:
        return (numeric.max() - numeric) / span
    return (numeric - numeric.min()) / span


def select_representative(
    metrics: pd.DataFrame,
    rule: str,
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> pd.Series:
    """Select one deterministic feasible policy using a scenario rule."""
    if rule not in SELECTION_RULES:
        raise ValueError(f"unsupported selection rule: {rule}")
    annotated = annotate_feasibility(metrics, tolerance=tolerance)
    candidates = annotated.loc[annotated["is_feasible"]].copy()
    if candidates.empty:
        minimum = annotated["constraint_penalty"].min()
        candidates = annotated.loc[
            annotated["constraint_penalty"] == minimum
        ].copy()

    bio = _normalized_loss(candidates["biodiversity_gain"], maximize=True)
    carbon = _normalized_loss(candidates["carbon_gain"], maximize=True)
    cost = _normalized_loss(candidates["cost"], maximize=False)
    changed = _normalized_loss(candidates["changed_pct"], maximize=False)
    wetland = _normalized_loss(candidates["wetland_gain_pct"], maximize=True)

    if rule == "green_maximum":
        score = bio + carbon
    elif rule == "food_security":
        score = bio
    elif rule == "low_budget":
        score = np.sqrt(bio**2 + carbon**2 + cost**2)
    elif rule == "wetland_priority":
        score = wetland
    else:
        score = np.sqrt(bio**2 + carbon**2 + cost**2 + changed**2)

    candidates["_selection_score"] = score
    ordered = candidates.sort_values(
        ["_selection_score", "cost", "changed_pct", "id"],
        ascending=True,
        kind="stable",
    )
    return ordered.iloc[0].drop(labels="_selection_score")


def select_scenario_representatives(
    pareto_frames: Mapping[str, pd.DataFrame],
    selection_rules: Mapping[str, str],
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> dict[str, pd.Series]:
    """Select one representative for every named scenario."""
    missing = [
        scenario for scenario in pareto_frames if scenario not in selection_rules
    ]
    if missing:
        raise ValueError(
            "missing selection rules for scenarios: " + ", ".join(missing)
        )
    return {
        scenario: select_representative(
            frame,
            selection_rules[scenario],
            tolerance=tolerance,
        )
        for scenario, frame in pareto_frames.items()
    }


def build_scenario_summary(
    pareto_frames: Mapping[str, pd.DataFrame],
    *,
    representatives: Mapping[str, pd.Series],
    selection_rules: Mapping[str, str],
    scenario_labels: Mapping[str, str] | None = None,
    elapsed_seconds: Mapping[str, float] | None = None,
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> pd.DataFrame:
    """Build one stable reporting row per scenario Pareto front."""
    labels = {} if scenario_labels is None else scenario_labels
    elapsed = {} if elapsed_seconds is None else elapsed_seconds
    rows = []

    for scenario_name, frame in pareto_frames.items():
        missing = [column for column in REQUIRED_METRIC_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(
                f"scenario {scenario_name!r} is missing columns: {', '.join(missing)}"
            )
        if frame.empty:
            raise ValueError(f"scenario {scenario_name!r} has an empty Pareto front")

        annotated = annotate_feasibility(frame, tolerance=tolerance)
        if scenario_name not in representatives:
            raise ValueError(
                f"scenario {scenario_name!r} is missing a representative"
            )
        if scenario_name not in selection_rules:
            raise ValueError(
                f"scenario {scenario_name!r} is missing a selection rule"
            )
        representative = representatives[scenario_name]
        status = (
            "feasible"
            if bool(representative["is_feasible"])
            else "infeasible"
        )

        rows.append(
            {
                "Scenario": labels.get(scenario_name, scenario_name),
                "Status": status,
                "Selection rule": selection_rules[scenario_name],
                "Policy ID": int(representative["id"]),
                "Biodiversity gain": representative["biodiversity_gain"],
                "Carbon gain": representative["carbon_gain"],
                "Cost": representative["cost"],
                "Changed land": representative["changed_pct"],
                "Agriculture loss": representative["agriculture_loss_pct"],
                "Wetland gain": representative["wetland_gain_pct"],
                "Constraint violation": representative["constraint_penalty"],
                "Feasible solutions": int(annotated["is_feasible"].sum()),
                "Front size": len(annotated),
                "Time (s)": elapsed.get(scenario_name, float("nan")),
            }
        )

    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
