"""Contracts for comparing seed-42 artifacts with Notebook 10's summary."""

from __future__ import annotations

import pandas as pd

from estonia_landuse.sensitivity.reproduction import compare_reference_summary


def _reference() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Scenario": "Balanced (default)",
                "Status": "feasible",
                "Selection rule": "balanced",
                "Policy ID": 7,
                "Biodiversity gain": 0.125,
                "Carbon gain": 0.25,
                "Cost": 0.375,
                "Changed land": 0.5,
                "Agriculture loss": 0.125,
                "Agriculture gain": 0.0,
                "Gross agriculture loss": 0.25,
                "Gross agriculture gain": 0.125,
                "Wetland gain": 0.0625,
                "Constraint violation": 0.0,
                "Feasible solutions": 8,
                "Front size": 8,
            },
            {
                "Scenario": "Food Security (preserve farmland)",
                "Status": "feasible",
                "Selection rule": "food_security",
                "Policy ID": 3,
                "Biodiversity gain": 0.1,
                "Carbon gain": 0.2,
                "Cost": 0.3,
                "Changed land": 0.4,
                "Agriculture loss": 0.01,
                "Agriculture gain": 0.0,
                "Gross agriculture loss": 0.02,
                "Gross agriculture gain": 0.01,
                "Wetland gain": 0.03,
                "Constraint violation": 0.0,
                "Feasible solutions": 6,
                "Front size": 7,
            },
        ]
    )


def _candidate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scenario": "balanced",
                "feasible": True,
                "selection_rule": "balanced",
                "policy_id": 7,
                "biodiversity_gain": 0.125,
                "carbon_gain": 0.25,
                "cost": 0.375,
                "changed_pct": 0.5,
                "agriculture_loss": 0.125,
                "agriculture_gain": 0.0,
                "gross_agriculture_loss": 0.25,
                "gross_agriculture_gain": 0.125,
                "wetland_gain": 0.0625,
                "constraint_penalty": 0.0,
                "feasible_solutions": 8,
                "front_size": 8,
            },
            {
                "scenario": "food_security",
                "feasible": True,
                "selection_rule": "food_security",
                "policy_id": 3,
                "biodiversity_gain": 0.1,
                "carbon_gain": 0.2,
                "cost": 0.3,
                "changed_pct": 0.4,
                "agriculture_loss": 0.01,
                "agriculture_gain": 0.0,
                "gross_agriculture_loss": 0.02,
                "gross_agriculture_gain": 0.01,
                "wetland_gain": 0.03,
                "constraint_penalty": 0.0,
                "feasible_solutions": 6,
                "front_size": 7,
            },
        ]
    )


def test_exact_summary_match_has_no_mismatches() -> None:
    """Catch a correct seed-42 reproduction being reported as drift."""
    mismatches = compare_reference_summary(_reference(), _candidate())

    assert mismatches.empty
    assert list(mismatches.columns) == [
        "scenario",
        "field",
        "reference",
        "candidate",
        "reason",
    ]


def test_rounding_within_tolerance_is_accepted() -> None:
    """Catch harmless parquet/display rounding failing the reproduction gate."""
    candidate = _candidate()
    candidate.loc[0, "carbon_gain"] += 2e-7
    candidate.loc[1, "constraint_penalty"] = 5e-9

    assert compare_reference_summary(_reference(), candidate).empty


def test_missing_and_unexpected_scenarios_are_both_reported() -> None:
    """Catch comparison stopping after only one side's missing scenario."""
    candidate = _candidate().iloc[[0]].copy()
    unexpected = candidate.iloc[[0]].copy()
    unexpected.loc[:, "scenario"] = "unexpected"
    candidate = pd.concat([candidate, unexpected], ignore_index=True)

    mismatches = compare_reference_summary(_reference(), candidate)

    assert mismatches[["scenario", "field", "reason"]].to_records(index=False).tolist() == [
        ("food_security", "Scenario", "missing_in_candidate"),
        ("unexpected", "Scenario", "missing_in_reference"),
    ]


def test_changed_selection_feasibility_and_all_metrics_are_reported() -> None:
    """Catch the gate returning after its first scientifically material mismatch."""
    candidate = _candidate().iloc[[0]].copy()
    candidate.loc[0, "selection_rule"] = "green_maximum"
    candidate.loc[0, "feasible"] = False
    candidate.loc[0, "carbon_gain"] = 0.5
    candidate.loc[0, "cost"] = 0.75

    mismatches = compare_reference_summary(_reference().iloc[[0]], candidate)

    assert set(mismatches["field"]) == {
        "Status",
        "Selection rule",
        "Carbon gain",
        "Cost",
    }
    assert set(mismatches["reason"]) == {"value_mismatch"}


def test_candidate_may_use_notebook_style_column_names() -> None:
    """Catch the public comparison API unnecessarily requiring runner internals."""
    reference = _reference()

    assert compare_reference_summary(reference, reference.copy()).empty
