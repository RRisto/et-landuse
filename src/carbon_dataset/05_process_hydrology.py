"""Step 05: Process hydrology data from ETAK WFS.

Sources:
  - ETAK: streams/rivers/ditches (e_203_vooluveekogu_j)
  - ETAK: standing waterbodies (e_202_seisuveekogu_a)
  - DEM: elevation/slope (Copernicus GLO-30 or existing features)

Derives per 1km grid cell:
  - distance_to_water_m
  - distance_to_river_or_stream_m
  - distance_to_ditch_or_drainage_m
  - waterbody_overlap_pct
  - stream_density_1km (km of rivers/streams per cell)
  - ditch_density_1km (km of ditches per cell)
  - elevation_mean, slope_mean (from DEM if available)
  - low_slope_score, lowland_score
  - hydrology_restoration_score

Outputs: data/processed/carbon_v1_5/hydrology_features.parquet
"""

import io

import geopandas as gpd
import numpy as np
import pandas as pd
from owslib.wfs import WebFeatureService
from shapely.ops import nearest_points

from config import CRS, DATA_PROCESSED_CARBON


ETAK_WFS_URL = "https://gsavalik.envir.ee/geoserver/etak/ows"
PAGE_SIZE = 5000


def fetch_wfs_paged_json(typename: str, bbox: tuple, max_pages: int = 50) -> gpd.GeoDataFrame:
    """Fetch features from ETAK WFS with paging (JSON format)."""
    wfs = WebFeatureService(ETAK_WFS_URL, version="2.0.0", timeout=60)
    all_gdfs = []
    start_index = 0

    for page in range(max_pages):
        try:
            resp = wfs.getfeature(
                typename=[typename],
                bbox=bbox,
                startindex=start_index,
                maxfeatures=PAGE_SIZE,
                outputFormat="application/json",
            )
            data = resp.read()
            if len(data) < 100:
                break
            gdf = gpd.read_file(io.BytesIO(data))
            if gdf.empty:
                break
            all_gdfs.append(gdf)
            start_index += len(gdf)
            if len(gdf) < PAGE_SIZE:
                break
        except Exception as e:
            print(f"    WFS page {page} error: {e}")
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


def fetch_streams(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch all streams/rivers/ditches from ETAK."""
    print("  Fetching streams/rivers/ditches (etak:e_203_vooluveekogu_j)...")
    gdf = fetch_wfs_paged_json("etak:e_203_vooluveekogu_j", bbox)
    print(f"    Got {len(gdf)} stream features")
    if not gdf.empty and "tyyp_tekst" in gdf.columns:
        types = gdf["tyyp_tekst"].value_counts()
        for t, cnt in types.items():
            print(f"      {t}: {cnt}")
    return gdf


def fetch_waterbodies(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch standing waterbodies (lakes, ponds)."""
    print("  Fetching waterbodies (etak:e_202_seisuveekogu_a)...")
    gdf = fetch_wfs_paged_json("etak:e_202_seisuveekogu_a", bbox)
    print(f"    Got {len(gdf)} waterbody polygons")
    return gdf


def compute_line_density_per_cell(grid: gpd.GeoDataFrame,
                                   lines: gpd.GeoDataFrame,
                                   col_name: str) -> np.ndarray:
    """Compute total line length (km) within each grid cell."""
    densities = np.zeros(len(grid))
    if lines.empty:
        return densities

    # Spatial index for efficiency
    sindex = lines.sindex

    for i, cell_geom in enumerate(grid.geometry):
        # Find candidate lines using spatial index
        candidates_idx = list(sindex.intersection(cell_geom.bounds))
        if not candidates_idx:
            continue
        candidates = lines.iloc[candidates_idx]
        # Clip lines to cell and sum length
        try:
            clipped = candidates.intersection(cell_geom)
            total_length_m = clipped.length.sum()
            densities[i] = total_length_m / 1000.0  # convert to km
        except Exception:
            pass

    return densities


def compute_distance_to_features(grid: gpd.GeoDataFrame,
                                  features: gpd.GeoDataFrame) -> np.ndarray:
    """Compute distance from each cell centroid to nearest feature (meters)."""
    distances = np.full(len(grid), np.nan)
    if features.empty:
        return distances

    centroids = grid.geometry.centroid

    # Union all features for fast nearest-point lookup
    try:
        unified = features.geometry.union_all()
    except Exception:
        unified = features.union_all()

    for i, centroid in enumerate(centroids):
        try:
            distances[i] = centroid.distance(unified)
        except Exception:
            pass

    return distances


def compute_waterbody_overlap(grid: gpd.GeoDataFrame,
                               waterbodies: gpd.GeoDataFrame) -> np.ndarray:
    """Compute share of each cell covered by waterbodies."""
    overlaps = np.zeros(len(grid))
    if waterbodies.empty:
        return overlaps

    try:
        dissolved = waterbodies.geometry.union_all()
    except Exception:
        dissolved = waterbodies.union_all()

    for i, cell_geom in enumerate(grid.geometry):
        try:
            intersection = cell_geom.intersection(dissolved)
            if not intersection.is_empty:
                overlaps[i] = intersection.area / cell_geom.area
        except Exception:
            pass

    return np.clip(overlaps, 0, 1)


def derive_hydrology_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Derive low_slope_score, lowland_score, and hydrology_restoration_score."""
    out = df.copy()

    # --- Slope/elevation scores ---
    # If DEM data not available, use proxies from water/wetland context
    if "elevation_mean" in out.columns and out["elevation_mean"].notna().any():
        # Normalize elevation: lower = more suitable for wetland restoration
        elev = out["elevation_mean"].fillna(out["elevation_mean"].median())
        elev_p5 = np.percentile(elev.dropna(), 5)
        elev_p95 = np.percentile(elev.dropna(), 95)
        out["lowland_score"] = (1.0 - (elev - elev_p5) / max(elev_p95 - elev_p5, 1)).clip(0, 1)
    else:
        # Fallback: use water proximity as proxy for lowland
        dist_water = out["distance_to_water_m"].fillna(out["distance_to_water_m"].max())
        max_dist = max(dist_water.quantile(0.95), 1)
        out["lowland_score"] = (1.0 - dist_water / max_dist).clip(0, 1)

    if "slope_mean" in out.columns and out["slope_mean"].notna().any():
        slope = out["slope_mean"].fillna(0)
        slope_p95 = max(np.percentile(slope.dropna(), 95), 1)
        out["low_slope_score"] = (1.0 - slope / slope_p95).clip(0, 1)
    else:
        # Fallback: assume flat terrain (Estonia is generally flat)
        out["low_slope_score"] = 0.75

    # --- Water proximity score ---
    dist = out["distance_to_water_m"].fillna(out["distance_to_water_m"].max())
    max_relevant_dist = 5000.0  # 5km
    out["water_proximity_score"] = (1.0 - dist / max_relevant_dist).clip(0, 1)

    # --- Wetland neighbor score (ditch + stream density as proxy) ---
    total_water_density = out["stream_density_1km"] + out["ditch_density_1km"]
    max_density = max(total_water_density.quantile(0.95), 0.1)
    out["wetland_neighbor_score"] = (total_water_density / max_density).clip(0, 1)

    # --- Ditch/drainage context score ---
    max_ditch = max(out["ditch_density_1km"].quantile(0.95), 0.1)
    out["ditch_drainage_context_score"] = (out["ditch_density_1km"] / max_ditch).clip(0, 1)

    # --- Combined hydrology restoration score (Section 6 of spec) ---
    # With ditch data available:
    out["hydrology_restoration_score"] = (
        0.30 * out["low_slope_score"]
        + 0.25 * out["lowland_score"]
        + 0.20 * out["water_proximity_score"]
        + 0.15 * out["wetland_neighbor_score"]
        + 0.10 * out["ditch_drainage_context_score"]
    ).clip(0, 1)

    return out


def process_hydrology(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    """Main processing: fetch hydrology layers and compute per-cell features."""
    print("Processing hydrology features...")

    bounds = grid.total_bounds
    bbox = (bounds[0], bounds[1], bounds[2], bounds[3], "urn:ogc:def:crs:EPSG::3301")

    # Fetch layers
    streams = fetch_streams(bbox)
    waterbodies = fetch_waterbodies(bbox)

    # Split streams into rivers/streams vs ditches
    if not streams.empty and "tyyp_tekst" in streams.columns:
        ditches = streams[streams["tyyp_tekst"] == "Kraav"].copy()
        rivers = streams[streams["tyyp_tekst"] != "Kraav"].copy()
    else:
        ditches = gpd.GeoDataFrame(geometry=[], crs=CRS)
        rivers = streams

    print(f"\n  Rivers/streams: {len(rivers)}, Ditches: {len(ditches)}")

    # Combine all water features for distance calculation
    all_water = gpd.GeoDataFrame(geometry=[], crs=CRS)
    parts = []
    if not waterbodies.empty:
        parts.append(waterbodies[["geometry"]])
    if not streams.empty:
        parts.append(streams[["geometry"]])
    if parts:
        all_water = pd.concat(parts, ignore_index=True)
        all_water = gpd.GeoDataFrame(all_water, geometry="geometry", crs=CRS)

    # Compute features
    print("\n  Computing distances...")
    df = pd.DataFrame({"cell_id": grid["cell_id"].values if "cell_id" in grid.columns else range(len(grid))})

    df["distance_to_water_m"] = compute_distance_to_features(grid, all_water)
    print(f"    distance_to_water_m: mean={df['distance_to_water_m'].mean():.0f}m")

    df["distance_to_river_or_stream_m"] = compute_distance_to_features(grid, rivers)
    df["distance_to_ditch_or_drainage_m"] = compute_distance_to_features(grid, ditches)

    print("  Computing waterbody overlap...")
    df["waterbody_overlap_pct"] = compute_waterbody_overlap(grid, waterbodies)

    print("  Computing stream density...")
    df["stream_density_1km"] = compute_line_density_per_cell(grid, rivers, "stream_density")
    print(f"    stream_density_1km: mean={df['stream_density_1km'].mean():.2f} km/cell")

    print("  Computing ditch density...")
    df["ditch_density_1km"] = compute_line_density_per_cell(grid, ditches, "ditch_density")
    print(f"    ditch_density_1km: mean={df['ditch_density_1km'].mean():.2f} km/cell")

    # Derive scores
    print("  Deriving scores...")
    df = derive_hydrology_scores(df)
    print(f"    hydrology_restoration_score: mean={df['hydrology_restoration_score'].mean():.3f}")

    return df


def save_hydrology_features(df: pd.DataFrame):
    """Save hydrology features to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "hydrology_features.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    grid_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    if not grid_path.exists():
        print("Grid not found — run 01_prepare_grid.py first")
        raise SystemExit(1)

    grid = gpd.read_file(grid_path)
    features = process_hydrology(grid)
    save_hydrology_features(features)
