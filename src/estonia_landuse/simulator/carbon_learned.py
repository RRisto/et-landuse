"""Learned carbon scorer: GBR for forest + NIR for non-forest transitions.

Uses the trained GradientBoostingRegressor from forest registry data to score
forest-related transitions, and falls back to NIR emission factors for
wetland/agriculture transitions.

The GBR predicts per-cell tCO2/ha/yr for existing/new forest based on
spatial features (mean_age, mean_height, dominant_species, etc.) from the
forest registry spatial join.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from .carbon_nir import estimate_carbon_nir, CELL_AREA_HA, NIR_TRANSITION_FACTORS


# Cached model to avoid reloading on every call
_cached_model = None


def _load_model():
    """Load the trained GBR model (cached after first load)."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    import joblib
    model_path = (Path(__file__).resolve().parents[3] /
                  "data" / "processed" / "learned_carbon" / "forest_carbon_gbr.joblib")

    if not model_path.exists():
        raise FileNotFoundError(
            f"Learned carbon model not found at {model_path}. "
            "Run notebook 08 to train it first."
        )

    _cached_model = joblib.load(model_path)
    return _cached_model


def _predict_forest_carbon(context: pd.DataFrame) -> np.ndarray:
    """Predict tCO2/ha/yr for each cell's existing forest using GBR.

    Uses the forest features from spatial join (mean_age, mean_height, etc.)
    Returns 0 for cells without forest data.
    """
    model = _load_model()
    n = len(context)

    # Check if forest features are available
    required = ["dominant_species", "mean_age", "mean_height"]
    if not all(col in context.columns for col in required):
        # Fall back to NIR flat value for forest
        return np.full(n, 3.8)  # NIR default for forest remaining forest

    # Prepare features matching the model's expected input
    # Model trained on: peapuuliik, keskmVanus, boniteediKood, kuivendatud, kasvukohaKood, pindala, korgus
    # Grid features map: dominant_species→peapuuliik, mean_age→keskmVanus, mean_height→korgus
    feat_df = pd.DataFrame({
        "peapuuliik": context.get("dominant_species", "MA"),
        "keskmVanus": context.get("mean_age", 50),
        "boniteediKood": context.get("boniteediKood", "3") if "boniteediKood" in context.columns else "3",
        "kuivendatud": context.get("pct_drained", 0).astype(int) if "pct_drained" in context.columns else 0,
        "kasvukohaKood": context.get("kasvukohaKood", "MO") if "kasvukohaKood" in context.columns else "MO",
        "pindala": context.get("forest_area_ha", 50) if "forest_area_ha" in context.columns else 50,
        "korgus": context.get("mean_height", 15),
    })

    # Encode categoricals (same as training)
    for col in ["peapuuliik", "boniteediKood", "kasvukohaKood"]:
        feat_df[col] = feat_df[col].astype("category").cat.codes

    feat_df["kuivendatud"] = feat_df["kuivendatud"].astype(int)
    feat_df = feat_df.fillna(feat_df.median(numeric_only=True))

    predictions = model.predict(feat_df)

    # Zero out cells with no forest data (mean_age == 0 means no forest)
    no_forest = context.get("mean_age", pd.Series(0, index=context.index)) == 0
    predictions[no_forest.values] = 3.8  # fallback to NIR default

    return np.clip(predictions, 0, None)  # can't be negative (min 0 sequestration)


def score_carbon_learned(context: pd.DataFrame,
                         target_fractions: np.ndarray,
                         config: dict = None) -> np.ndarray:
    """Score carbon using learned GBR for forest + NIR for other transitions.

    Logic:
    - Forest gain: use GBR-predicted tCO2/ha/yr for the target cell
    - Forest loss: subtract GBR-predicted value (lose that sequestration)
    - Wetland/agriculture transitions: use NIR emission factors

    Returns per-cell normalized carbon gain score.
    """
    n = len(context)
    groups = ["forest", "wetland", "agriculture", "grassland"]

    # Current fractions
    current = np.column_stack([context[f"{g}_pct"].values for g in groups])

    # Normalize targets
    urban = context["urban_pct"].values if "urban_pct" in context.columns else np.zeros(n)
    water = context["water_pct"].values if "water_pct" in context.columns else np.zeros(n)
    available_land = np.clip(1.0 - urban - water, 0, 1)

    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]

    delta = targets - current

    # --- Forest component: use GBR ---
    forest_tco2_per_ha = _predict_forest_carbon(context)

    # Forest gain: new forest area × predicted sequestration rate
    forest_gain = np.clip(delta[:, 0], 0, None)
    # Forest loss: losing existing forest × its predicted sequestration
    forest_loss = np.clip(-delta[:, 0], 0, None)

    forest_carbon = (forest_gain - forest_loss) * forest_tco2_per_ha * CELL_AREA_HA

    # --- Non-forest component: use NIR for wetland/agriculture transitions ---
    # Peat fraction
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
    max_wetland_gain = wetland_feasible * 0.3

    # Non-forest transitions (wetland and agriculture)
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
        # Skip forest transitions (handled by GBR above)
        if g_from == "forest" or g_to == "forest":
            continue

        i_from = groups.index(g_from)
        i_to = groups.index(g_to)

        transition_frac = loss_share[:, i_from] * gain_share[:, i_to] * total_change

        if g_to == "wetland":
            transition_frac = np.minimum(transition_frac, max_wetland_gain) * wetland_feasible

        ef = factors["mineral"] * (1 - peat_frac) + factors["peat"] * peat_frac
        non_forest_carbon += transition_frac * ef * CELL_AREA_HA

    # --- Combine and normalize ---
    total_tco2 = forest_carbon + non_forest_carbon

    # Normalize to same scale as other models (0-1 ish)
    SCALE_FACTOR = 1.0 / (10.0 * CELL_AREA_HA)
    return total_tco2 * SCALE_FACTOR
