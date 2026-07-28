import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

SCRIPT = Path(__file__).parents[2] / "src/carbon_dataset/09_fetch_rohemeeter.py"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("rohemeeter_fetcher", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_query_points_uses_500m_cell_geometry() -> None:
    fetcher = _load_fetcher()
    grid = gpd.GeoDataFrame(
        {"cell_id": [7], "geometry": [box(0, 0, 500, 500)]},
        crs="EPSG:3301",
    )

    points = fetcher.generate_query_points(
        grid,
        water_cells=set(),
        step=200,
        offset=100,
    )

    assert points == [
        ("7_0_0", 7, 100.0, 100.0),
        ("7_0_1", 7, 100.0, 300.0),
        ("7_1_0", 7, 300.0, 100.0),
        ("7_1_1", 7, 300.0, 300.0),
    ]


def test_build_paths_keeps_refresh_outputs_in_selected_directory(tmp_path) -> None:
    fetcher = _load_fetcher()
    grid_path = tmp_path / "grid.gpkg"
    output_dir = tmp_path / "refresh"

    paths = fetcher.build_paths(grid_path, output_dir)

    assert paths.grid == grid_path
    assert paths.progress == output_dir / "rohemeeter_progress.json"
    assert paths.raw == output_dir / "rohemeeter_scores_raw.parquet"
    assert paths.aggregate == output_dir / "rohemeeter_scores.parquet"
