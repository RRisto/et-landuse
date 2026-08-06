"""Learned carbon scorer: uses pre-computed per-cell tCO2/ha/yr from GBR predictions.

The GBR predicts per-compartment, then results are area-weighted and aggregated
to grid cells during the spatial join (notebook 09). At evolution time, this module
just looks up the pre-computed value — no model inference needed.

For non-forest transitions (wetland/agriculture), falls back to NIR emission factors.
"""

import numpy as np
import pandas as pd

from .carbon_nir import CELL_AREA_HA, NIR_TRANSITION_FACTORS
from .targets import normalize_targets


def score_carbon_learned(context: pd.DataFrame,
                         target_fractions: np.ndarray,
                         config: dict = None) -> np.ndarray:
    """Score carbon using pre-computed GBR predictions for forest + NIR for rest.

    Expects context to have a 'predicted_tco2_ha_yr' column (from spatial join).
    If missing, falls back to NIR default (3.8).

    Returns per-cell normalized carbon gain score.
    """
    n = len(context)
    groups = ["forest", "wetland", "agriculture", "grassland"]

    # Current fractions
    current = np.column_stack([context[f"{g}_pct"].values for g in groups])

    targets = normalize_targets(context, target_fractions)

    delta = targets - current

    # --- Forest component: pre-computed per-cell rate ---
    if "predicted_tco2_ha_yr" in context.columns:
        forest_tco2_per_ha = context["predicted_tco2_ha_yr"].fillna(3.8).values
    else:
        forest_tco2_per_ha = np.full(n, 3.8)  # NIR default fallback

    # Forest gain/loss × cell-specific rate
    forest_gain = np.clip(delta[:, 0], 0, None)
    forest_loss = np.clip(-delta[:, 0], 0, None)
    forest_carbon = (forest_gain - forest_loss) * forest_tco2_per_ha * CELL_AREA_HA

    # --- Non-forest component: NIR factors for wetland/agriculture ---
    if "peat_overlap_pct" in context.columns:
        peat_frac = context["peat_overlap_pct"].values.astype(np.float64)
    else:
        peat_frac = np.zeros(n)
    peat_frac = np.clip(peat_frac, 0, 1)

    # Wetland suitability gating
    if "wetland_suitability" in context.columns:
        wetland_suit = context["wetland_suitability"].values.astype(np.float64)
    else:
        wetland_suit = np.ones(n)
    wetland_feasible = np.where(wetland_suit >= 0.3, wetland_suit, 0.0)

    # Transition allocation
    loss_from = np.clip(-delta, 0, None)
    gain_to = np.clip(delta, 0, None)
    total_loss = loss_from.sum(axis=1, keepdims=True)
    total_loss = np.where(total_loss > 0, total_loss, 1.0)
    total_gain = gain_to.sum(axis=1, keepdims=True)
    total_gain = np.where(total_gain > 0, total_gain, 1.0)
    loss_share = loss_from / total_loss
    gain_share = gain_to / total_gain
    total_change = np.abs(delta).sum(axis=1) / 2.0

    non_forest_carbon = np.zeros(n)
    for (g_from, g_to), factors in NIR_TRANSITION_FACTORS.items():
        if g_from == "forest" or g_to == "forest":
            continue

        i_from = groups.index(g_from)
        i_to = groups.index(g_to)

        transition_frac = loss_share[:, i_from] * gain_share[:, i_to] * total_change

        if g_to == "wetland":
            transition_frac = transition_frac * wetland_feasible

        ef = factors["mineral"] * (1 - peat_frac) + factors["peat"] * peat_frac
        non_forest_carbon += transition_frac * ef * CELL_AREA_HA

    # Combine and normalize
    total_tco2 = forest_carbon + non_forest_carbon
    SCALE_FACTOR = 1.0 / (10.0 * CELL_AREA_HA)
    return total_tco2 * SCALE_FACTOR
