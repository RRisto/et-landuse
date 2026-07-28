import numpy as np
import pandas as pd
import pytest

from estonia_landuse.simulator.simulator import summarize_policy


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
