"""Step 07: Export merged carbon features as final dataset.

Merges all layer features into one table and exports as GeoPackage + Parquet.
Also produces a version that can be merged with the V1 features for the simulator.

Outputs:
  data/processed/carbon_v1_5/carbon_features_merged.parquet
  data/processed/carbon_v1_5/carbon_features_merged.gpkg
  data/processed/carbon_v1_5/metadata.yml
"""

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from config import DATA_PROCESSED_CARBON


def export_merged_dataset():
    """Merge all available feature layers and export."""
    grid_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    corine_path = DATA_PROCESSED_CARBON / "corine_features.parquet"
    biomass_path = DATA_PROCESSED_CARBON / "biomass_features.parquet"
    scores_path = DATA_PROCESSED_CARBON / "carbon_scores.parquet"

    if not grid_path.exists():
        print("Grid not found — run pipeline from step 01")
        raise SystemExit(1)

    grid = gpd.read_file(grid_path)
    print(f"Grid: {len(grid)} cells")

    # Merge layers
    merged = grid[["cell_id", "geometry", "area_m2"]].copy()

    if corine_path.exists():
        corine = pd.read_parquet(corine_path)
        merged = merged.merge(corine, on="cell_id", how="left")
        print(f"  + CORINE features ({len(corine.columns)-1} columns)")

    if biomass_path.exists():
        biomass = pd.read_parquet(biomass_path)
        merged = merged.merge(biomass, on="cell_id", how="left")
        print(f"  + Biomass features ({len(biomass.columns)-1} columns)")

    if scores_path.exists():
        scores = pd.read_parquet(scores_path)
        merged = merged.merge(scores, on="cell_id", how="left")
        print(f"  + Carbon scores ({len(scores.columns)-1} columns)")

    print(f"\nFinal dataset: {len(merged)} cells, {len(merged.columns)} columns")

    # Save
    parquet_path = DATA_PROCESSED_CARBON / "carbon_features_merged.parquet"
    merged.drop(columns=["geometry"]).to_parquet(parquet_path, index=False)
    print(f"Saved: {parquet_path}")

    gpkg_path = DATA_PROCESSED_CARBON / "carbon_features_merged.gpkg"
    merged.to_file(gpkg_path, driver="GPKG")
    print(f"Saved: {gpkg_path}")

    # Write metadata
    metadata = {
        "version": "carbon_v1_5",
        "created": datetime.now().isoformat(),
        "n_cells": len(merged),
        "n_columns": len(merged.columns),
        "layers_included": {
            "corine": corine_path.exists(),
            "biomass": biomass_path.exists(),
            "soil_peat": False,  # not yet
            "hydrology": False,  # not yet
        },
        "crs": "EPSG:3301",
        "notes": [
            "Carbon scores use CORINE fallbacks where biomass/soil/hydrology layers are missing.",
            "carbon_model_uncertainty_score reflects data completeness.",
            "This is a proxy dataset — not official carbon accounting.",
        ],
    }
    meta_path = DATA_PROCESSED_CARBON / "metadata.yml"
    with open(meta_path, "w") as f:
        yaml.dump(metadata, f, default_flow_style=False)
    print(f"Saved: {meta_path}")


if __name__ == "__main__":
    export_merged_dataset()
