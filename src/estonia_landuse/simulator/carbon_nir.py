"""NIR-calibrated carbon scorer: uses Estonian National Inventory Report
emission factors stratified by transition type and soil (peat/mineral).

Drop-in replacement for the flat lookup in carbon_tonnes.py.
Produces per-cell tCO2/yr estimates that are closer to observed national totals.

Sources:
- Estonia NIR 2024, Chapter 6 (LULUCF)
- EEA LULUCF Emission Factors Viewer (country-specific Tier 2 values)
- IPCC 2013 Wetlands Supplement (boreal peatland defaults)
"""

import numpy as np
import pandas as pd


# Estonian NIR 2024 implied emission factors (tCO2/ha/yr)
# Positive = net sequestration, Negative = net emission
NIR_TRANSITION_FACTORS = {
    # Cropland → Forest: young afforestation
    ("agriculture", "forest"): {
        "mineral": 8.7,   # biomass 7.5 + SOC recovery 1.2
        "peat": 0.5,      # biomass 5.0 + peat still emitting -4.5
    },
    # Grassland → Forest
    ("grassland", "forest"): {
        "mineral": 6.3,   # biomass 5.5 + SOC 0.8
        "peat": 1.0,
    },
    # Cropland → Wetland (rewetting)
    ("agriculture", "wetland"): {
        "mineral": 2.5,
        "peat": 23.0,     # avoided peat emission
    },
    # Grassland → Wetland
    ("grassland", "wetland"): {
        "mineral": 1.5,
        "peat": 12.0,
    },
    # Forest → Cropland (deforestation)
    ("forest", "agriculture"): {
        "mineral": -8.0,  # annualized biomass loss over 20yr
        "peat": -34.0,    # biomass loss + peat drainage starts
    },
    # Forest → Grassland
    ("forest", "grassland"): {
        "mineral": -4.5,
        "peat": -14.5,
    },
    # Wetland → Cropland (drainage)
    ("wetland", "agriculture"): {
        "mineral": -2.0,
        "peat": -26.0,
    },
    # Wetland → Grassland
    ("wetland", "grassland"): {
        "mineral": -1.0,
        "peat": -7.0,
    },
    # Cropland → Grassland (extensification)
    ("agriculture", "grassland"): {
        "mineral": 1.5,
        "peat": 8.0,      # reduced tillage on peat
    },
    # Grassland → Cropland (intensification)
    ("grassland", "agriculture"): {
        "mineral": -1.5,
        "peat": -16.0,
    },
    # Forest → Wetland (paludiculture, rare)
    ("forest", "wetland"): {
        "mineral": -1.0,
        "peat": 4.0,      # net positive if rewetting drained forest peat
    },
    # Wetland → Forest
    ("wetland", "forest"): {
        "mineral": 2.0,
        "peat": -4.0,     # draining peat for forestry
    },
}

# Cell area in hectares (1 km² = 100 ha)
CELL_AREA_HA = 100.0


def estimate_carbon_nir(context: pd.DataFrame,
                        target_fractions: np.ndarray) -> pd.DataFrame:
    """Estimate annual tCO2 change per cell using NIR-calibrated factors.

    Same interface as carbon_tonnes.estimate_carbon_tonnes so it can be
    swapped in as a drop-in replacement.

    Args:
        context: Feature table with current land-use fractions (_pct columns).
        target_fractions: Array (n_cells, 4) — target fractions for
            [forest, wetland, agriculture, grassland].

    Returns:
        DataFrame with per-cell carbon estimates (same schema as carbon_tonnes).
    """
    n = len(context)
    groups = ["forest", "wetland", "agriculture", "grassland"]

    # Current fractions
    current = np.column_stack([context[f"{g}_pct"].values for g in groups])

    # Peat overlap per cell (0-1)
    if "peat_overlap_pct" in context.columns:
        peat_frac = context["peat_overlap_pct"].values.astype(np.float64)
    else:
        peat_frac = np.zeros(n)
    peat_frac = np.clip(peat_frac, 0, 1)

    # Normalize targets to available land
    urban = context["urban_pct"].values if "urban_pct" in context.columns else np.zeros(n)
    water = context["water_pct"].values if "water_pct" in context.columns else np.zeros(n)
    available_land = np.clip(1.0 - urban - water, 0, 1)

    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]

    delta = targets - current  # (n, 4)

    # Vectorized transition-based carbon calculation
    # loss_from[i, g] = how much cell i loses from group g
    loss_from = np.clip(-delta, 0, None)  # (n, 4)
    gain_to = np.clip(delta, 0, None)      # (n, 4)

    # Total loss and gain per cell
    total_loss = loss_from.sum(axis=1, keepdims=True)  # (n, 1)
    total_loss = np.where(total_loss > 0, total_loss, 1.0)
    total_gain = gain_to.sum(axis=1, keepdims=True)    # (n, 1)
    total_gain = np.where(total_gain > 0, total_gain, 1.0)

    # Fraction of loss from each source / fraction of gain to each target
    loss_share = loss_from / total_loss  # (n, 4)
    gain_share = gain_to / total_gain    # (n, 4)

    # Wetland suitability: gate wetland transitions by physical feasibility
    # (same approach as biodiversity model in 03.2)
    # Zero out credit where wetland is not feasible (suit < 0.3)
    if "wetland_suitability" in context.columns:
        wetland_suit = context["wetland_suitability"].values.astype(np.float64)
    else:
        wetland_suit = np.ones(n)

    # Hard gate: no carbon credit for wetland conversion where suitability < 0.3
    wetland_feasible = np.where(wetland_suit >= 0.3, wetland_suit, 0.0)
    # Also cap max creditable wetland gain to suitability * 0.3 (max 30% even in best cells)
    max_wetland_gain = wetland_feasible * 0.3

    # For each transition pair, compute area transitioning and apply EF
    tco2 = np.zeros(n)
    # Total area changing (for proportional allocation)
    total_change = np.abs(delta).sum(axis=1) / 2.0  # (n,)

    for (g_from, g_to), factors in NIR_TRANSITION_FACTORS.items():
        i_from = groups.index(g_from)
        i_to = groups.index(g_to)

        # Transition area = loss_share_from * gain_share_to * total_change
        transition_frac = loss_share[:, i_from] * gain_share[:, i_to] * total_change

        # Gate wetland transitions: only credit up to feasible amount
        if g_to == "wetland":
            transition_frac = np.minimum(transition_frac, max_wetland_gain) * wetland_feasible

        # Emission factor blended by peat
        ef = factors["mineral"] * (1 - peat_frac) + factors["peat"] * peat_frac
        tco2 += transition_frac * ef * CELL_AREA_HA

    ha_changed = total_change * CELL_AREA_HA

    return pd.DataFrame({
        "cell_id": context["cell_id"].values if "cell_id" in context.columns else range(n),
        "tco2_per_year": tco2,
        "tco2_per_year_stocks": np.zeros(n),
        "tco2_per_year_transitions": tco2,
        "ha_changed": ha_changed,
    })


def score_carbon_nir(context: pd.DataFrame,
                     target_fractions: np.ndarray) -> np.ndarray:
    """Return per-cell carbon gain as a normalized score (for use in simulator).

    This matches the interface expected by simulator.py's carbon_gain calculation.
    Returns values in the same scale as the flat carbon_density model (0-1 ish).
    """
    result = estimate_carbon_nir(context, target_fractions)
    # Normalize to per-cell-per-ha equivalent for comparability
    # Max realistic gain ~23 tCO2/ha/yr (peat rewetting), scale to ~1.0
    SCALE_FACTOR = 1.0 / (10.0 * CELL_AREA_HA)  # 10 tCO2/ha as "1.0 score"
    return result["tco2_per_year"].values * SCALE_FACTOR
