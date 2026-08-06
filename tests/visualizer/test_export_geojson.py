"""Tests for saved-scenario visualizer exports."""

import importlib.util
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

_MODULE_PATH = Path(__file__).parents[2] / "visualizer" / "export_geojson.py"
_SPEC = importlib.util.spec_from_file_location("export_geojson", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
export_scenario_results = _MODULE.export_scenario_results


def test_export_scenario_results_writes_wgs84_map_and_summary(tmp_path):
    """Removing reprojection or either output write must fail this test."""
    source_dir = tmp_path / "learned_carbon" / "scenario_maps"
    source_dir.mkdir(parents=True)
    gpd.GeoDataFrame(
        {"cell_id": [7], "action": ["afforest"]},
        geometry=[Point(500000, 6500000)],
        crs="EPSG:3301",
    ).to_file(source_dir / "balanced.gpkg", driver="GPKG")
    pd.DataFrame(
        [{"scenario": "balanced", "biodiversity": 0.82, "carbon": 123.0}]
    ).to_parquet(source_dir.parent / "scenario_summary.parquet", index=False)

    output_dir = tmp_path / "visualizer"
    export_scenario_results(source_dir, output_dir)

    exported_map = output_dir / "scenario_maps" / "balanced.geojson"
    assert exported_map.exists()
    exported = gpd.read_file(exported_map)
    assert exported.crs.to_epsg() == 4326
    assert exported.loc[0, "action"] == "afforest"

    assert json.loads((output_dir / "scenario_summary.json").read_text()) == [
        {"scenario": "balanced", "biodiversity": 0.82, "carbon": 123.0}
    ]
