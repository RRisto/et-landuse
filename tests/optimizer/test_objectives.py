import numpy as np
import pytest

from estonia_landuse.optimizer.trainer import (
    _fourth_progress,
    _objective_metrics,
)

SUMMARY = {
    "biodiversity_gain": 0.4,
    "carbon_gain": 0.3,
    "cost": 0.2,
    "changed_pct": 0.1,
    "agriculture_gain_pct": 0.6,
    "wetland_gain_pct": 0.5,
}


def test_default_fourth_objective_minimizes_changed_land() -> None:
    assert _objective_metrics(SUMMARY, None) == (-0.4, -0.3, 0.2, 0.1)


def test_wetland_fourth_objective_maximizes_wetland_gain() -> None:
    config = {"optimization": {"fourth_objective": "wetland_gain_pct"}}

    assert _objective_metrics(SUMMARY, config) == (-0.4, -0.3, 0.2, -0.5)


def test_agriculture_fourth_objective_maximizes_gain() -> None:
    config = {"optimization": {"fourth_objective": "agriculture_gain_pct"}}

    assert _objective_metrics(SUMMARY, config) == (-0.4, -0.3, 0.2, -0.6)


@pytest.mark.parametrize(
    ("objective", "metric", "expected"),
    [
        ("changed_pct", 0.1, ("change", 0.1)),
        ("wetland_gain_pct", -0.5, ("wetland_gain", 0.5)),
        (
            "agriculture_gain_pct",
            -0.6,
            ("agriculture_gain", 0.6),
        ),
    ],
)
def test_fourth_progress_uses_public_label_and_sign(
    objective: str,
    metric: float,
    expected: tuple[str, float],
) -> None:
    config = {"optimization": {"fourth_objective": objective}}

    assert _fourth_progress(
        np.array([0.0, 0.0, 0.0, metric]),
        config,
    ) == expected


def test_unsupported_fourth_objective_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported fourth objective"):
        _objective_metrics(
            SUMMARY,
            {"optimization": {"fourth_objective": "forest_gain"}},
        )
