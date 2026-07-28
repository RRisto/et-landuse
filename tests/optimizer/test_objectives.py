import pytest

from estonia_landuse.optimizer.trainer import _objective_metrics

SUMMARY = {
    "biodiversity_gain": 0.4,
    "carbon_gain": 0.3,
    "cost": 0.2,
    "changed_pct": 0.1,
    "wetland_gain_pct": 0.5,
}


def test_default_fourth_objective_minimizes_changed_land() -> None:
    assert _objective_metrics(SUMMARY, None) == (-0.4, -0.3, 0.2, 0.1)


def test_wetland_fourth_objective_maximizes_wetland_gain() -> None:
    config = {"optimization": {"fourth_objective": "wetland_gain_pct"}}

    assert _objective_metrics(SUMMARY, config) == (-0.4, -0.3, 0.2, -0.5)


def test_unsupported_fourth_objective_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported fourth objective"):
        _objective_metrics(
            SUMMARY,
            {"optimization": {"fourth_objective": "forest_gain"}},
        )
