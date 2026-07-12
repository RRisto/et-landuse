"""Convert land-use transitions to estimated tCO2 sequestration/emission.

Uses Estonian-specific rates derived from:
- IPCC 2014 Wetlands Supplement, Tier 1 defaults for boreal/cool temperate
- Estonian NIR (National Inventory Report)
- METK (Center of Estonian Rural Research and Knowledge) analysis 2024
- Maljanen et al. 2010, Nordic peatlands
- ERR News reporting on Estonian LULUCF data

Key references:
- https://news.err.ee/1609382576/clashing-interests-in-the-way-of-reducing-co2-emissions-in-agriculture
- https://news.err.ee/1608756928/reducing-co2-emissions-from-land-restoring-wetlands-or-drainage-systems
- https://www.eea.europa.eu/en/europe-environment-2025/countries/estonia/lulucf-emissions
- https://link.springer.com/article/10.1672/08-206.1 (Estonian peatland GWP synthesis)
- https://www.nature.com/articles/s43247-023-01091-y (improved drained peat EF)

All values in tCO2 per hectare per year.
Positive = sequestration (good), negative = emission (bad).

IMPORTANT: Values are given as (low, mid, high) ranges.
The 'mid' value is the best estimate; low/high define a plausible confidence interval.
Actual values depend on soil type, tree species, drainage status, age, etc.
"""

import numpy as np
import pandas as pd


# --- Annual stock rates: tCO2/ha/year (low, mid, high) ---
# What a land-use type sequesters (or emits) per year if unchanged.
ANNUAL_STOCK_RATE = {
    # Estonian managed forest: varies 2-6 by age class (EEA/NIR data)
    "forest": (2.0, 4.0, 6.0),
    # Intact peatland/wetland: slow C accumulation (Maljanen et al.)
    "wetland": (0.0, 0.8, 2.0),
    # Cropland on mineral soil: mild net emitter (IPCC Vol 4)
    "agriculture_mineral": (-1.0, -0.5, -0.2),
    # Cropland on DRAINED PEAT: major emitter (IPCC Wetlands Supp: ~29 tCO2/ha/yr)
    "agriculture_peat": (-35.0, -26.0, -20.0),
    # Semi-natural grassland on mineral soil
    "grassland": (0.0, 0.3, 1.0),
}

# --- Transition rates: tCO2/ha/year gained by converting (from → to) ---
# (low, mid, high) — net change relative to prior land use.
TRANSITION_RATE = {
    # Afforestation on mineral cropland (biomass accumulation + soil recovery)
    # Young forest sequesters 4-15 tCO2/ha/yr in first decades
    ("agriculture", "forest"): (4.0, 7.0, 15.0),
    # Rewetting drained agricultural PEAT — avoids 20-30 tCO2/ha/yr emission
    # METK 2024: ~23 tCO2/ha avoided; IPCC: cropland peat EF ~29
    ("agriculture", "wetland_peat"): (15.0, 23.0, 30.0),
    # Rewetting agricultural land on mineral soil (modest benefit)
    ("agriculture", "wetland_mineral"): (1.0, 3.0, 5.0),
    # Cropland to extensive grassland (stops tillage, some soil C recovery)
    ("agriculture", "grassland"): (0.8, 1.5, 3.0),
    # Afforestation on grassland
    ("grassland", "forest"): (2.0, 4.0, 8.0),
    # Grassland rewetting (on peat)
    ("grassland", "wetland_peat"): (5.0, 10.0, 18.0),
    # Grassland rewetting (mineral)
    ("grassland", "wetland_mineral"): (0.5, 1.5, 3.0),
    # Deforestation to cropland (biomass loss + soil emission)
    ("forest", "agriculture"): (-15.0, -8.0, -5.0),
    # Forest to grassland (clear-cutting without replanting)
    ("forest", "grassland"): (-6.0, -3.5, -2.0),
    # Forest removal for wetland (paludiculture — rare, context-dependent)
    ("forest", "wetland"): (-3.0, -1.0, 0.0),
    # Draining wetland for farming — worst case (IPCC: 20-30 tCO2/ha/yr new emission)
    ("wetland", "agriculture"): (-30.0, -25.0, -20.0),
    # Draining wetland for grassland
    ("wetland", "grassland"): (-12.0, -7.0, -3.0),
    # Draining wetland for forestry
    ("wetland", "forest"): (-8.0, -4.0, -2.0),
    # Intensification: grassland to cropland
    ("grassland", "agriculture"): (-3.0, -1.5, -0.5),
}

# Cell area in hectares (1 km² = 100 ha)
CELL_AREA_HA = 100.0


def _get_agriculture_stock_rate(peat_fraction: float) -> tuple:
    """Blend agriculture stock rate based on peat overlap."""
    mineral = ANNUAL_STOCK_RATE["agriculture_mineral"]
    peat = ANNUAL_STOCK_RATE["agriculture_peat"]
    pf = np.clip(peat_fraction, 0, 1)
    return tuple(
        mineral[i] * (1 - pf) + peat[i] * pf for i in range(3)
    )


def _get_transition_rate(from_group: str, to_group: str,
                         peat_fraction: float) -> tuple:
    """Get transition rate, adjusting for peat presence."""
    # Check peat-specific transition first
    if to_group == "wetland":
        key_peat = (from_group, "wetland_peat")
        key_mineral = (from_group, "wetland_mineral")
        if key_peat in TRANSITION_RATE and key_mineral in TRANSITION_RATE:
            pf = np.clip(peat_fraction, 0, 1)
            r_peat = TRANSITION_RATE[key_peat]
            r_mineral = TRANSITION_RATE[key_mineral]
            return tuple(
                r_mineral[i] * (1 - pf) + r_peat[i] * pf for i in range(3)
            )
        if key_peat in TRANSITION_RATE:
            return TRANSITION_RATE[key_peat]

    # Generic key
    key = (from_group, to_group)
    return TRANSITION_RATE.get(key, (0.0, 0.0, 0.0))


def estimate_carbon_tonnes(context: pd.DataFrame,
                           target_fractions: np.ndarray,
                           scenario: str = "mid") -> pd.DataFrame:
    """Estimate annual tCO2 change per cell from a land-use policy.

    Args:
        context: Feature table with current land-use fractions.
            Must include peat_overlap_pct if available (from carbon_v1_5).
        target_fractions: Array (n_cells, 4) of target fractions
            [forest, wetland, agriculture, grassland].
        scenario: "low", "mid", or "high" — which estimate to use.

    Returns:
        DataFrame with per-cell carbon estimates.
    """
    scenario_idx = {"low": 0, "mid": 1, "high": 2}[scenario]
    n = len(context)
    groups = ["forest", "wetland", "agriculture", "grassland"]

    # Current fractions
    current = np.column_stack([context[f"{g}_pct"].values for g in groups])

    # Peat overlap per cell (0-1), if available
    if "peat_overlap_pct" in context.columns:
        peat_frac = context["peat_overlap_pct"].values
    else:
        peat_frac = np.zeros(n)

    # Normalize targets to available land
    urban = context["urban_pct"].values
    water = context["water_pct"].values
    available_land = np.clip(1.0 - urban - water, 0, 1)

    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]

    delta = targets - current

    # --- 1. Stock-based annual flux change ---
    # Compute per-cell stock rates (accounting for peat in agriculture)
    stock_current = np.zeros(n)
    stock_target = np.zeros(n)

    for i, g in enumerate(groups):
        if g == "agriculture":
            for cell_idx in range(n):
                rate = _get_agriculture_stock_rate(peat_frac[cell_idx])
                stock_current[cell_idx] += current[cell_idx, i] * rate[scenario_idx]
                stock_target[cell_idx] += targets[cell_idx, i] * rate[scenario_idx]
        else:
            rate = ANNUAL_STOCK_RATE.get(g, (0, 0, 0))
            stock_current += current[:, i] * rate[scenario_idx]
            stock_target += targets[:, i] * rate[scenario_idx]

    tco2_stock_change = (stock_target - stock_current) * CELL_AREA_HA

    # --- 2. Transition-based carbon ---
    tco2_transitions = np.zeros(n)

    for i_from, g_from in enumerate(groups):
        for i_to, g_to in enumerate(groups):
            if i_from == i_to:
                continue

            loss = np.clip(-delta[:, i_from], 0, None)
            gain = np.clip(delta[:, i_to], 0, None)

            # Proportional allocation of losses to gains
            total_gain = np.clip(delta, 0, None).sum(axis=1)
            total_gain = np.where(total_gain > 0, total_gain, 1.0)
            share = gain / total_gain

            # Area transitioning (fraction of cell)
            transition_area = np.minimum(loss, gain) * share

            # Per-cell transition rate (peat-aware)
            for cell_idx in range(n):
                if transition_area[cell_idx] < 1e-6:
                    continue
                rate = _get_transition_rate(g_from, g_to, peat_frac[cell_idx])
                tco2_transitions[cell_idx] += (
                    transition_area[cell_idx] * rate[scenario_idx] * CELL_AREA_HA
                )

    # --- Total ---
    tco2_total = tco2_stock_change + tco2_transitions
    ha_changed = np.abs(delta).sum(axis=1) / 2.0 * CELL_AREA_HA

    return pd.DataFrame({
        "cell_id": context["cell_id"].values if "cell_id" in context.columns else range(n),
        "tco2_per_year": tco2_total,
        "tco2_per_year_stocks": tco2_stock_change,
        "tco2_per_year_transitions": tco2_transitions,
        "ha_changed": ha_changed,
    })


def estimate_carbon_tonnes_ci(context: pd.DataFrame,
                              target_fractions: np.ndarray) -> dict:
    """Estimate carbon with confidence interval (low, mid, high scenarios).

    Returns dict with total estimates for each scenario.
    """
    results = {}
    for scenario in ("low", "mid", "high"):
        df = estimate_carbon_tonnes(context, target_fractions, scenario=scenario)
        results[scenario] = {
            "total_tco2_per_year": df["tco2_per_year"].sum(),
            "tco2_per_year_stocks": df["tco2_per_year_stocks"].sum(),
            "tco2_per_year_transitions": df["tco2_per_year_transitions"].sum(),
            "total_ha_changed": df["ha_changed"].sum(),
            "total_km2_changed": df["ha_changed"].sum() / 100.0,
            "cells_changed": (df["ha_changed"] > 0.5).sum(),
        }
    return results


def summarize_carbon_tonnes(context: pd.DataFrame,
                            target_fractions: np.ndarray) -> dict:
    """Summarize total carbon impact with CI in real units.

    Returns dict with 'low', 'mid', 'high' totals and summary stats.
    """
    ci = estimate_carbon_tonnes_ci(context, target_fractions)
    mid = ci["mid"]

    return {
        "total_tco2_per_year_mid": mid["total_tco2_per_year"],
        "total_tco2_per_year_low": ci["low"]["total_tco2_per_year"],
        "total_tco2_per_year_high": ci["high"]["total_tco2_per_year"],
        "tco2_stocks_mid": mid["tco2_per_year_stocks"],
        "tco2_transitions_mid": mid["tco2_per_year_transitions"],
        "total_ha_changed": mid["total_ha_changed"],
        "total_km2_changed": mid["total_km2_changed"],
        "cells_changed": mid["cells_changed"],
        "total_cells": len(context),
        "avg_tco2_per_ha_changed": (
            mid["total_tco2_per_year"] / max(mid["total_ha_changed"], 1)
        ),
    }
