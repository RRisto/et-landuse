"""Pure helpers for scenario feasibility and summary reporting."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .optimizer.nsga2 import CONSTRAINT_TOLERANCE

SUMMARY_COLUMNS = [
    "Scenario",
    "Status",
    "Bio (best)",
    "Carbon (best bio)",
    "Cost (best bio)",
    "Changed % (best bio)",
    "Constraint violation (best bio)",
    "Feasible solutions",
    "Front size",
    "Time (s)",
]

REQUIRED_METRIC_COLUMNS = [
    "biodiversity_gain",
    "carbon_gain",
    "cost",
    "changed_pct",
    "constraint_penalty",
]


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


def build_scenario_summary(
    pareto_frames: Mapping[str, pd.DataFrame],
    *,
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
        feasible = annotated.loc[annotated["is_feasible"]]
        if feasible.empty:
            status = "infeasible"
            candidates = annotated.sort_values(
                ["constraint_penalty", "biodiversity_gain"],
                ascending=[True, False],
                na_position="last",
            )
            best = candidates.iloc[0]
        else:
            status = "feasible"
            best = feasible.loc[feasible["biodiversity_gain"].idxmax()]

        rows.append(
            {
                "Scenario": labels.get(scenario_name, scenario_name),
                "Status": status,
                "Bio (best)": best["biodiversity_gain"],
                "Carbon (best bio)": best["carbon_gain"],
                "Cost (best bio)": best["cost"],
                "Changed % (best bio)": best["changed_pct"],
                "Constraint violation (best bio)": best["constraint_penalty"],
                "Feasible solutions": int(annotated["is_feasible"].sum()),
                "Front size": len(annotated),
                "Time (s)": elapsed.get(scenario_name, float("nan")),
            }
        )

    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
