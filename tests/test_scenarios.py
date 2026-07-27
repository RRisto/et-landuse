import pandas as pd

from estonia_landuse.scenarios import annotate_feasibility, build_scenario_summary


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


def test_scenario_summary_selects_best_biodiversity_from_feasible_rows() -> None:
    frames = {
        "balanced": pd.DataFrame(
            [
                {
                    "biodiversity_gain": 0.9,
                    "carbon_gain": 0.8,
                    "cost": 0.1,
                    "changed_pct": 0.4,
                    "constraint_penalty": 0.2,
                },
                {
                    "biodiversity_gain": 0.7,
                    "carbon_gain": 0.6,
                    "cost": 0.3,
                    "changed_pct": 0.2,
                    "constraint_penalty": 0.0,
                },
            ]
        )
    }

    result = build_scenario_summary(
        frames,
        scenario_labels={"balanced": "Balanced"},
        elapsed_seconds={"balanced": 12.5},
    )

    assert result.to_dict("records") == [
        {
            "Scenario": "Balanced",
            "Status": "feasible",
            "Bio (best)": 0.7,
            "Carbon (best bio)": 0.6,
            "Cost (best bio)": 0.3,
            "Changed % (best bio)": 0.2,
            "Constraint violation (best bio)": 0.0,
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
                    "biodiversity_gain": 0.8,
                    "carbon_gain": 0.2,
                    "cost": 0.1,
                    "changed_pct": 0.3,
                    "constraint_penalty": 0.4,
                },
                {
                    "biodiversity_gain": 0.5,
                    "carbon_gain": 0.4,
                    "cost": 0.2,
                    "changed_pct": 0.1,
                    "constraint_penalty": 0.1,
                },
            ]
        )
    }

    result = build_scenario_summary(frames)

    assert result.loc[0, "Status"] == "infeasible"
    assert result.loc[0, "Bio (best)"] == 0.5
    assert result.loc[0, "Constraint violation (best bio)"] == 0.1
    assert result.loc[0, "Feasible solutions"] == 0
