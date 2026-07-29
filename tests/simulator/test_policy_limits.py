import numpy as np
import pandas as pd
import pytest

from estonia_landuse.simulator.config import default_config
from estonia_landuse.simulator.simulator import summarize_policy


def test_default_config_prices_agriculture_expansion() -> None:
    assert default_config()["scoring"]["agriculture_gain_cost"] == 0.3


def test_summary_reports_county_agriculture_loss_and_wetland_gain(
    minimal_context: pd.DataFrame,
) -> None:
    agriculture_conversion = np.array([[0.5, 0.1, 0.2, 0.1]])
    wetland_restoration = np.array([[0.3, 0.2, 0.3, 0.1]])

    agriculture = summarize_policy(
        minimal_context,
        agriculture_conversion,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
        },
    )
    wetland = summarize_policy(
        minimal_context,
        wetland_restoration,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
        },
    )

    assert agriculture["agriculture_loss_pct"] == pytest.approx(1.0 / 3.0)
    assert agriculture["wetland_gain_pct"] == pytest.approx(0.0)
    assert wetland["agriculture_loss_pct"] == pytest.approx(0.0)
    assert wetland["wetland_gain_pct"] == pytest.approx(1.0)


def test_policy_limit_excess_adds_to_constraint_penalty(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.5, 0.1, 0.2, 0.1]])
    unrestricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
        },
    )
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 0.05,
            "max_total_agri_loss_pct": 0.10,
        },
    )

    expected = (
        unrestricted["changed_pct"]
        - 0.05
        + unrestricted["agriculture_loss_pct"]
        - 0.10
    )
    assert unrestricted["constraint_penalty"] == pytest.approx(0.0)
    assert restricted["constraint_penalty"] == pytest.approx(expected)


def test_policy_exactly_on_limits_remains_feasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.5, 0.1, 0.2, 0.1]])
    baseline = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
        },
    )
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": baseline["changed_pct"],
            "max_total_agri_loss_pct": baseline["agriculture_loss_pct"],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)


def test_summary_distinguishes_net_and_gross_agriculture_change(
    minimal_context: pd.DataFrame,
) -> None:
    context = pd.concat([minimal_context, minimal_context], ignore_index=True)
    proposal = np.array(
        [
            [0.5, 0.1, 0.2, 0.1],
            [0.2, 0.1, 0.5, 0.1],
        ]
    )

    result = summarize_policy(
        context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )

    assert result["agriculture_loss_pct"] == pytest.approx(0.0)
    assert result["agriculture_gain_pct"] == pytest.approx(1.0 / 6.0)
    assert result["gross_agriculture_loss_pct"] == pytest.approx(1.0 / 6.0)
    assert result["gross_agriculture_gain_pct"] == pytest.approx(1.0 / 3.0)


def test_zero_current_agriculture_has_zero_agriculture_percentages(
    minimal_context: pd.DataFrame,
) -> None:
    context = minimal_context.copy()
    context["forest_pct"] = 0.7
    context["agriculture_pct"] = 0.0
    proposal = np.array([[0.7, 0.1, 0.0, 0.1]])

    result = summarize_policy(
        context,
        proposal,
        {"carbon_model": "flat"},
    )

    assert result["agriculture_loss_pct"] == 0.0
    assert result["agriculture_gain_pct"] == 0.0
    assert result["gross_agriculture_loss_pct"] == 0.0
    assert result["gross_agriculture_gain_pct"] == 0.0


def test_gross_agriculture_gain_increases_cost(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
    }
    free = summarize_policy(
        minimal_context,
        proposal,
        {**base, "scoring": {"agriculture_gain_cost": 0.0}},
    )
    priced = summarize_policy(
        minimal_context,
        proposal,
        {**base, "scoring": {"agriculture_gain_cost": 10.0}},
    )

    assert priced["cost"] - free["cost"] == pytest.approx(2.0)


def test_agriculture_expansion_excess_adds_to_constraint_penalty(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    unrestricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 0.05,
        },
    )

    assert restricted["constraint_penalty"] == pytest.approx(
        unrestricted["agriculture_gain_pct"] - 0.05
    )


def test_policy_exactly_on_agriculture_gain_limit_is_feasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    baseline = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": baseline["agriculture_gain_pct"],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)


def test_gross_agriculture_expansion_excess_is_infeasible(
    minimal_context: pd.DataFrame,
) -> None:
    context = pd.concat([minimal_context, minimal_context], ignore_index=True)
    proposal = np.array(
        [
            [0.5, 0.1, 0.2, 0.1],
            [0.2, 0.1, 0.5, 0.1],
        ]
    )
    result = summarize_policy(
        context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
            "max_gross_agri_gain_pct": 0.15,
        },
    )

    assert result["constraint_penalty"] == pytest.approx(1.0 / 3.0 - 0.15)


def test_policy_exactly_on_gross_agriculture_gain_limit_is_feasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    baseline = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
            "max_gross_agri_gain_pct": 1.0,
        },
    )
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
            "max_gross_agri_gain_pct": baseline[
                "gross_agriculture_gain_pct"
            ],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)


def test_minimum_agriculture_gain_shortfall_is_infeasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
        "max_gross_agri_gain_pct": 1.0,
    }
    baseline = summarize_policy(minimal_context, proposal, base)
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            **base,
            "min_total_agri_gain_pct": (
                baseline["agriculture_gain_pct"] + 0.05
            ),
        },
    )

    assert restricted["constraint_penalty"] == pytest.approx(0.05)


def test_policy_exactly_on_minimum_agriculture_gain_is_feasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
        "max_gross_agri_gain_pct": 1.0,
    }
    baseline = summarize_policy(minimal_context, proposal, base)
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            **base,
            "min_total_agri_gain_pct": baseline["agriculture_gain_pct"],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)


def test_gross_agriculture_loss_excess_is_infeasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.5, 0.1, 0.2, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
        "max_gross_agri_gain_pct": 1.0,
    }
    baseline = summarize_policy(minimal_context, proposal, base)
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            **base,
            "max_gross_agri_loss_pct": (
                baseline["gross_agriculture_loss_pct"] - 0.05
            ),
        },
    )

    assert restricted["constraint_penalty"] == pytest.approx(0.05)


def test_biodiversity_and_carbon_floor_shortfalls_are_infeasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.4, 0.1, 0.3, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
        "max_gross_agri_gain_pct": 1.0,
        "max_gross_agri_loss_pct": 1.0,
    }
    baseline = summarize_policy(minimal_context, proposal, base)
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            **base,
            "min_biodiversity_gain": baseline["biodiversity_gain"] + 0.02,
            "min_carbon_gain": baseline["carbon_gain"] + 0.03,
        },
    )

    assert restricted["constraint_penalty"] == pytest.approx(0.05)
