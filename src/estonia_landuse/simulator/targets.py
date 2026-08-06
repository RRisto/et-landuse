"""Convert prescriptor proposals into physically realizable land-use targets."""

import numpy as np
import pandas as pd

GROUP_COLUMNS = [
    "forest_pct",
    "wetland_pct",
    "agriculture_pct",
    "grassland_pct",
]


def normalize_targets(
    context: pd.DataFrame,
    target_fractions: np.ndarray,
) -> np.ndarray:
    """Scale proposal shares to the currently modelled changeable land."""
    proposals = np.asarray(target_fractions, dtype=float)
    current_total = context[GROUP_COLUMNS].to_numpy(dtype=float).sum(
        axis=1, keepdims=True
    )
    proposal_sum = proposals.sum(axis=1, keepdims=True)
    shares = np.divide(
        proposals,
        proposal_sum,
        out=np.full_like(proposals, 0.25),
        where=proposal_sum > 0,
    )
    return shares * current_total


def realize_targets(
    context: pd.DataFrame,
    target_fractions: np.ndarray,
    config: dict | None = None,
) -> np.ndarray:
    """Project proposals onto hard protected-area and wetland constraints."""
    config = {} if config is None else config
    targets = normalize_targets(context, target_fractions)
    current = context[GROUP_COLUMNS].to_numpy(dtype=float)

    threshold = config.get("constraints", {}).get(
        "protected_pct_blocks_change", 0.3
    )
    protected = context["protected_overlap_pct"].to_numpy(dtype=float) > threshold
    targets[protected] = current[protected]

    wetland_deficit = np.clip(current[:, 1] - targets[:, 1], 0, None)
    repair = (wetland_deficit > 0) & ~protected
    if repair.any():
        other = targets[repair][:, [0, 2, 3]]
        other_total = other.sum(axis=1, keepdims=True)
        reduction = np.divide(
            other,
            other_total,
            out=np.zeros_like(other),
            where=other_total > 0,
        ) * wetland_deficit[repair, None]
        targets[np.ix_(repair, [0, 2, 3])] = other - reduction
        targets[repair, 1] = current[repair, 1]

    suitability = context["wetland_suitability"].to_numpy(dtype=float)
    allowed_gain = np.where(suitability >= 0.3, suitability * 0.3, 0.0)
    wetland_cap = current[:, 1] + allowed_gain
    excess = np.clip(targets[:, 1] - wetland_cap, 0, None)
    capped = (excess > 0) & ~protected
    if capped.any():
        other = targets[capped][:, [0, 2, 3]]
        weights = other.copy()
        empty = weights.sum(axis=1) <= 0
        if empty.any():
            weights[empty] = current[capped][:, [0, 2, 3]][empty]
        weight_sum = weights.sum(axis=1, keepdims=True)
        weights = np.divide(
            weights,
            weight_sum,
            out=np.full_like(weights, 1.0 / 3.0),
            where=weight_sum > 0,
        )
        targets[np.ix_(capped, [0, 2, 3])] = other + weights * excess[capped, None]
        targets[capped, 1] = wetland_cap[capped]

    return targets
