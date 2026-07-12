"""Export grid + features as GeoJSON for the visualizer.

Run from project root:
    uv run python visualizer/export_geojson.py
"""
import sys
sys.path.insert(0, "src")

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

from estonia_landuse.data.constants import DATA_PROCESSED, PROJECT_ROOT
from estonia_landuse.data.load import merge_carbon_v15
from estonia_landuse.simulator.config import default_config
from estonia_landuse.simulator.features import derive_features

OUT_PATH = Path(__file__).parent / "grid.geojson"
CARBON_DIR = PROJECT_ROOT / "data" / "processed" / "carbon_v1_5"


def main():
    print("Loading grid...")
    gdf = gpd.read_file(DATA_PROCESSED / "base_grid.gpkg")
    config = default_config()
    gdf = derive_features(gdf, config)
    gdf = merge_carbon_v15(gdf)

    # Load Rohemeeter
    rohemeeter_path = CARBON_DIR / "rohemeeter_scores.parquet"
    if rohemeeter_path.exists():
        rohemeeter = pd.read_parquet(rohemeeter_path)
        gdf = gdf.merge(
            rohemeeter[["cell_id", "rohemeeter_mean"]],
            on="cell_id", how="left"
        )
        gdf["rohemeeter_norm"] = gdf["rohemeeter_mean"].fillna(50) / 100.0
    else:
        gdf["rohemeeter_norm"] = 0.5

    # Load peat overlap
    soil_path = CARBON_DIR / "soil_peat_features.parquet"
    if soil_path.exists():
        soil = pd.read_parquet(soil_path, columns=["cell_id", "peat_overlap_pct"])
        gdf = gdf.merge(soil, on="cell_id", how="left")
        gdf["peat_overlap_pct"] = gdf["peat_overlap_pct"].fillna(0)
    else:
        gdf["peat_overlap_pct"] = 0.0

    # Select columns for export (keep it lean)
    keep_cols = [
        "cell_id", "geometry",
        "forest_pct", "wetland_pct", "agriculture_pct",
        "grassland_pct", "urban_pct", "water_pct",
        "naturalness_score", "wetland_suitability",
        "protected_overlap_pct", "rohemeeter_norm",
        "peat_overlap_pct",
    ]
    keep_cols = [c for c in keep_cols if c in gdf.columns]
    export_gdf = gdf[keep_cols].copy()

    # Round floats to reduce file size
    float_cols = export_gdf.select_dtypes(include=[np.floating]).columns
    for col in float_cols:
        export_gdf[col] = export_gdf[col].round(3)

    # Reproject to WGS84 for Leaflet
    export_gdf = export_gdf.to_crs("EPSG:4326")

    # Simplify geometries slightly to reduce size
    export_gdf["geometry"] = export_gdf["geometry"].simplify(0.001, preserve_topology=True)

    print(f"Exporting {len(export_gdf)} cells to {OUT_PATH}")
    export_gdf.to_file(OUT_PATH, driver="GeoJSON")

    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"Done: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
