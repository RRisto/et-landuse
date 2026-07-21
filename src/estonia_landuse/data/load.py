"""Loading and basic processing functions for V1 datasets."""

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from owslib.wfs import WebFeatureService
from shapely.geometry import mapping

from .constants import (
    CARBON_SCORES,
    CORINE_PIXEL_TO_CODE,
    CORINE_TO_GROUP,
    CRS_ESTONIAN,
    EELIS_WFS_URL,
    NATURALNESS_SCORES,
)


# Path to carbon v1.5 scores (relative to project root)
_CARBON_V15_SCORES = None  # set lazily


def _carbon_v15_path():
    """Get path to carbon v1.5 scores parquet."""
    from .constants import PROJECT_ROOT
    return PROJECT_ROOT / "data" / "processed" / "carbon_v1_5" / "carbon_scores.parquet"


def load_carbon_v15_scores() -> pd.DataFrame | None:
    """Load carbon v1.5 action scores if available.
    
    Returns DataFrame with columns:
        cell_id, carbon_stock_score, score_protect_carbon,
        score_restore_wetland_carbon, score_afforest_carbon,
        carbon_model_uncertainty_score
    
    Returns None if the file doesn't exist yet.
    """
    path = _carbon_v15_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)


def merge_carbon_v15(features: pd.DataFrame) -> pd.DataFrame:
    """Merge carbon v1.5 scores into a features DataFrame (by cell_id).
    
    If carbon v1.5 data is not available, returns features unchanged.
    """
    scores = load_carbon_v15_scores()
    if scores is None:
        return features
    
    # Only merge the columns the simulator needs
    merge_cols = [
        "cell_id",
        "carbon_stock_score",
        "score_protect_carbon",
        "score_restore_wetland_carbon",
        "score_afforest_carbon",
        "carbon_model_uncertainty_score",
    ]
    merge_cols = [c for c in merge_cols if c in scores.columns]
    
    if "cell_id" not in features.columns:
        # Can't merge without cell_id
        return features
    
    merged = features.merge(scores[merge_cols], on="cell_id", how="left")
    return merged


def load_county_boundary(counties_path: str, county_name: str) -> gpd.GeoDataFrame:
    """Load a single county boundary polygon."""
    counties = gpd.read_file(counties_path)
    if counties.crs != CRS_ESTONIAN:
        counties = counties.to_crs(CRS_ESTONIAN)
    # Try common name columns
    for col in ["MNIMI", "NIMI", "NAME", "name", "MAANIMI"]:
        if col in counties.columns:
            match = counties[counties[col].str.contains(county_name, case=False, na=False)]
            if len(match) > 0:
                return match.iloc[[0]]
    raise ValueError(f"County '{county_name}' not found. Columns: {list(counties.columns)}")


def clip_grid_to_county(grid: gpd.GeoDataFrame, county: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clip a grid to a county boundary using spatial intersection."""
    if grid.crs != CRS_ESTONIAN:
        grid = grid.to_crs(CRS_ESTONIAN)
    clipped = gpd.sjoin(grid, county[["geometry"]], how="inner", predicate="intersects")
    return clipped.drop(columns=["index_right"], errors="ignore").reset_index(drop=True)


def fetch_protected_areas_wfs(bbox: tuple, layer: str = "eelis:kr_kaitseala") -> gpd.GeoDataFrame:
    """Fetch protected areas from EELIS public WFS within a bounding box.
    
    bbox: (minx, miny, maxx, maxy) in EPSG:3301
    """
    wfs = WebFeatureService(url=EELIS_WFS_URL, version="2.0.0")
    
    # List available layers if requested one not found
    available = list(wfs.contents.keys())
    if layer not in available:
        print(f"Layer '{layer}' not found. Available layers ({len(available)}):")
        for name in sorted(available)[:30]:
            print(f"  {name}")
        raise ValueError(f"Layer '{layer}' not available")

    resp = wfs.getfeature(
        typename=[layer],
        bbox=bbox,
        srsname=CRS_ESTONIAN,
        outputFormat="application/json",
    )
    gdf = gpd.read_file(resp)
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_ESTONIAN)
    elif gdf.crs != CRS_ESTONIAN:
        gdf = gdf.to_crs(CRS_ESTONIAN)
    return gdf


# All EELIS protection layers relevant for land-use planning
# Names verified against live WFS at gsavalik.envir.ee
PROTECTED_AREA_LAYERS = [
    "eelis:kr_kaitseala",          # Nature reserves (kaitsealad)
    "eelis:kr_hoiuala",            # Conservation areas (Natura 2000 habitat)
   # "eelis:kr_kohalik_objekt",     # Local protected objects
  #  "eelis:kr_kohalik_objekt_pv",  # Local protected objects (buffer zones)
]


def fetch_all_protected_areas_wfs(bbox: tuple) -> gpd.GeoDataFrame:
    """Fetch all types of protected areas from EELIS WFS and merge.

    Fetches multiple layers (reserves, Natura 2000, local objects) and
    returns a unified GeoDataFrame with a 'protection_type' column.
    Returns individual polygons (not dissolved) for distance calculations.

    bbox: (minx, miny, maxx, maxy) in EPSG:3301
    """
    all_gdfs = []

    for layer in PROTECTED_AREA_LAYERS:
        try:
            gdf = fetch_protected_areas_wfs(bbox, layer=layer)
            gdf["protection_type"] = layer.split(":")[-1]
            all_gdfs.append(gdf[["geometry", "protection_type"]])
            print(f"  {layer}: {len(gdf)} polygons")
        except Exception as e:
            print(f"  {layer}: FAILED ({e})")

    if not all_gdfs:
        return gpd.GeoDataFrame(columns=["geometry", "protection_type"],
                                geometry="geometry", crs=CRS_ESTONIAN)

    combined = pd.concat(all_gdfs, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=CRS_ESTONIAN)
    print(f"  Total: {len(combined)} polygons from {len(all_gdfs)} layers")
    return combined


def add_land_cover_group(gdf: gpd.GeoDataFrame, clc_col: str = "CODE_18") -> gpd.GeoDataFrame:
    """Add land_cover_group, naturalness_score, carbon_score from CORINE class."""
    df = gdf.copy()
    df["land_cover_class"] = pd.to_numeric(df[clc_col], errors="coerce").astype("Int64")
    df["land_cover_group"] = df["land_cover_class"].map(CORINE_TO_GROUP).fillna("other_natural")
    df["naturalness_score"] = df["land_cover_group"].map(NATURALNESS_SCORES)
    df["carbon_score"] = df["land_cover_group"].map(CARBON_SCORES)
    return df


def extract_clc_from_raster(grid: gpd.GeoDataFrame, clc_tif_path: str) -> gpd.GeoDataFrame:
    """Extract CORINE land cover per grid cell: dominant class + group proportions.
    
    For each 1km grid cell, reads all 100m pixels inside it and computes:
    - dominant land cover class (mode)
    - proportion of each land cover group (forest_pct, wetland_pct, etc.)
    - weighted naturalness and carbon scores based on proportions
    """
    from collections import Counter

    GROUPS = ["urban", "agriculture", "grassland", "forest", "wetland", "water", "other_natural"]
    
    df = grid.copy()
    
    with rasterio.open(clc_tif_path) as src:
        grid_in_raster_crs = df.to_crs(src.crs)
        
        rows = []
        for geom in grid_in_raster_crs.geometry:
            row = {}
            try:
                out_image, _ = rio_mask(src, [mapping(geom)], crop=True, nodata=0)
                pixels = out_image[0]
                valid = pixels[pixels > 0]
                
                if len(valid) > 0:
                    # Dominant class (translate pixel -> CLC code)
                    counts = Counter(valid.tolist())
                    dominant_pixel = counts.most_common(1)[0][0]
                    row["land_cover_class"] = CORINE_PIXEL_TO_CODE.get(int(dominant_pixel), int(dominant_pixel))
                    
                    # Map each pixel to group and count proportions
                    group_counts = Counter()
                    for val, cnt in counts.items():
                        clc_code = CORINE_PIXEL_TO_CODE.get(int(val), int(val))
                        group = CORINE_TO_GROUP.get(clc_code, "other_natural")
                        group_counts[group] += cnt
                    
                    total = sum(group_counts.values())
                    for g in GROUPS:
                        row[f"{g}_pct"] = group_counts.get(g, 0) / total
                else:
                    row["land_cover_class"] = None
                    for g in GROUPS:
                        row[f"{g}_pct"] = 0.0
            except Exception:
                row["land_cover_class"] = None
                for g in GROUPS:
                    row[f"{g}_pct"] = 0.0
            
            rows.append(row)
    
    result = pd.DataFrame(rows)
    df["land_cover_class"] = pd.array(result["land_cover_class"].tolist(), dtype="Int64")
    df["land_cover_group"] = df["land_cover_class"].map(CORINE_TO_GROUP).fillna("other_natural")
    
    for g in GROUPS:
        df[f"{g}_pct"] = result[f"{g}_pct"].values
    
    # Weighted scores from proportions (exclude water from weighting)
    land_pct = 1.0 - df["water_pct"]
    df["naturalness_score"] = sum(
        df[f"{group}_pct"] * score
        for group, score in NATURALNESS_SCORES.items()
        if score is not None
    ) / land_pct.replace(0, 1)
    
    df["carbon_score"] = sum(
        df[f"{group}_pct"] * score
        for group, score in CARBON_SCORES.items()
        if score is not None
    ) / land_pct.replace(0, 1)
    
    return df


def compute_distance_to_nearest(grid: gpd.GeoDataFrame, features: gpd.GeoDataFrame) -> np.ndarray:
    """Compute distance from each grid cell centroid to the nearest feature geometry."""
    centroids = grid.geometry.centroid
    if features.empty:
        return np.full(len(grid), np.nan)
    
    unified = features.geometry.union_all()
    distances = centroids.distance(unified)
    return distances.values


def load_osm_layer(shp_path: str, county_grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Load an OSM shapefile and clip to the county grid extent.
    
    Handles the CRS mismatch: OSM is EPSG:4326, grid is EPSG:3301.
    """
    # Convert grid bounds to WGS84 for bbox filtering
    grid_wgs84 = county_grid.to_crs("EPSG:4326")
    bbox = tuple(grid_wgs84.total_bounds)
    
    gdf = gpd.read_file(shp_path, bbox=bbox)
    if gdf.empty:
        return gdf
    gdf = gdf.to_crs(CRS_ESTONIAN)
    return gdf


def compute_road_density(grid: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> np.ndarray:
    """Compute total road length (km) within each grid cell."""
    if roads.empty:
        return np.zeros(len(grid))
    
    # Spatial join: find which roads intersect which cells
    joined = gpd.sjoin(roads, grid[["cell_id", "geometry"]], how="inner", predicate="intersects")
    
    # Clip roads to cell boundaries and measure length
    densities = np.zeros(len(grid))
    for cell_id, group in joined.groupby("cell_id"):
        cell_geom = grid.loc[grid["cell_id"] == cell_id, "geometry"].values[0]
        clipped = group.geometry.intersection(cell_geom)
        total_length_m = clipped.length.sum()
        densities[cell_id] = total_length_m / 1000  # km
    
    return densities


def compute_building_density(grid: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame) -> np.ndarray:
    """Count number of buildings per grid cell."""
    if buildings.empty:
        return np.zeros(len(grid))
    
    joined = gpd.sjoin(buildings, grid[["cell_id", "geometry"]], how="inner", predicate="intersects")
    counts = joined.groupby("cell_id").size()
    
    densities = np.zeros(len(grid))
    for cell_id, count in counts.items():
        densities[cell_id] = count
    
    return densities
