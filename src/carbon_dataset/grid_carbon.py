"""Aggregate compartment carbon predictions into operational grid cells."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "cell_id",
    "predicted_tco2_ha_yr",
    "intersect_area_ha",
}


def aggregate_cell_carbon(overlay: pd.DataFrame) -> pd.DataFrame:
    """Area-weight valid compartment predictions into one row per grid cell."""
    missing = sorted(REQUIRED_COLUMNS.difference(overlay.columns))
    if missing:
        raise ValueError(
            f"overlay is missing required columns: {', '.join(missing)}"
        )

    cell_ids = pd.Index(pd.unique(overlay["cell_id"]), name="cell_id")
    prediction = pd.to_numeric(
        overlay["predicted_tco2_ha_yr"], errors="coerce"
    )
    area = pd.to_numeric(overlay["intersect_area_ha"], errors="coerce")
    valid = (
        np.isfinite(prediction.to_numpy(float))
        & np.isfinite(area.to_numpy(float))
        & (area.to_numpy(float) > 0)
    )

    contributions = pd.DataFrame(
        {
            "cell_id": overlay.loc[valid, "cell_id"],
            "predicted_forest_area_ha": area.loc[valid],
            "predicted_tco2_yr": prediction.loc[valid] * area.loc[valid],
        }
    )
    grouped = contributions.groupby("cell_id", sort=False).sum()
    grouped = grouped.reindex(cell_ids, fill_value=0.0)
    grouped["predicted_tco2_ha_yr"] = np.divide(
        grouped["predicted_tco2_yr"],
        grouped["predicted_forest_area_ha"],
        out=np.full(len(grouped), np.nan),
        where=grouped["predicted_forest_area_ha"].to_numpy() > 0,
    )
    return grouped.reset_index()[
        [
            "cell_id",
            "predicted_forest_area_ha",
            "predicted_tco2_ha_yr",
            "predicted_tco2_yr",
        ]
    ]
