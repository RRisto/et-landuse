"""Derive proxy features needed by the simulator from raw features."""

import numpy as np
import pandas as pd

from .config import default_config


def derive_features(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Add derived proxy features to the feature table.
    
    Args:
        df: Feature table with raw columns from notebook 01.
        config: Simulator config dict. Uses default_config() if None.
    
    Output columns added:
        wetland_suitability, biodiversity_proxy, opportunity_cost_proxy, constraint_mask
    """
    if config is None:
        config = default_config()
    
    out = df.copy()
    
    # --- Wetland suitability ---
    w = config["wetland_suitability_weights"]
    # Restoration potential: high near water/wetland but NOT in cells already dominated by wetland
    near_wetland_or_water = (out["wetland_pct"] + out["water_pct"]).clip(0, 1)
    restoration_potential = near_wetland_or_water * (1.0 - out["wetland_pct"])
    
    out["wetland_suitability"] = (
        w["wetland_pct"] * restoration_potential
        + w["water_proximity"] * out["water_pct"].clip(0, 0.5) * 2
        + w["low_roads"] * (1.0 - _normalize(out["road_density_km"]))
        + w["low_buildings"] * (1.0 - _normalize(out["building_count"]))
    ).clip(0, 1)
    
    # --- Biodiversity proxy ---
    w = config["biodiversity_proxy_weights"]
    out["biodiversity_proxy"] = (
        w["naturalness"] * out["naturalness_score"].fillna(0)
        + w["protected_area"] * out["protected_overlap_pct"].fillna(0)
        + w["low_roads"] * (1.0 - _normalize(out["road_density_km"]))
        + w["wetland_bonus"] * out["wetland_pct"]
    ).clip(0, 1)
    
    # --- Opportunity cost proxy ---
    w = config["opportunity_cost_weights"]
    population_norm = _normalize(out["TOTAL_24"].fillna(0))
    building_norm = _normalize(out["building_count"].fillna(0))
    
    out["opportunity_cost_proxy"] = (
        w["population"] * population_norm
        + w["buildings"] * building_norm
        + w["agriculture"] * out["agriculture_pct"]
        + w["roads"] * _normalize(out["road_density_km"])
    ).clip(0, 1)
    
    # --- Constraint mask ---
    c = config["constraints"]
    mask = np.zeros(len(out), dtype=int)
    
    is_urban = out["urban_pct"] > c["urban_pct_blocks_all"]
    is_water = out["water_pct"] > c["water_pct_blocks_all"]
    is_high_pop = population_norm > c["population_norm_blocks_restore"]
    is_low_wetland_suit = out["wetland_suitability"] < c["wetland_suit_min_for_restore"]
    is_already_forest = out["forest_pct"] > c["forest_pct_blocks_afforest"]
    is_heavily_protected = out["protected_overlap_pct"].fillna(0) > c["protected_pct_blocks_change"]
    is_somewhat_protected = out["protected_overlap_pct"].fillna(0) > c["protected_pct_blocks_afforest"]
    
    # Urban/water → block all actions
    mask[is_urban | is_water] |= (1 << 1) | (1 << 2) | (1 << 3)
    
    # Heavily protected → only no_change (already protected, don't intervene)
    mask[is_heavily_protected] |= (1 << 1) | (1 << 2) | (1 << 3)
    
    # Somewhat protected → block afforest (can't plant trees in a reserve)
    mask[is_somewhat_protected] |= (1 << 3)
    
    # Block restore_wetland where unsuitable or high population
    mask[is_high_pop | is_low_wetland_suit] |= (1 << 2)
    
    # Block afforest where already mostly forest
    mask[is_already_forest] |= (1 << 3)
    
    out["constraint_mask"] = mask
    
    return out


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a series to [0, 1]."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.0, index=series.index)
    return (series - mn) / (mx - mn)
