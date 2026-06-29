"""Step 04: Process soil/peat data from Estonian WFS services.

Sources:
  - Maa-amet maardlad WFS: peat deposit extents, exploitable/damaged peatland
  - ETAK WFS: wetland/mire polygons (raised bogs, fens, reed beds),
              peat extraction fields

Derives per 1km grid cell:
  - peat_overlap_pct (share of cell covered by peat deposits)
  - wetland_mire_overlap_pct (ETAK wetland polygons)
  - peat_extraction_overlap_pct (damaged peatland / extraction)
  - dominant_wetland_type (Raba/Madalsoo/Roostik/None)
  - peatland_status (natural / exploitable / damaged / none)
  - soil_carbon_relevance_score
  - wetland_restoration_soil_score
  - soil_data_quality_flag

Outputs: data/processed/carbon_v1_5/soil_peat_features.parquet
"""

import io
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from owslib.wfs import WebFeatureService
from shapely.geometry import box

from config import CRS, DATA_PROCESSED_CARBON


# --- WFS endpoints ---
MAARDLAD_WFS_URL = "https://teenus.maaamet.ee/ows/maardlad"
ETAK_WFS_URL = "https://gsavalik.envir.ee/geoserver/etak/ows"

# WFS page size (ETAK has 5000 limit)
PAGE_SIZE = 5000


def fetch_wfs_paged(url: str, typename: str, bbox: tuple,
                    srs: str = "urn:ogc:def:crs:EPSG::3301",
                    output_format: Optional[str] = None,
                    max_pages: int = 20) -> gpd.GeoDataFrame:
    """Fetch features from WFS with paging support.

    Args:
        url: WFS endpoint URL.
        typename: Layer name.
        bbox: (minx, miny, maxx, maxy, srs_uri) or (minx, miny, maxx, maxy).
        srs: SRS for the request.
        output_format: Output format (None = default GML, or 'application/json').
        max_pages: Safety limit on number of pages.

    Returns:
        GeoDataFrame with all features, or empty GeoDataFrame on failure.
    """
    wfs = WebFeatureService(url, version="2.0.0", timeout=60)

    all_gdfs = []
    start_index = 0

    for page in range(max_pages):
        kwargs = {
            "typename": [typename],
            "bbox": bbox,
            "startindex": start_index,
            "maxfeatures": PAGE_SIZE,
        }
        if output_format:
            kwargs["outputFormat"] = output_format

        try:
            resp = wfs.getfeature(**kwargs)
            data = resp.read()

            if len(data) < 100:
                break

            gdf = gpd.read_file(io.BytesIO(data))
            if gdf.empty:
                break

            all_gdfs.append(gdf)
            start_index += len(gdf)

            if len(gdf) < PAGE_SIZE:
                break  # last page
        except Exception as e:
            print(f"    WFS error on page {page}: {e}")
            break

    if not all_gdfs:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)

    result = pd.concat(all_gdfs, ignore_index=True)
    result = gpd.GeoDataFrame(result, geometry="geometry")
    if result.crs is None:
        result = result.set_crs(CRS)
    elif result.crs.to_epsg() != 3301:
        result = result.to_crs(CRS)

    return result


def fetch_peat_deposits(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch peat deposit extent polygons from maardlad WFS."""
    print("  Fetching peat deposits (ms:Turvas_levi)...")
    gdf = fetch_wfs_paged(MAARDLAD_WFS_URL, "ms:Turvas_levi", bbox)
    print(f"    Got {len(gdf)} peat deposit polygons")
    return gdf


def fetch_exploitable_peat(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch exploitable (actively used) peat areas."""
    print("  Fetching exploitable peat (ms:ta_kasutatav)...")
    gdf = fetch_wfs_paged(MAARDLAD_WFS_URL, "ms:ta_kasutatav", bbox)
    print(f"    Got {len(gdf)} exploitable peat areas")
    return gdf


def fetch_damaged_peat(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch damaged/disturbed peatland areas."""
    print("  Fetching damaged peatland (ms:ta_rikutud)...")
    gdf = fetch_wfs_paged(MAARDLAD_WFS_URL, "ms:ta_rikutud", bbox)
    print(f"    Got {len(gdf)} damaged peatland areas")
    return gdf


def fetch_etak_wetlands(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch ETAK wetland/mire polygons (includes type: Raba, Madalsoo, Roostik)."""
    print("  Fetching ETAK wetlands (etak:e_306_margala_a)...")
    gdf = fetch_wfs_paged(ETAK_WFS_URL, "etak:e_306_margala_a", bbox,
                          output_format="application/json")
    print(f"    Got {len(gdf)} wetland polygons")

    # Also fetch the 'ka' variant (reed beds etc)
    print("  Fetching ETAK wetlands (etak:e_306_margala_ka)...")
    gdf_ka = fetch_wfs_paged(ETAK_WFS_URL, "etak:e_306_margala_ka", bbox,
                             output_format="application/json")
    print(f"    Got {len(gdf_ka)} additional wetland polygons")

    if not gdf_ka.empty:
        # Harmonize columns
        common_cols = ["geometry", "tyyp_tekst"]
        for col in common_cols:
            if col not in gdf.columns:
                gdf[col] = None
            if col not in gdf_ka.columns:
                gdf_ka[col] = None
        gdf = pd.concat([
            gdf[["geometry", "tyyp_tekst"]],
            gdf_ka[["geometry", "tyyp_tekst"]]
        ], ignore_index=True)
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=CRS)

    return gdf


def fetch_peat_extraction_fields(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch peat extraction field polygons from ETAK."""
    print("  Fetching peat extraction fields (etak:e_307_turbavali_a)...")
    gdf = fetch_wfs_paged(ETAK_WFS_URL, "etak:e_307_turbavali_a", bbox,
                          output_format="application/json")
    print(f"    Got {len(gdf)} peat extraction fields")
    return gdf


def compute_overlap_pct(grid: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame,
                        col_name: str) -> pd.Series:
    """Compute share of each grid cell covered by polygons.

    Uses geopandas overlay for efficient batch intersection.
    Returns Series indexed same as grid with values 0-1.
    """
    if polygons.empty:
        return pd.Series(0.0, index=grid.index, name=col_name)

    # Use overlay intersection (vectorized, much faster than per-cell loop)
    grid_with_idx = grid[["geometry"]].copy()
    grid_with_idx["_grid_idx"] = grid.index
    grid_with_idx["_cell_area"] = grid.geometry.area

    poly_simple = polygons[["geometry"]].copy()

    try:
        intersected = gpd.overlay(grid_with_idx, poly_simple, how="intersection")
    except Exception:
        # Fallback to spatial-index loop if overlay fails
        return _compute_overlap_fallback(grid, polygons, col_name)

    if intersected.empty:
        return pd.Series(0.0, index=grid.index, name=col_name)

    # Sum intersection areas per grid cell
    intersected["_int_area"] = intersected.geometry.area
    area_per_cell = intersected.groupby("_grid_idx")["_int_area"].sum()

    # Compute overlap percentage
    overlaps = pd.Series(0.0, index=grid.index, name=col_name)
    for idx, int_area in area_per_cell.items():
        cell_area = grid_with_idx.loc[idx, "_cell_area"]
        if cell_area > 0:
            overlaps.loc[idx] = min(int_area / cell_area, 1.0)

    return overlaps.clip(0, 1)


def _compute_overlap_fallback(grid: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame,
                               col_name: str) -> pd.Series:
    """Fallback overlap using spatial index (slower but robust)."""
    sindex = polygons.sindex
    overlaps = np.zeros(len(grid))

    for i, cell_geom in enumerate(grid.geometry):
        cell_area = cell_geom.area
        if cell_area <= 0:
            continue
        candidates_idx = list(sindex.intersection(cell_geom.bounds))
        if not candidates_idx:
            continue
        candidates = polygons.iloc[candidates_idx]
        try:
            clipped = candidates.intersection(cell_geom)
            total_area = clipped.area.sum()
            overlaps[i] = min(total_area / cell_area, 1.0)
        except Exception:
            pass

    return pd.Series(overlaps, index=grid.index, name=col_name).clip(0, 1)


def compute_dominant_wetland_type(grid: gpd.GeoDataFrame,
                                  wetlands: gpd.GeoDataFrame) -> pd.Series:
    """Determine dominant wetland type per cell (Raba/Madalsoo/Roostik/None)."""
    if wetlands.empty or "tyyp_tekst" not in wetlands.columns:
        return pd.Series(None, index=grid.index, name="dominant_wetland_type", dtype="object")

    results = [None] * len(grid)

    # Spatial join to find which wetlands intersect which cells
    joined = gpd.sjoin(wetlands, grid[["geometry"]], how="inner", predicate="intersects")

    if joined.empty:
        return pd.Series(results, index=grid.index, name="dominant_wetland_type")

    # For each cell, find the wetland type with most area
    for cell_idx, group in joined.groupby("index_right"):
        type_areas = {}
        cell_geom = grid.geometry.iloc[cell_idx]
        for _, row in group.iterrows():
            wtype = row.get("tyyp_tekst", "Unknown")
            if wtype is None:
                wtype = "Unknown"
            try:
                area = row.geometry.intersection(cell_geom).area
                type_areas[wtype] = type_areas.get(wtype, 0) + area
            except Exception:
                pass
        if type_areas:
            results[cell_idx] = max(type_areas, key=type_areas.get)

    return pd.Series(results, index=grid.index, name="dominant_wetland_type")


def derive_peatland_status(row: pd.Series) -> str:
    """Classify peatland status for a cell."""
    if row["peat_extraction_overlap_pct"] > 0.1:
        return "damaged"
    if row["exploitable_peat_overlap_pct"] > 0.1:
        return "exploitable"
    if row["peat_overlap_pct"] > 0.1:
        return "natural"
    if row["wetland_mire_overlap_pct"] > 0.2:
        return "wetland_no_peat_data"
    return "none"


def derive_soil_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Derive soil_carbon_relevance_score and wetland_restoration_soil_score."""
    out = df.copy()

    # Soil carbon relevance (from spec Section 4.3)
    out["soil_carbon_relevance_score"] = np.select(
        [
            out["peat_overlap_pct"] > 0.5,
            out["peat_overlap_pct"] > 0.2,
            out["wetland_mire_overlap_pct"] > 0.3,
            out["wetland_mire_overlap_pct"] > 0.1,
            out["peat_overlap_pct"] > 0.0,
        ],
        [1.0, 0.8, 0.7, 0.5, 0.4],
        default=0.1,
    )

    # Wetland restoration soil score — high for damaged peatland
    out["wetland_restoration_soil_score"] = np.select(
        [
            # Damaged peatland = prime restoration candidate
            out["peat_extraction_overlap_pct"] > 0.1,
            # Exploitable peat = could be restored if decommissioned
            out["exploitable_peat_overlap_pct"] > 0.1,
            # Natural peat = already valuable, moderate restoration potential
            (out["peat_overlap_pct"] > 0.3) & (out["peatland_status"] == "natural"),
            # Wetland context without peat data
            out["wetland_mire_overlap_pct"] > 0.2,
        ],
        [0.9, 0.7, 0.5, 0.4],
        default=0.1,
    )

    # Data quality flag
    out["soil_data_quality_flag"] = np.where(
        (out["peat_overlap_pct"] > 0) | (out["wetland_mire_overlap_pct"] > 0),
        "good",
        "no_peat_or_wetland_data"
    )

    return out


def process_soil_peat(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    """Main processing: fetch peat/wetland layers and compute per-cell features."""
    print("Processing soil/peat features...")

    # Get bounding box for WFS queries
    bounds = grid.total_bounds  # minx, miny, maxx, maxy
    bbox = (bounds[0], bounds[1], bounds[2], bounds[3], "urn:ogc:def:crs:EPSG::3301")

    # Fetch all layers
    peat_extent = fetch_peat_deposits(bbox)
    exploitable = fetch_exploitable_peat(bbox)
    damaged = fetch_damaged_peat(bbox)
    wetlands = fetch_etak_wetlands(bbox)
    extraction_fields = fetch_peat_extraction_fields(bbox)

    # Merge damaged peat from maardlad + extraction fields from ETAK
    damaged_all = gpd.GeoDataFrame(geometry=[], crs=CRS)
    parts = []
    if not damaged.empty:
        parts.append(damaged[["geometry"]])
    if not extraction_fields.empty:
        parts.append(extraction_fields[["geometry"]])
    if parts:
        damaged_all = pd.concat(parts, ignore_index=True)
        damaged_all = gpd.GeoDataFrame(damaged_all, geometry="geometry", crs=CRS)

    # Compute overlaps per cell
    print("\n  Computing overlaps...")
    df = pd.DataFrame({"cell_id": grid["cell_id"].values if "cell_id" in grid.columns else range(len(grid))})

    df["peat_overlap_pct"] = compute_overlap_pct(grid, peat_extent, "peat_overlap_pct").values
    print(f"    peat_overlap_pct: {(df['peat_overlap_pct'] > 0).sum()} cells with peat")

    df["exploitable_peat_overlap_pct"] = compute_overlap_pct(grid, exploitable, "exploitable_peat_overlap_pct").values
    df["peat_extraction_overlap_pct"] = compute_overlap_pct(grid, damaged_all, "peat_extraction_overlap_pct").values

    df["wetland_mire_overlap_pct"] = compute_overlap_pct(grid, wetlands, "wetland_mire_overlap_pct").values
    print(f"    wetland_mire_overlap_pct: {(df['wetland_mire_overlap_pct'] > 0).sum()} cells with wetland")

    # Dominant wetland type
    print("  Computing dominant wetland types...")
    df["dominant_wetland_type"] = compute_dominant_wetland_type(grid, wetlands).values

    # Peatland status
    df["peatland_status"] = df.apply(derive_peatland_status, axis=1)

    # Derived scores
    df = derive_soil_scores(df)

    # Summary
    print(f"\n  Results ({len(df)} cells):")
    print(f"    Peatland status distribution:")
    print(f"      {df['peatland_status'].value_counts().to_dict()}")
    print(f"    soil_carbon_relevance_score: mean={df['soil_carbon_relevance_score'].mean():.3f}")
    print(f"    wetland_restoration_soil_score: mean={df['wetland_restoration_soil_score'].mean():.3f}")

    return df


def save_soil_peat_features(df: pd.DataFrame):
    """Save soil/peat features to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "soil_peat_features.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    grid_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    if not grid_path.exists():
        print("Grid not found — run 01_prepare_grid.py first")
        raise SystemExit(1)

    grid = gpd.read_file(grid_path)
    features = process_soil_peat(grid)
    save_soil_peat_features(features)
