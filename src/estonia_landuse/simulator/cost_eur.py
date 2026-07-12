"""Convert land-use transitions to estimated implementation cost in EUR.

Provides per-hectare cost ranges (low, mid, high) for each transition type,
based on Estonian-specific data where available.

Key references:
- Arbonics/AgFunder 2025: afforestation in Baltics starts at €2,000/ha
  https://agfundernews.com/planting-more-forests-comes-with-high-upfront-costs-many-landowners-cant-afford-report
- ERR 2024: Estonia spent €40M+ on peatland restoration over past decades
  https://news.err.ee/1609248588/estonia-planning-to-restore-25-000-hectares-of-marshland-by-2050
- ERR 2025: €68M meadows restoration plan in climate act
  https://news.err.ee/1609570045/68-million-meadows-restoration-plan-added-to-updated-climate-act
- ERR 2026: Estonian agricultural land avg price €6,122/ha; rent ~€150/ha/yr
  https://news.err.ee/1610026633/agricultural-land-prices-fall-in-estonia-amid-lack-of-large-deals
- Eurostat 2024: EU avg arable land rent €295/ha/yr
  https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Agricultural_land_prices_and_rents_-_statistics
- METK 2024: Estonian agricultural peat soil analysis
  https://news.err.ee/1609382576/clashing-interests-in-the-way-of-reducing-co2-emissions-in-agriculture

All costs in EUR per hectare (one-time implementation cost).
Opportunity costs are annualized (EUR/ha/year of lost income).

IMPORTANT: These are rough estimates with wide uncertainty ranges.
Actual costs depend on site conditions, scale, labor market, subsidies.
"""

import numpy as np
import pandas as pd


# --- Implementation costs: EUR/ha (one-time) (low, mid, high) ---
IMPLEMENTATION_COST = {
    # Afforestation: saplings, planting, 5-year maintenance
    # Arbonics 2025: "starts at €2,000/ha and only goes up"
    ("agriculture", "forest"): (1500, 2500, 4000),
    ("grassland", "forest"): (1500, 2500, 4000),

    # Wetland restoration: ditch blocking, water level management, monitoring
    # ERR: €40M over decades for peatland; €68M for meadows plan
    # LIFE Peat Restore: ~5,300 ha across 5 countries
    # Estimates: €1,500-3,000/ha for simple rewetting, up to €15,000 for complex
    ("agriculture", "wetland"): (2000, 5000, 15000),
    ("grassland", "wetland"): (1500, 4000, 12000),
    ("forest", "wetland"): (3000, 7000, 15000),  # requires tree removal + rewetting

    # Grassland conversion: stop inputs, re-seed, basic fencing
    ("agriculture", "grassland"): (300, 600, 1200),

    # These transitions are generally not planned interventions but included
    # for completeness (represent infrastructure/development costs)
    ("forest", "agriculture"): (2000, 4000, 8000),  # clearing, soil prep
    ("forest", "grassland"): (1500, 3000, 6000),    # clearing without replanting
    ("wetland", "agriculture"): (5000, 10000, 20000),  # major drainage works
    ("wetland", "grassland"): (3000, 6000, 12000),     # partial drainage
    ("wetland", "forest"): (4000, 8000, 15000),        # drain + plant
    ("grassland", "agriculture"): (500, 1000, 2000),   # plowing, soil prep
}

# --- Annual opportunity cost: EUR/ha/year (lost income from taking land out of production) ---
# Estonian agricultural rent ~€150/ha/yr (METK 2024 article)
# Eurostat: EU avg arable rent €295/ha/yr (Estonia below EU average)
OPPORTUNITY_COST_PER_YEAR = {
    # Lost agricultural income when converting farmland
    "agriculture": (100, 180, 300),
    # Lost forestry income (timber harvest revenue)
    "forest": (50, 120, 250),
    # Grassland has low productive value
    "grassland": (20, 50, 100),
    # Wetland: no productive use typically
    "wetland": (0, 0, 0),
}

# Time horizon for annualizing opportunity cost (years)
DEFAULT_HORIZON_YEARS = 20

# Cell area in hectares (1 km² = 100 ha)
CELL_AREA_HA = 100.0


def estimate_cost_eur(context: pd.DataFrame,
                      target_fractions: np.ndarray,
                      scenario: str = "mid",
                      horizon_years: int = DEFAULT_HORIZON_YEARS,
                      include_opportunity_cost: bool = True) -> pd.DataFrame:
    """Estimate implementation + opportunity cost per cell in EUR.

    Args:
        context: Feature table with current land-use fractions.
        target_fractions: Array (n_cells, 4) [forest, wetland, agriculture, grassland].
        scenario: "low", "mid", or "high".
        horizon_years: Years over which to sum opportunity cost.
        include_opportunity_cost: Whether to add lost income from converting land.

    Returns:
        DataFrame with per-cell cost breakdown.
    """
    scenario_idx = {"low": 0, "mid": 1, "high": 2}[scenario]
    n = len(context)
    groups = ["forest", "wetland", "agriculture", "grassland"]

    # Current fractions
    current = np.column_stack([context[f"{g}_pct"].values for g in groups])

    # Normalize targets
    urban = context["urban_pct"].values
    water = context["water_pct"].values
    available_land = np.clip(1.0 - urban - water, 0, 1)

    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]

    delta = targets - current

    # --- Implementation cost ---
    impl_cost = np.zeros(n)

    for i_from, g_from in enumerate(groups):
        for i_to, g_to in enumerate(groups):
            if i_from == i_to:
                continue

            key = (g_from, g_to)
            cost_tuple = IMPLEMENTATION_COST.get(key, (0, 0, 0))
            cost_per_ha = cost_tuple[scenario_idx]

            if cost_per_ha == 0:
                continue

            # Estimate area transitioning from g_from to g_to
            loss = np.clip(-delta[:, i_from], 0, None)
            gain = np.clip(delta[:, i_to], 0, None)

            total_gain = np.clip(delta, 0, None).sum(axis=1)
            total_gain = np.where(total_gain > 0, total_gain, 1.0)
            share = gain / total_gain

            transition_area_frac = np.minimum(loss, gain) * share
            transition_area_ha = transition_area_frac * CELL_AREA_HA

            impl_cost += transition_area_ha * cost_per_ha

    # --- Opportunity cost ---
    opp_cost = np.zeros(n)
    if include_opportunity_cost:
        for i_from, g_from in enumerate(groups):
            opp_tuple = OPPORTUNITY_COST_PER_YEAR.get(g_from, (0, 0, 0))
            opp_per_ha_yr = opp_tuple[scenario_idx]

            if opp_per_ha_yr == 0:
                continue

            # Area lost from this land use (converted to something else)
            loss_frac = np.clip(-delta[:, i_from], 0, None)
            loss_ha = loss_frac * CELL_AREA_HA

            opp_cost += loss_ha * opp_per_ha_yr * horizon_years

    total_cost = impl_cost + opp_cost
    ha_changed = np.abs(delta).sum(axis=1) / 2.0 * CELL_AREA_HA

    return pd.DataFrame({
        "cell_id": context["cell_id"].values if "cell_id" in context.columns else range(n),
        "cost_eur_total": total_cost,
        "cost_eur_implementation": impl_cost,
        "cost_eur_opportunity": opp_cost,
        "ha_changed": ha_changed,
    })


def estimate_cost_eur_ci(context: pd.DataFrame,
                         target_fractions: np.ndarray,
                         horizon_years: int = DEFAULT_HORIZON_YEARS) -> dict:
    """Estimate cost with confidence interval (low, mid, high).

    Returns dict with totals for each scenario.
    """
    results = {}
    for scenario in ("low", "mid", "high"):
        df = estimate_cost_eur(context, target_fractions,
                               scenario=scenario, horizon_years=horizon_years)
        results[scenario] = {
            "total_cost_eur": df["cost_eur_total"].sum(),
            "implementation_eur": df["cost_eur_implementation"].sum(),
            "opportunity_eur": df["cost_eur_opportunity"].sum(),
            "total_ha_changed": df["ha_changed"].sum(),
            "total_km2_changed": df["ha_changed"].sum() / 100.0,
            "cells_changed": int((df["ha_changed"] > 0.5).sum()),
        }
    return results


def summarize_cost_eur(context: pd.DataFrame,
                       target_fractions: np.ndarray,
                       horizon_years: int = DEFAULT_HORIZON_YEARS) -> dict:
    """Summarize total cost with CI.

    Returns dict with 'low', 'mid', 'high' totals and summary stats.
    """
    ci = estimate_cost_eur_ci(context, target_fractions, horizon_years=horizon_years)
    mid = ci["mid"]

    return {
        "total_cost_eur_mid": mid["total_cost_eur"],
        "total_cost_eur_low": ci["low"]["total_cost_eur"],
        "total_cost_eur_high": ci["high"]["total_cost_eur"],
        "implementation_eur_mid": mid["implementation_eur"],
        "opportunity_eur_mid": mid["opportunity_eur"],
        "total_ha_changed": mid["total_ha_changed"],
        "total_km2_changed": mid["total_km2_changed"],
        "cells_changed": mid["cells_changed"],
        "avg_cost_per_ha_changed": (
            mid["total_cost_eur"] / max(mid["total_ha_changed"], 1)
        ),
        "horizon_years": horizon_years,
    }
