"""Grid generation utilities.

Creates grids at configurable resolution by subdividing the Statistics Estonia
1km grid or generating from scratch within a county boundary.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from .constants import CRS_ESTONIAN, GRID_CELL_SIZE


def subdivide_grid(grid_1km: gpd.GeoDataFrame, cell_size: int = GRID_CELL_SIZE) -> gpd.GeoDataFrame:
    """Subdivide a 1km grid into smaller cells.

    Args:
        grid_1km: Original 1km GeoDataFrame with geometry and TOTAL_24 (population).
        cell_size: Target cell size in meters (default from constants).

    Returns:
        New GeoDataFrame with smaller cells. Population distributed equally
        among sub-cells.
    """
    if cell_size >= 1000:
        # No subdivision needed
        result = grid_1km.copy()
        result["cell_id"] = range(len(result))
        return result

    subdivisions = 1000 // cell_size  # 2 for 500m, 4 for 250m
    n_subcells = subdivisions ** 2    # 4 for 500m, 16 for 250m

    rows = []
    for idx, row in grid_1km.iterrows():
        bounds = row.geometry.bounds  # minx, miny, maxx, maxy
        minx, miny, maxx, maxy = bounds

        # Population per sub-cell (distribute equally)
        pop = row.get("TOTAL_24", 0) or 0
        pop_per_subcell = pop / n_subcells

        for i in range(subdivisions):
            for j in range(subdivisions):
                sub_minx = minx + i * cell_size
                sub_miny = miny + j * cell_size
                sub_maxx = sub_minx + cell_size
                sub_maxy = sub_miny + cell_size

                geom = box(sub_minx, sub_miny, sub_maxx, sub_maxy)
                rows.append({
                    "geometry": geom,
                    "TOTAL_24": pop_per_subcell,
                    "parent_idx": idx,
                })

    result = gpd.GeoDataFrame(rows, crs=CRS_ESTONIAN)
    result["cell_id"] = range(len(result))
    print(f"Subdivided {len(grid_1km)} cells (1km) → {len(result)} cells ({cell_size}m)")
    return result


def generate_grid(boundary: gpd.GeoDataFrame, cell_size: int = GRID_CELL_SIZE) -> gpd.GeoDataFrame:
    """Generate a regular grid within a boundary polygon.

    Args:
        boundary: GeoDataFrame with the area boundary.
        cell_size: Cell size in meters.

    Returns:
        GeoDataFrame of grid cells that intersect the boundary.
    """
    bounds = boundary.total_bounds  # minx, miny, maxx, maxy
    minx, miny, maxx, maxy = bounds

    # Align to grid
    minx = np.floor(minx / cell_size) * cell_size
    miny = np.floor(miny / cell_size) * cell_size

    cols = int(np.ceil((maxx - minx) / cell_size))
    row_count = int(np.ceil((maxy - miny) / cell_size))

    geometries = []
    for i in range(cols):
        for j in range(row_count):
            x0 = minx + i * cell_size
            y0 = miny + j * cell_size
            geometries.append(box(x0, y0, x0 + cell_size, y0 + cell_size))

    grid = gpd.GeoDataFrame({"geometry": geometries}, crs=CRS_ESTONIAN)

    # Keep only cells that intersect the boundary
    boundary_union = boundary.geometry.union_all()
    mask = grid.intersects(boundary_union)
    grid = grid[mask].reset_index(drop=True)
    grid["cell_id"] = range(len(grid))
    grid["TOTAL_24"] = 0  # no population data for generated grid

    print(f"Generated {len(grid)} cells ({cell_size}m) within boundary")
    return grid
