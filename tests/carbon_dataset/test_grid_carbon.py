import numpy as np
import pandas as pd
import pytest

from carbon_dataset.grid_carbon import aggregate_cell_carbon


def test_aggregate_cell_carbon_uses_intersection_area_weights() -> None:
    overlay = pd.DataFrame(
        {
            "cell_id": [1, 1, 2],
            "predicted_tco2_ha_yr": [6.0, 3.0, 6.0],
            "intersect_area_ha": [10.0, 5.0, 2.0],
        }
    )

    result = aggregate_cell_carbon(overlay).set_index("cell_id")

    assert result.loc[1, "predicted_forest_area_ha"] == pytest.approx(15.0)
    assert result.loc[1, "predicted_tco2_yr"] == pytest.approx(75.0)
    assert result.loc[1, "predicted_tco2_ha_yr"] == pytest.approx(5.0)
    assert result.loc[2, "predicted_forest_area_ha"] == pytest.approx(2.0)
    assert result.loc[2, "predicted_tco2_yr"] == pytest.approx(12.0)
    assert result.loc[2, "predicted_tco2_ha_yr"] == pytest.approx(6.0)


def test_aggregate_cell_carbon_excludes_invalid_rows() -> None:
    overlay = pd.DataFrame(
        {
            "cell_id": [1, 1, 2, 2],
            "predicted_tco2_ha_yr": [4.0, np.nan, np.nan, 9.0],
            "intersect_area_ha": [3.0, 7.0, 4.0, 0.0],
        }
    )

    result = aggregate_cell_carbon(overlay).set_index("cell_id")

    assert result.loc[1, "predicted_forest_area_ha"] == pytest.approx(3.0)
    assert result.loc[1, "predicted_tco2_yr"] == pytest.approx(12.0)
    assert result.loc[1, "predicted_tco2_ha_yr"] == pytest.approx(4.0)
    assert result.loc[2, "predicted_forest_area_ha"] == pytest.approx(0.0)
    assert result.loc[2, "predicted_tco2_yr"] == pytest.approx(0.0)
    assert np.isnan(result.loc[2, "predicted_tco2_ha_yr"])


def test_aggregate_cell_carbon_rejects_missing_columns() -> None:
    with pytest.raises(
        ValueError,
        match="overlay is missing required columns: intersect_area_ha",
    ):
        aggregate_cell_carbon(
            pd.DataFrame(
                {
                    "cell_id": [1],
                    "predicted_tco2_ha_yr": [4.0],
                }
            )
        )
