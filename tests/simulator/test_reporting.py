import numpy as np
import pandas as pd
import pytest

from estonia_landuse.simulator.config import default_config
from estonia_landuse.simulator.reporting import summarize_policy_reporting


def synthetic_context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "forest_pct": [0.2, 0.2, 0.2],
            "wetland_pct": [0.1, 0.1, 0.3],
            "agriculture_pct": [0.5, 0.4, 0.3],
            "grassland_pct": [0.2, 0.3, 0.2],
            "urban_pct": [0.0, 0.0, 0.0],
            "water_pct": [0.0, 0.0, 0.0],
            "protected_overlap_pct": [0.0, 0.2, 0.0],
            "wetland_suitability": [1.0, 1.0, 1.0],
            "opportunity_cost_proxy": [0.0, 0.0, 0.0],
        }
    )


def test_reporting_summary_includes_constrained_bar_chart_metrics():
    context = synthetic_context()
    targets = np.array(
        [
            [0.3, 0.2, 0.3, 0.2],  # loses agriculture and restores wetland
            [0.6, 0.1, 0.1, 0.2],  # protected: all changes are blocked
            [0.3, 0.1, 0.4, 0.2],  # wetland loss is blocked
        ]
    )

    result = summarize_policy_reporting(context, targets, default_config())

    assert set(result) >= {
        "biodiversity_gain",
        "carbon_gain",
        "cost",
        "changed_pct",
        "agriculture_loss",
        "agriculture_gain",
        "gross_agriculture_gain",
        "wetland_gain",
    }
    current_agriculture = 1.2
    assert result["agriculture_loss"] == pytest.approx(0.2 / current_agriculture)
    assert result["agriculture_gain"] == 0.0
    assert result["gross_agriculture_gain"] == pytest.approx(0.1 / current_agriculture)
    assert result["wetland_gain"] == pytest.approx(0.1 / 3)
