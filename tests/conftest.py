import pandas as pd
import pytest


@pytest.fixture
def minimal_context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cell_id": [1],
            "forest_pct": [0.4],
            "wetland_pct": [0.1],
            "agriculture_pct": [0.3],
            "grassland_pct": [0.1],
            "urban_pct": [0.05],
            "water_pct": [0.05],
            "wetland_suitability": [0.5],
            "protected_overlap_pct": [0.0],
            "opportunity_cost_proxy": [0.2],
        }
    )
