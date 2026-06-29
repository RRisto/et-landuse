"""Step 02: Process CORINE raster into carbon-relevant features per grid cell.

Reads the CORINE 2018 100m raster and computes per 1km cell:
- dominant CLC class and label
- land-use group proportions (forest_share, wetland_share, etc.)
- carbon lookup scores, naturalness, afforestation/wetland suitability

Outputs: data/processed/carbon_v1_5/corine_features.parquet
"""

from collections import Counter

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping

from config import (
    AFFORESTATION_BASE_SUITABILITY,
    ALL_GROUPS,
    CORINE_PIXEL_TO_CODE,
    CORINE_TO_GROUP,
    CORINE_TIF,
    DATA_PROCESSED_CARBON,
    LAND_COVER_CARBON_LOOKUP,
    NATURALNESS_LOOKUP,
    SOIL_PEAT_RELEVANCE_FALLBACK,
    WETLAND_BASE_SUITABILITY,
)


# CLC code -> human-readable label (level 1 simplified)
CLC_LABELS = {
    111: "Continuous urban fabric", 112: "Discontinuous urban fabric",
    121: "Industrial/commercial", 122: "Road/rail networks",
    123: "Port areas", 124: "Airports",
    131: "Mineral extraction", 132: "Dump sites", 133: "Construction sites",
    141: "Green urban areas", 142: "Sport/leisure",
    211: "Non-irrigated arable", 212: "Permanently irrigated", 213: "Rice fields",
    221: "Vineyards", 222: "Fruit trees/berry", 223: "Olive groves",
    231: "Pastures", 241: "Annual+permanent crops", 242: "Complex cultivation",
    243: "Agriculture+natural", 244: "Agro-forestry",
    311: "Broad-leaved forest", 312: "Coniferous forest", 313: "Mixed forest",
    321: "Natural grassland", 322: "Moors/heathland", 323: "Sclerophyllous vegetation",
    324: "Transitional woodland-shrub",
    331: "Beaches/dunes/sand", 332: "Bare rock", 333: "Sparsely vegetated",
    334: "Burnt areas", 335: "Glaciers/perpetual snow",
    411: "Inland marshes", 412: "Peat bogs",
    421: "Salt marshes", 422: "Salines", 423: "Intertidal flats",
    511: "Water courses", 512: "Water bodies",
    521: "Coastal lagoons", 522: "Estuaries", 523: "Sea/ocean",
}


def process_corine(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    """Extract CORINE-derived carbon features for each grid cell.

    Returns a DataFrame indexed by cell_id with all CORINE-derived columns.
    """
    print(f"Opening CORINE raster: {CORINE_TIF}")
    records = []

    with rasterio.open(str(CORINE_TIF)) as src:
        grid_reproj = grid.to_crs(src.crs)

        for idx, row in grid_reproj.iterrows():
            cell_id = grid.loc[idx, "cell_id"] if "cell_id" in grid.columns else idx
            rec = _extract_cell(src, row.geometry, cell_id)
            records.append(rec)

    df = pd.DataFrame(records)
    print(f"Processed {len(df)} cells")

    # Quality checks
    _validate(df)

    return df


def _extract_cell(src, geom, cell_id: int) -> dict:
    """Extract CORINE features for a single grid cell."""
    rec = {"cell_id": cell_id}

    try:
        out_image, _ = rio_mask(src, [mapping(geom)], crop=True, nodata=0)
        pixels = out_image[0]
        valid = pixels[pixels > 0]
    except Exception:
        valid = np.array([])

    if len(valid) == 0:
        rec["dominant_clc_code"] = None
        rec["dominant_clc_label"] = None
        rec["dominant_clc_share"] = 0.0
        rec["clc_group"] = None
        for g in ALL_GROUPS:
            rec[f"{g}_share"] = 0.0
        rec["land_cover_carbon_lookup_score"] = 0.0
        rec["naturalness_score"] = 0.0
        rec["afforestation_base_suitability"] = 0.0
        rec["wetland_base_suitability"] = 0.0
        rec["urban_or_water_constraint"] = True
        return rec

    # Count pixel classes
    counts = Counter(valid.tolist())
    total_pixels = sum(counts.values())

    # Dominant class
    dominant_pixel = counts.most_common(1)[0][0]
    dominant_code = CORINE_PIXEL_TO_CODE.get(int(dominant_pixel), int(dominant_pixel))
    dominant_share = counts[dominant_pixel] / total_pixels

    rec["dominant_clc_code"] = dominant_code
    rec["dominant_clc_label"] = CLC_LABELS.get(dominant_code, f"CLC_{dominant_code}")
    rec["dominant_clc_share"] = round(dominant_share, 4)
    rec["clc_group"] = CORINE_TO_GROUP.get(dominant_code, "other_natural")

    # Group proportions
    group_counts = Counter()
    for val, cnt in counts.items():
        clc_code = CORINE_PIXEL_TO_CODE.get(int(val), int(val))
        group = CORINE_TO_GROUP.get(clc_code, "other_natural")
        group_counts[group] += cnt

    for g in ALL_GROUPS:
        rec[f"{g}_share"] = round(group_counts.get(g, 0) / total_pixels, 4)

    # Derived scores (weighted by group shares)
    land_share = 1.0 - rec["water_share"]
    if land_share > 0:
        rec["land_cover_carbon_lookup_score"] = round(sum(
            rec[f"{g}_share"] * LAND_COVER_CARBON_LOOKUP[g]
            for g in ALL_GROUPS if g != "water"
        ) / land_share, 4)

        rec["naturalness_score"] = round(sum(
            rec[f"{g}_share"] * NATURALNESS_LOOKUP[g]
            for g in ALL_GROUPS if g != "water"
        ) / land_share, 4)

        rec["afforestation_base_suitability"] = round(sum(
            rec[f"{g}_share"] * AFFORESTATION_BASE_SUITABILITY[g]
            for g in ALL_GROUPS if g != "water"
        ) / land_share, 4)

        rec["wetland_base_suitability"] = round(sum(
            rec[f"{g}_share"] * WETLAND_BASE_SUITABILITY[g]
            for g in ALL_GROUPS if g != "water"
        ) / land_share, 4)
    else:
        rec["land_cover_carbon_lookup_score"] = 0.0
        rec["naturalness_score"] = 0.0
        rec["afforestation_base_suitability"] = 0.0
        rec["wetland_base_suitability"] = 0.0

    # Constraint flag
    rec["urban_or_water_constraint"] = (rec["urban_share"] + rec["water_share"]) > 0.5

    return rec


def _validate(df: pd.DataFrame):
    """Run quality checks on CORINE features."""
    n_null_dom = df["dominant_clc_code"].isna().sum()
    if n_null_dom > 0:
        print(f"  WARNING: {n_null_dom} cells have no dominant CLC code (nodata/empty)")

    # Check shares sum ~ 1
    share_cols = [f"{g}_share" for g in ALL_GROUPS]
    share_sums = df[share_cols].sum(axis=1)
    bad_sums = ((share_sums < 0.95) | (share_sums > 1.05)).sum()
    if bad_sums > 0:
        print(f"  WARNING: {bad_sums} cells have group shares not summing to ~1.0")

    n_urban = (df["urban_or_water_constraint"]).sum()
    print(f"  Stats: {n_urban} urban/water-constrained cells, "
          f"{(~df['urban_or_water_constraint']).sum()} actionable cells")


def save_corine_features(df: pd.DataFrame):
    """Save CORINE features to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "corine_features.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    grid_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    if not grid_path.exists():
        print("Grid not found — run 01_prepare_grid.py first")
        raise SystemExit(1)

    grid = gpd.read_file(grid_path)
    features = process_corine(grid)
    save_corine_features(features)
