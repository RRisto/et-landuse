import pandas as pd
import pytest

from estonia_landuse.scenarios import (
    annotate_feasibility,
    build_scenario_summary,
    select_representative,
    select_scenario_representatives,
)


def _metrics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 10,
                "biodiversity_gain": 0.9,
                "carbon_gain": 0.2,
                "cost": 0.8,
                "changed_pct": 0.3,
                "agriculture_loss_pct": 0.1,
                "wetland_gain_pct": 0.1,
                "constraint_penalty": 0.0,
            },
            {
                "id": 20,
                "biodiversity_gain": 0.5,
                "carbon_gain": 0.9,
                "cost": 0.4,
                "changed_pct": 0.2,
                "agriculture_loss_pct": 0.02,
                "wetland_gain_pct": 0.8,
                "constraint_penalty": 0.0,
            },
            {
                "id": 30,
                "biodiversity_gain": 1.0,
                "carbon_gain": 1.0,
                "cost": 0.1,
                "changed_pct": 0.1,
                "agriculture_loss_pct": 0.5,
                "wetland_gain_pct": 1.0,
                "constraint_penalty": 0.2,
            },
        ]
    )


def test_annotate_feasibility_handles_tolerance_and_nonfinite_values() -> None:
    frame = pd.DataFrame(
        {"constraint_penalty": [0.0, 1e-13, 0.1, float("nan"), float("inf")]}
    )

    result = annotate_feasibility(frame, tolerance=1e-12)

    assert result["is_feasible"].tolist() == [True, True, False, False, False]
    assert result["feasibility"].tolist() == [
        "feasible",
        "feasible",
        "infeasible",
        "infeasible",
        "infeasible",
    ]
    assert "is_feasible" not in frame.columns


@pytest.mark.parametrize(
    ("rule", "expected_id"),
    [
        ("green_maximum", 20),
        ("food_security", 10),
        ("wetland_priority", 20),
    ],
)
def test_representative_rules_use_only_feasible_rows(
    rule: str, expected_id: int
) -> None:
    assert select_representative(_metrics(), rule)["id"] == expected_id


def test_low_budget_and_balanced_select_normalized_knees() -> None:
    frame = _metrics()

    assert select_representative(frame, "low_budget")["id"] == 20
    assert select_representative(frame, "balanced")["id"] == 20


def test_no_feasible_policy_uses_least_violation_then_rule() -> None:
    frame = _metrics()
    frame["constraint_penalty"] = [0.3, 0.1, 0.2]

    selected = select_representative(frame, "food_security")

    assert selected["id"] == 20
    assert not bool(selected["is_feasible"])


def test_ties_use_cost_then_change_then_id() -> None:
    frame = pd.DataFrame(
        [
            {
                "id": 2,
                "biodiversity_gain": 1.0,
                "carbon_gain": 1.0,
                "cost": 0.5,
                "changed_pct": 0.2,
                "agriculture_loss_pct": 0.0,
                "wetland_gain_pct": 0.0,
                "constraint_penalty": 0.0,
            },
            {
                "id": 1,
                "biodiversity_gain": 1.0,
                "carbon_gain": 1.0,
                "cost": 0.5,
                "changed_pct": 0.2,
                "agriculture_loss_pct": 0.0,
                "wetland_gain_pct": 0.0,
                "constraint_penalty": 0.0,
            },
        ]
    )

    assert select_representative(frame, "green_maximum")["id"] == 1


def test_scenario_selection_requires_a_rule_for_every_frame() -> None:
    with pytest.raises(ValueError, match="missing selection rules.*balanced"):
        select_scenario_representatives({"balanced": _metrics()}, {})


def test_scenario_summary_reports_the_preselected_representative() -> None:
    frames = {
        "balanced": pd.DataFrame(
            [
                {
                    "id": 1,
                    "biodiversity_gain": 0.9,
                    "carbon_gain": 0.8,
                    "cost": 0.1,
                    "changed_pct": 0.4,
                    "agriculture_loss_pct": 0.2,
                    "wetland_gain_pct": 0.3,
                    "constraint_penalty": 0.2,
                },
                {
                    "id": 2,
                    "biodiversity_gain": 0.7,
                    "carbon_gain": 0.6,
                    "cost": 0.3,
                    "changed_pct": 0.2,
                    "agriculture_loss_pct": 0.05,
                    "wetland_gain_pct": 0.1,
                    "constraint_penalty": 0.0,
                },
            ]
        )
    }
    representative = pd.Series(
        {
            "id": 2,
            "biodiversity_gain": 0.7,
            "carbon_gain": 0.6,
            "cost": 0.3,
            "changed_pct": 0.2,
            "agriculture_loss_pct": 0.05,
            "wetland_gain_pct": 0.1,
            "constraint_penalty": 0.0,
            "is_feasible": True,
        }
    )

    result = build_scenario_summary(
        frames,
        representatives={"balanced": representative},
        selection_rules={"balanced": "balanced"},
        scenario_labels={"balanced": "Balanced"},
        elapsed_seconds={"balanced": 12.5},
    )

    assert result.to_dict("records") == [
        {
            "Scenario": "Balanced",
            "Status": "feasible",
            "Selection rule": "balanced",
            "Policy ID": 2,
            "Biodiversity gain": 0.7,
            "Carbon gain": 0.6,
            "Cost": 0.3,
            "Changed land": 0.2,
            "Agriculture loss": 0.05,
            "Wetland gain": 0.1,
            "Constraint violation": 0.0,
            "Feasible solutions": 1,
            "Front size": 2,
            "Time (s)": 12.5,
        }
    ]


def test_scenario_summary_reports_front_with_no_feasible_solution() -> None:
    frames = {
        "strict": pd.DataFrame(
            [
                {
                    "id": 1,
                    "biodiversity_gain": 0.8,
                    "carbon_gain": 0.2,
                    "cost": 0.1,
                    "changed_pct": 0.3,
                    "agriculture_loss_pct": 0.4,
                    "wetland_gain_pct": 0.0,
                    "constraint_penalty": 0.4,
                },
                {
                    "id": 2,
                    "biodiversity_gain": 0.5,
                    "carbon_gain": 0.4,
                    "cost": 0.2,
                    "changed_pct": 0.1,
                    "agriculture_loss_pct": 0.1,
                    "wetland_gain_pct": 0.2,
                    "constraint_penalty": 0.1,
                },
            ]
        )
    }
    representative = pd.Series(
        {
            **frames["strict"].iloc[1].to_dict(),
            "is_feasible": False,
        }
    )

    result = build_scenario_summary(
        frames,
        representatives={"strict": representative},
        selection_rules={"strict": "food_security"},
    )

    assert result.loc[0, "Status"] == "infeasible"
    assert result.loc[0, "Policy ID"] == 2
    assert result.loc[0, "Biodiversity gain"] == 0.5
    assert result.loc[0, "Constraint violation"] == 0.1
    assert result.loc[0, "Feasible solutions"] == 0
