import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point, box

from estonia_landuse.data.load import compute_building_density, compute_road_density


def _grid(cell_ids: list[object]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"cell_id": cell_ids},
        geometry=[box(0, 0, 1000, 1000), box(2000, 0, 3000, 1000)],
        crs="EPSG:3301",
    )


def test_road_density_follows_row_order_for_string_ids() -> None:
    grid = _grid(["cell-b", "cell-a"])
    roads = gpd.GeoDataFrame(
        geometry=[
            LineString([(0, 500), (1000, 500)]),
            LineString([(2000, 500), (2500, 500)]),
        ],
        crs=grid.crs,
    )

    result = compute_road_density(grid, roads)

    np.testing.assert_allclose(result, [1.0, 0.5])


def test_building_density_supports_filtered_integer_ids() -> None:
    grid = _grid([42, 10])
    buildings = gpd.GeoDataFrame(
        geometry=[Point(100, 100), Point(200, 200), Point(2100, 100)],
        crs=grid.crs,
    )

    result = compute_building_density(grid, buildings)

    np.testing.assert_array_equal(result, [2.0, 1.0])


@pytest.mark.parametrize("function_name", ["roads", "buildings"])
def test_density_rejects_duplicate_cell_ids(function_name: str) -> None:
    grid = _grid([7, 7])
    features = gpd.GeoDataFrame(geometry=[], crs=grid.crs)
    function = compute_road_density if function_name == "roads" else compute_building_density

    with pytest.raises(ValueError, match="cell_id.*unique"):
        function(grid, features)
