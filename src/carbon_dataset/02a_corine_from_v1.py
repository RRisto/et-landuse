"""Step 02a: Derive CORINE carbon features from existing V1 features.

Instead of re-processing the CORINE raster (which takes ~15 min),
this script derives the spec's carbon-relevant columns from the existing
V1 feature table which already has CORINE group proportions.

Outputs: data/processed/carbon_v1_5/corine_features.parquet
"""

import numpy as np
import pandas as pd

from config import (
    AFFORESTATION_BASE_SUITABILITY,
    ALL_GROUPS,
    DATA_PROCESSED_CARBON,
    LAND_COVER_CARBON_LOOKUP,
    NATURALNESS_LOOKUP,
    WETLAND_BASE_SUITABILITY,
)


# Mapping from V1 column names to spec group names
V1_TO_SPEC_GROUP = {
    "urban_pct": "urban",
    "agriculture_pct": "agriculture",
    "grassland_pct": "grassland",
    "forest_pct": "forest",
    "wetland_pct": "wetland",
    "water_pct": "water",
    "other_natural_pct": "other_natural",
}


def corine_from_v1(v1_features_path: str) -> pd.DataFrame:
    """Derive CORINE carbon features from existing V1 feature table."""
    print(f"Loading V1 features: {v1_features_path}")
    v1 = pd.read_parquet(v1_features_path)
    print(f"  {len(v1)} cells, columns: {list(v1.columns)}")

    df = pd.DataFrame()
    df["cell_id"] = v1["cell_id"] if "cell_id" in v1.columns else range(len(v1))

    # Copy group shares (rename _pct -> _share for spec consistency)
    for v1_col, group in V1_TO_SPEC_GROUP.items():
        if v1_col in v1.columns:
            df[f"{group}_share"] = v1[v1_col].fillna(0)
        else:
            df[f"{group}_share"] = 0.0

    # Dominant CLC group
    share_cols = {g: f"{g}_share" for g in ALL_GROUPS}
    shares = df[[f"{g}_share" for g in ALL_GROUPS]]
    df["clc_group"] = shares.idxmax(axis=1).str.replace("_share", "")

    # Use existing land_cover_class and land_cover_group if available
    if "land_cover_class" in v1.columns:
        df["dominant_clc_code"] = v1["land_cover_class"]
    if "land_cover_group" in v1.columns:
        df["clc_group"] = v1["land_cover_group"]

    # Dominant share
    df["dominant_clc_share"] = shares.max(axis=1)

    # Derived scores (weighted by group shares)
    land_share = 1.0 - df["water_share"]
    land_share_safe = land_share.replace(0, 1)

    df["land_cover_carbon_lookup_score"] = sum(
        df[f"{g}_share"] * LAND_COVER_CARBON_LOOKUP[g]
        for g in ALL_GROUPS if g != "water"
    ) / land_share_safe

    df["naturalness_score"] = sum(
        df[f"{g}_share"] * NATURALNESS_LOOKUP[g]
        for g in ALL_GROUPS if g != "water"
    ) / land_share_safe

    df["afforestation_base_suitability"] = sum(
        df[f"{g}_share"] * AFFORESTATION_BASE_SUITABILITY[g]
        for g in ALL_GROUPS if g != "water"
    ) / land_share_safe

    df["wetland_base_suitability"] = sum(
        df[f"{g}_share"] * WETLAND_BASE_SUITABILITY[g]
        for g in ALL_GROUPS if g != "water"
    ) / land_share_safe

    # Constraint flag
    df["urban_or_water_constraint"] = (df["urban_share"] + df["water_share"]) > 0.5

    # Clip scores to [0, 1]
    for col in ["land_cover_carbon_lookup_score", "naturalness_score",
                "afforestation_base_suitability", "wetland_base_suitability"]:
        df[col] = df[col].clip(0, 1)

    print(f"\nDerived CORINE features for {len(df)} cells:")
    print(f"  land_cover_carbon_lookup_score: mean={df['land_cover_carbon_lookup_score'].mean():.3f}")
    print(f"  naturalness_score: mean={df['naturalness_score'].mean():.3f}")
    print(f"  afforestation_base_suitability: mean={df['afforestation_base_suitability'].mean():.3f}")
    print(f"  wetland_base_suitability: mean={df['wetland_base_suitability'].mean():.3f}")
    print(f"  urban_or_water_constraint: {df['urban_or_water_constraint'].sum()} cells")

    return df


def save_corine_features(df: pd.DataFrame):
    """Save CORINE features to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "corine_features.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    from config import DATA_PROCESSED_CARBON
    from pathlib import Path

    v1_path = Path("data/processed/v1/features_v1.parquet")
    if not v1_path.exists():
        print(f"V1 features not found at {v1_path}")
        raise SystemExit(1)

    features = corine_from_v1(str(v1_path))
    save_corine_features(features)
