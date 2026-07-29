"""Export existing Notebook 10 outputs for the static scenario dashboard.

Run from the project root:
    .venv\\Scripts\\python.exe visualizer/scenario_results/export_dashboard_data.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_PATH = (
    PROJECT_ROOT / "data" / "processed" / "learned_carbon" / "scenario_summary.parquet"
)
DEFAULT_MAPS_DIR = PROJECT_ROOT / "data" / "processed" / "learned_carbon" / "scenario_maps"
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "data" / "scenario-results.json"
MAP_COLUMNS = [
    "action",
    "change_intensity",
    "delta_forest",
    "delta_wetland",
    "delta_agriculture",
    "delta_grassland",
]


def _json_value(value: Any) -> Any:
    """Convert pandas and NumPy scalar values into JSON-safe values."""
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _scenario_values(scenario_map: gpd.GeoDataFrame) -> dict[str, dict[str, Any]]:
    missing = sorted(set(["cell_id", *MAP_COLUMNS]).difference(scenario_map.columns))
    if missing:
        raise ValueError(f"scenario map is missing columns: {', '.join(missing)}")

    values: dict[str, dict[str, Any]] = {}
    for row in scenario_map[["cell_id", *MAP_COLUMNS]].itertuples(index=False):
        cell_id = str(row.cell_id)
        values[cell_id] = {
            column: _json_value(getattr(row, column)) for column in MAP_COLUMNS
        }
    return values


def build_dashboard_payload(summary_path: Path, maps_dir: Path) -> dict[str, Any]:
    """Build a compact, shared-geometry payload from Notebook 10 outputs."""
    if not summary_path.exists():
        raise FileNotFoundError(f"scenario summary is missing: {summary_path}")
    if not maps_dir.exists():
        raise FileNotFoundError(f"scenario maps directory is missing: {maps_dir}")

    summary = pd.read_parquet(summary_path)
    if "Selection rule" not in summary.columns:
        raise ValueError("scenario summary is missing column: Selection rule")

    scenarios = {
        str(row["Selection rule"]): {
            column: _json_value(value) for column, value in row.items()
        }
        for _, row in summary.iterrows()
    }
    if not scenarios:
        raise ValueError("scenario summary has no rows")

    maps: dict[str, dict[str, dict[str, Any]]] = {}
    grid: dict[str, Any] | None = None
    expected_cell_ids: set[str] | None = None
    for scenario in scenarios:
        map_path = maps_dir / f"{scenario}.gpkg"
        if not map_path.exists():
            raise FileNotFoundError(f"scenario map is missing: {map_path}")

        scenario_map = gpd.read_file(map_path)
        maps[scenario] = _scenario_values(scenario_map)
        cell_ids = set(maps[scenario])
        if expected_cell_ids is None:
            expected_cell_ids = cell_ids
            grid_gdf = scenario_map[["cell_id", "geometry"]].to_crs("EPSG:4326")
            grid = json.loads(grid_gdf.to_json(drop_id=True))
        elif cell_ids != expected_cell_ids:
            raise ValueError(f"scenario map cell IDs differ for: {scenario}")

    return {"scenarios": scenarios, "grid": grid, "maps": maps}


def write_dashboard_payload(output_path: Path, payload: dict[str, Any]) -> None:
    """Write the dashboard payload with UTF-8 text and compact JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    payload = build_dashboard_payload(DEFAULT_SUMMARY_PATH, DEFAULT_MAPS_DIR)
    write_dashboard_payload(DEFAULT_OUTPUT_PATH, payload)
    print(f"Dashboard data written: {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
