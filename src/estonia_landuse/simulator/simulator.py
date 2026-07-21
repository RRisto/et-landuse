"""V2 land-use simulator: continuous actions (target land-use fractions).

The prescriptor outputs target fractions for each changeable land-use group.
The simulator computes outcomes based on the transition from current to target.
"""

import numpy as np
import pandas as pd

from .actions import LAND_USE_GROUPS, CHANGEABLE_GROUPS, FIXED_GROUPS
from .carbon_nir import score_carbon_nir
from .config import default_config


def score_policy(context: pd.DataFrame, target_fractions: np.ndarray,
                 config: dict | None = None) -> pd.DataFrame:
    """Score a policy: compute per-cell outcomes from land-use transitions.
    
    Args:
        context: Feature table (one row per cell), must include derived features.
        target_fractions: Array (n_cells, 4) of target fractions for
            [forest, wetland, agriculture, grassland]. Values 0-1, should sum to
            available land (1 - urban_pct - water_pct) per cell.
        config: Simulator config dict.
    
    Returns:
        DataFrame with per-cell outcomes:
            biodiversity_gain, carbon_gain, cost, change_pct
    """
    if config is None:
        config = default_config()
    
    n = len(context)
    sc = config.get("scoring", {})
    
    # Current fractions for changeable groups
    current = np.column_stack([
        context["forest_pct"].values,
        context["wetland_pct"].values,
        context["agriculture_pct"].values,
        context["grassland_pct"].values,
    ])
    
    # Fixed fractions (urban + water = land the prescriptor can't touch)
    urban = context["urban_pct"].values
    water = context["water_pct"].values
    available_land = np.clip(1.0 - urban - water, 0, 1)
    
    # Normalize target fractions to sum to available land per cell
    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]
    
    # Compute transitions (delta per group)
    delta = targets - current  # positive = increase, negative = decrease
    
    # Change percentage: sum of all positive changes / available land
    change_pct = np.abs(delta).sum(axis=1) / (2.0 * np.where(available_land > 0, available_land, 1.0))
    # Divide by 2 because each unit moved appears as +1 and -1
    
    # --- Carbon gain ---
    # Select carbon model based on config
    carbon_model = config.get("carbon_model", "auto")
    # "auto" = use v1.5 if columns present, else flat
    # "flat" = always use flat density lookup
    # "nir" = use NIR-calibrated model (Estonian emission factors)
    # "learned" = use trained GBR for forest + NIR for non-forest transitions

    if carbon_model == "nir":
        # NIR-calibrated: uses Estonian NIR emission factors by transition type
        carbon_gain = score_carbon_nir(context, target_fractions)
    elif carbon_model == "learned":
        # Learned model: GBR for forest sequestration + NIR for other transitions
        from .carbon_learned import score_carbon_learned
        carbon_gain = score_carbon_learned(context, target_fractions, config)
    else:
        # V1.5 or flat model (existing logic)
        carbon_v15 = config.get("carbon_v1_5", {})
        use_v15 = carbon_v15.get("enabled", False) and carbon_model != "flat"
        blend = carbon_v15.get("blend", 1.0)
        score_cols = carbon_v15.get("score_columns", {})

        has_v15_cols = (
            use_v15
            and score_cols.get("carbon_stock") in context.columns
            and score_cols.get("afforest") in context.columns
        )

        # Old flat model: transition TO higher-carbon types = positive gain
        carbon_density = np.array(sc.get("carbon_density", [0.8, 1.0, 0.3, 0.4]))
        # [forest, wetland, agriculture, grassland]
        carbon_gain_flat = (delta * carbon_density[None, :]).sum(axis=1)

        if has_v15_cols and blend > 0:
            # V1.5 model: carbon gain is weighted by per-cell action potentials
            # Forest increase weighted by afforestation potential
            afforest_score = context[score_cols["afforest"]].fillna(0).values
            # Wetland increase weighted by wetland restoration potential
            restore_score = context[score_cols["restore_wetland"]].fillna(0).values
            # Protection benefit for preserving existing carbon stock
            carbon_stock = context[score_cols["carbon_stock"]].fillna(0).values

            forest_gain_v15 = np.clip(delta[:, 0], 0, None) * afforest_score
            wetland_gain_v15 = np.clip(delta[:, 1], 0, None) * restore_score
            # Preservation bonus: NOT changing high-carbon cells
            preserve_bonus = (1.0 - change_pct) * carbon_stock * 0.1
            # Loss penalty: reducing forest/wetland in high-stock cells
            forest_loss_v15 = np.clip(-delta[:, 0], 0, None) * carbon_stock * 0.8
            wetland_loss_v15 = np.clip(-delta[:, 1], 0, None) * carbon_stock * 1.0

            carbon_gain_v15 = (
                forest_gain_v15 + wetland_gain_v15 + preserve_bonus
                - forest_loss_v15 - wetland_loss_v15
            )
            # Blend old and new
            carbon_gain = (1.0 - blend) * carbon_gain_flat + blend * carbon_gain_v15
        else:
            carbon_gain = carbon_gain_flat
    
    # --- Biodiversity gain ---
    # Increasing natural/semi-natural land at expense of agriculture = positive
    biodiversity_value = np.array(sc.get("biodiversity_value", [0.7, 0.9, 0.2, 0.6]))
    biodiversity_gain = (delta * biodiversity_value[None, :]).sum(axis=1)
    
    # Gate wetland biodiversity reward by suitability (same as 03.2)
    # Only give biodiversity credit for wetland gain where physically feasible
    wetland_suit = context["wetland_suitability"].values
    wetland_gain_raw = np.clip(delta[:, 1], 0, None)
    # Remove ungated wetland reward, add gated version
    biodiversity_gain -= wetland_gain_raw * biodiversity_value[1]
    biodiversity_gain += wetland_gain_raw * biodiversity_value[1] * wetland_suit

    # Bonus for increasing land near protected areas
    protected = context["protected_overlap_pct"].values
    biodiversity_gain += sc.get("connectivity_bonus", 0.2) * change_pct * protected
    
    # --- Cost ---
    # Cost of change depends on: amount changed, opportunity cost, and what you're converting
    opp_cost = context["opportunity_cost_proxy"].values
    base_cost = sc.get("base_change_cost", 0.3)
    
    # Converting agriculture is expensive (food production loss)
    agriculture_loss = np.clip(-delta[:, 2], 0, None)  # agriculture decrease
    agriculture_penalty = sc.get("agriculture_loss_cost", 2.0) * agriculture_loss
    
    # Hard cap: can't lose more than X% of cell's original agriculture
    max_agri_loss = sc.get("max_agriculture_loss_pct", 0.3)
    current_agri = current[:, 2]
    max_allowed_loss = current_agri * max_agri_loss
    excess_agri_loss = np.clip(agriculture_loss - max_allowed_loss, 0, None)
    agriculture_penalty += excess_agri_loss * 20.0  # very heavy penalty for exceeding cap
    
    cost = base_cost * change_pct + opp_cost * change_pct + agriculture_penalty
    
    # --- Constraint penalties ---
    penalty = np.zeros(n)
    
    # Protected areas: NO change allowed (hard constraint)
    protected = context["protected_overlap_pct"].values
    protected_threshold = config.get("constraints", {}).get("protected_pct_blocks_change", 0.3)
    is_protected = protected > protected_threshold
    # Zero out ALL scores for protected cells — no benefit from changing them
    biodiversity_gain[is_protected] = 0.0
    carbon_gain[is_protected] = 0.0
    change_pct[is_protected] = 0.0  # don't count toward budget
    # Massive penalty proportional to how much change is attempted
    penalty[is_protected] += np.abs(delta[is_protected]).sum(axis=1) * 100.0
    
    # Penalize converting wetland to forest (ecologically wrong)
    wetland_loss = np.clip(-delta[:, 1], 0, None)
    forest_gain_where_wetland_lost = np.clip(delta[:, 0], 0, None) * (wetland_loss > 0.01).astype(float)
    penalty += forest_gain_where_wetland_lost * 10.0
    
    # Penalize converting existing high-value wetland to anything
    is_wetland_cell = context["wetland_pct"].values > 0.3
    penalty[is_wetland_cell] += wetland_loss[is_wetland_cell] * 10.0
    
    # Penalize cells that increase BOTH forest and wetland simultaneously
    # (physically contradictory — same land can't become both)
    forest_gain = np.clip(delta[:, 0], 0, None)
    wetland_gain = np.clip(delta[:, 1], 0, None)
    dual_increase = np.minimum(forest_gain, wetland_gain)  # the overlapping part
    penalty += dual_increase * 15.0
    
    # Penalize wetland increase where suitability is low
    wetland_suit = context["wetland_suitability"].values
    wetland_gain = np.clip(delta[:, 1], 0, None)
    # Only allow wetland gain up to suitability * max_wetland_gain_factor
    max_allowed_gain = wetland_suit * 0.3  # max 30% wetland gain even in best cells
    excess_wetland = np.clip(wetland_gain - max_allowed_gain, 0, None)
    penalty += excess_wetland * 20.0
    # Also penalize any gain where suitability < 0.3 (not feasible at all)
    infeasible = (wetland_suit < 0.3) & (wetland_gain > 0.01)
    penalty[infeasible] += wetland_gain[infeasible] * 30.0
    
    # Negative fractions are invalid
    penalty += np.clip(-targets, 0, None).sum(axis=1) * 10.0
    
    return pd.DataFrame({
        "biodiversity_gain": biodiversity_gain,
        "carbon_gain": carbon_gain,
        "cost": cost,
        "constraint_penalty": penalty,
        "change_pct": change_pct,
    })


def summarize_policy(context: pd.DataFrame, target_fractions: np.ndarray,
                     config: dict | None = None) -> dict:
    """Score a policy and return aggregate metrics."""
    if config is None:
        config = default_config()
    
    outcomes = score_policy(context, target_fractions, config)
    changed_pct = outcomes["change_pct"].mean()
    
    # Budget penalty
    max_changed = config.get("max_changed_pct", 0.20)
    budget_weight = config.get("budget_penalty_weight", 10.0)
    budget_penalty = max(0.0, changed_pct - max_changed) * budget_weight
    
    # Food security: penalize total agriculture loss across the county
    # Can't reduce total agriculture area by more than max_total_agri_loss_pct
    max_total_agri_loss = config.get("max_total_agri_loss_pct", 0.20)
    current_agri_total = context["agriculture_pct"].values.sum()
    if current_agri_total > 0:
        # Compute target agriculture fractions
        urban = context["urban_pct"].values
        water = context["water_pct"].values
        available_land = np.clip(1.0 - urban - water, 0, 1)
        target_sum = target_fractions.sum(axis=1, keepdims=True)
        target_sum = np.where(target_sum > 0, target_sum, 1.0)
        targets = target_fractions / target_sum * available_land[:, None]
        target_agri_total = targets[:, 2].sum()  # agriculture is index 2
        agri_loss_frac = (current_agri_total - target_agri_total) / current_agri_total
        excess_agri_loss = max(0.0, agri_loss_frac - max_total_agri_loss)
        agri_penalty_weight = config.get("total_agri_loss_penalty_weight", 20.0)
        budget_penalty += excess_agri_loss * agri_penalty_weight
    
    return {
        "biodiversity_gain": outcomes["biodiversity_gain"].mean(),
        "carbon_gain": outcomes["carbon_gain"].mean(),
        "cost": outcomes["cost"].mean() + budget_penalty,
        "constraint_penalty": outcomes["constraint_penalty"].mean(),
        "changed_pct": changed_pct,
    }
