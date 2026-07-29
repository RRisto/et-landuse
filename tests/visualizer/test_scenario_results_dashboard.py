"""Contract tests for the static Scenario Results dashboard."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "visualizer" / "scenario_results"
EXPORTER_PATH = DASHBOARD_DIR / "export_dashboard_data.py"

SCENARIOS = {
    "balanced",
    "food_security",
    "green_maximum",
    "low_budget",
    "sustainable_agriculture",
    "wetland_priority",
}


def _load_exporter():
    spec = importlib.util.spec_from_file_location("scenario_dashboard_exporter", EXPORTER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_dashboard_payload_contains_summary_and_all_scenario_maps(tmp_path: Path) -> None:
    summary_path = tmp_path / "scenario_summary.parquet"
    maps_dir = tmp_path / "scenario_maps"
    maps_dir.mkdir()
    pd.DataFrame(
        {
            "Selection rule": sorted(SCENARIOS),
            "Policy ID": list(range(len(SCENARIOS))),
            "Cost": [0.1] * len(SCENARIOS),
        }
    ).to_parquet(
        summary_path,
        index=False,
    )

    for scenario in SCENARIOS:
        gdf = gpd.GeoDataFrame(
            {
                "cell_id": [112],
                "action": ["no_change"],
                "change_intensity": [0.0],
                "delta_forest": [0.0],
                "delta_wetland": [0.0],
                "delta_agriculture": [0.0],
                "delta_grassland": [0.0],
            },
            geometry=[box(500_000, 6_500_000, 500_500, 6_500_500)],
            crs="EPSG:3301",
        )
        gdf.to_file(maps_dir / f"{scenario}.gpkg", driver="GPKG")

    payload = _load_exporter().build_dashboard_payload(summary_path, maps_dir)

    assert set(payload["scenarios"]) == SCENARIOS
    assert payload["grid"]["type"] == "FeatureCollection"
    assert payload["maps"]["balanced"]["112"] == {
        "action": "no_change",
        "change_intensity": 0.0,
        "delta_forest": 0.0,
        "delta_wetland": 0.0,
        "delta_agriculture": 0.0,
        "delta_grassland": 0.0,
    }
