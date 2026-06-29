"""Step 01: Prepare the 1km grid for the carbon dataset.

Loads the base grid from V1 processing, ensures EPSG:3301, assigns stable cell_id.
Outputs: data/processed/carbon_v1_5/grid.gpkg
"""

import geopandas as gpd

from config import BASE_GRID_PATH, CRS, DATA_PROCESSED_CARBON


def prepare_grid() -> gpd.GeoDataFrame:
    """Load base grid, ensure CRS and cell_id, save to carbon output folder."""
    print(f"Loading base grid from {BASE_GRID_PATH}")
    grid = gpd.read_file(BASE_GRID_PATH)

    if grid.crs is None or grid.crs.to_epsg() != 3301:
        grid = grid.to_crs(CRS)

    # Ensure stable cell_id
    if "cell_id" not in grid.columns:
        grid["cell_id"] = range(len(grid))

    # Store geometry area
    grid["area_m2"] = grid.geometry.area

    print(f"Grid: {len(grid)} cells, CRS={grid.crs}")

    # Save
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    grid.to_file(out_path, driver="GPKG")
    print(f"Saved: {out_path}")

    return grid


if __name__ == "__main__":
    prepare_grid()
