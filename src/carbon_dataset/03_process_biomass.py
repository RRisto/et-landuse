"""Step 03: Process ESA CCI Biomass AGB raster into per-cell features.

Reads ESA CCI Biomass above-ground biomass (AGB) GeoTIFF and computes per 1km cell:
- agb_mean_mg_ha, agb_median_mg_ha, agb_p90_mg_ha, agb_max_mg_ha
- agb_uncertainty_mean_mg_ha (if uncertainty raster available)
- agb_valid_pixel_share
- aboveground_carbon_mean_mg_c_ha (AGB * 0.47)
- aboveground_co2e_mean_mg_ha (carbon * 44/12)
- forest_aboveground_carbon_score (normalized, weighted by forest_share)

Outputs: data/processed/carbon_v1_5/biomass_features.parquet

NOTE: This script requires ESA CCI Biomass data to be downloaded manually.
      Place the AGB GeoTIFF in data/raw/esa_cci_biomass/
      Expected filename pattern: *_ESACCI-BIOMASS-L4-AGB-MERGED-100m-*.tif
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping

from config import (
    AGB_TO_CARBON_FACTOR,
    BIOMASS_DIR,
    CARBON_TO_CO2E_FACTOR,
    DATA_PROCESSED_CARBON,
    NORM_LOWER_PERCENTILE,
    NORM_UPPER_PERCENTILE,
)


def find_biomass_raster(biomass_dir: Path) -> Path | None:
    """Find the AGB GeoTIFF in the biomass directory."""
    if not biomass_dir.exists():
        return None
    # Look for common ESA CCI Biomass filename patterns
    patterns = ["*AGB*.tif", "*agb*.tif", "*biomass*.tif"]
    for pattern in patterns:
        matches = list(biomass_dir.glob(pattern))
        if matches:
            return matches[0]
    # Fall back to any .tif
    tifs = list(biomass_dir.glob("*.tif"))
    return tifs[0] if tifs else None


def find_uncertainty_raster(biomass_dir: Path) -> Path | None:
    """Find the AGB uncertainty GeoTIFF."""
    if not biomass_dir.exists():
        return None
    patterns = ["*AGB*SD*.tif", "*uncertainty*.tif", "*agb*sd*.tif"]
    for pattern in patterns:
        matches = list(biomass_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def process_biomass(grid: gpd.GeoDataFrame,
                    corine_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Extract biomass features for each grid cell.

    Args:
        grid: GeoDataFrame with cell_id and geometry.
        corine_df: Optional CORINE features (used for forest_share weighting).

    Returns:
        DataFrame with biomass-derived columns, indexed by cell_id.
    """
    agb_path = find_biomass_raster(BIOMASS_DIR)
    if agb_path is None:
        print(f"No biomass raster found in {BIOMASS_DIR}")
        print("Generating placeholder biomass features (all NaN).")
        return _empty_biomass_df(grid)

    print(f"Processing AGB raster: {agb_path}")
    unc_path = find_uncertainty_raster(BIOMASS_DIR)
    if unc_path:
        print(f"  Uncertainty raster: {unc_path}")

    records = []
    with rasterio.open(str(agb_path)) as src:
        grid_reproj = grid.to_crs(src.crs)
        nodata = src.nodata if src.nodata is not None else 0

        unc_src = rasterio.open(str(unc_path)) if unc_path else None

        for idx, row in grid_reproj.iterrows():
            cell_id = grid.loc[idx, "cell_id"] if "cell_id" in grid.columns else idx
            rec = _extract_biomass_cell(src, unc_src, row.geometry, cell_id, nodata)
            records.append(rec)

        if unc_src:
            unc_src.close()

    df = pd.DataFrame(records)

    # Convert AGB to carbon and CO2e
    df["aboveground_carbon_mean_mg_c_ha"] = df["agb_mean_mg_ha"] * AGB_TO_CARBON_FACTOR
    df["aboveground_co2e_mean_mg_ha"] = df["aboveground_carbon_mean_mg_c_ha"] * CARBON_TO_CO2E_FACTOR

    # Normalize AGB to score (0-1) using robust percentiles
    df["forest_aboveground_carbon_score"] = _robust_normalize(df["agb_mean_mg_ha"])

    # Weight by forest_share if CORINE data available
    if corine_df is not None and "forest_share" in corine_df.columns:
        forest_share = corine_df.set_index("cell_id")["forest_share"].reindex(df["cell_id"]).values
        # forest_share_adjustment = min(1, forest_share / 0.5)
        adjustment = np.clip(forest_share / 0.5, 0, 1)
        adjustment = np.where(np.isnan(adjustment), 0, adjustment)
        df["forest_aboveground_carbon_score"] = df["forest_aboveground_carbon_score"] * adjustment

    # Biomass uncertainty score (higher = less reliable)
    if "agb_uncertainty_mean_mg_ha" in df.columns:
        # Ratio of uncertainty to value
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_unc = df["agb_uncertainty_mean_mg_ha"] / df["agb_mean_mg_ha"].replace(0, np.nan)
        df["biomass_uncertainty_score"] = rel_unc.clip(0, 1).fillna(1.0)
    else:
        df["biomass_uncertainty_score"] = 0.5  # default moderate uncertainty

    print(f"Processed {len(df)} cells")
    return df


def _extract_biomass_cell(src, unc_src, geom, cell_id: int, nodata) -> dict:
    """Extract biomass stats for a single grid cell."""
    rec = {"cell_id": cell_id}

    try:
        out_image, _ = rio_mask(src, [mapping(geom)], crop=True, nodata=nodata)
        pixels = out_image[0].astype(float)
        valid = pixels[(pixels != nodata) & (pixels > 0) & np.isfinite(pixels)]
    except Exception:
        valid = np.array([])

    total_pixels = max(pixels.size if len(pixels.shape) == 0 else pixels.size, 1)

    if len(valid) > 0:
        rec["agb_mean_mg_ha"] = float(np.mean(valid))
        rec["agb_median_mg_ha"] = float(np.median(valid))
        rec["agb_p90_mg_ha"] = float(np.percentile(valid, 90))
        rec["agb_max_mg_ha"] = float(np.max(valid))
        rec["agb_valid_pixel_share"] = len(valid) / total_pixels
    else:
        rec["agb_mean_mg_ha"] = 0.0
        rec["agb_median_mg_ha"] = 0.0
        rec["agb_p90_mg_ha"] = 0.0
        rec["agb_max_mg_ha"] = 0.0
        rec["agb_valid_pixel_share"] = 0.0

    # Uncertainty
    if unc_src is not None:
        try:
            unc_image, _ = rio_mask(unc_src, [mapping(geom)], crop=True,
                                    nodata=unc_src.nodata or 0)
            unc_pixels = unc_image[0].astype(float)
            unc_valid = unc_pixels[(unc_pixels > 0) & np.isfinite(unc_pixels)]
            rec["agb_uncertainty_mean_mg_ha"] = float(np.mean(unc_valid)) if len(unc_valid) > 0 else np.nan
        except Exception:
            rec["agb_uncertainty_mean_mg_ha"] = np.nan
    else:
        rec["agb_uncertainty_mean_mg_ha"] = np.nan

    return rec


def _robust_normalize(series: pd.Series) -> pd.Series:
    """Percentile-based normalization to [0, 1]."""
    valid = series.dropna()
    if len(valid) == 0:
        return pd.Series(0.0, index=series.index)
    p_low = np.percentile(valid[valid > 0], NORM_LOWER_PERCENTILE) if (valid > 0).any() else 0
    p_high = np.percentile(valid[valid > 0], NORM_UPPER_PERCENTILE) if (valid > 0).any() else 1
    if p_high == p_low:
        return pd.Series(0.0, index=series.index)
    return ((series - p_low) / (p_high - p_low)).clip(0, 1).fillna(0)


def _empty_biomass_df(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return a placeholder DataFrame with NaN biomass features."""
    cell_ids = grid["cell_id"].values if "cell_id" in grid.columns else range(len(grid))
    return pd.DataFrame({
        "cell_id": cell_ids,
        "agb_mean_mg_ha": np.nan,
        "agb_median_mg_ha": np.nan,
        "agb_p90_mg_ha": np.nan,
        "agb_max_mg_ha": np.nan,
        "agb_uncertainty_mean_mg_ha": np.nan,
        "agb_valid_pixel_share": 0.0,
        "aboveground_carbon_mean_mg_c_ha": np.nan,
        "aboveground_co2e_mean_mg_ha": np.nan,
        "forest_aboveground_carbon_score": 0.0,
        "biomass_uncertainty_score": 1.0,
    })


def save_biomass_features(df: pd.DataFrame):
    """Save biomass features to parquet."""
    DATA_PROCESSED_CARBON.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_CARBON / "biomass_features.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    grid_path = DATA_PROCESSED_CARBON / "grid.gpkg"
    corine_path = DATA_PROCESSED_CARBON / "corine_features.parquet"

    if not grid_path.exists():
        print("Grid not found — run 01_prepare_grid.py first")
        raise SystemExit(1)

    grid = gpd.read_file(grid_path)
    corine_df = pd.read_parquet(corine_path) if corine_path.exists() else None

    features = process_biomass(grid, corine_df)
    save_biomass_features(features)
