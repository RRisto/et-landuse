"""Aggregate reporting metrics for constrained land-use policy targets."""

import numpy as np
import pandas as pd

from .config import default_config
from .simulator import summarize_policy


def realize_targets(
    context: pd.DataFrame, target_fractions: np.ndarray, config: dict | None = None
) -> np.ndarray:
    """Normalize targets and apply the constraints used by scenario-map reporting."""
    if config is None:
        config = default_config()

    current = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].to_numpy()
    available_land = np.clip(
        1.0 - context["urban_pct"].to_numpy() - context["water_pct"].to_numpy(),
        0,
        1,
    )
    target_sum = target_fractions.sum(axis=1, keepdims=True)
    target_sum = np.where(target_sum > 0, target_sum, 1.0)
    targets = target_fractions / target_sum * available_land[:, None]

    protected_threshold = config.get("constraints", {}).get(
        "protected_pct_blocks_change", 0.15
    )
    is_protected = (
        context["protected_overlap_pct"].to_numpy() > protected_threshold
    )
    targets[is_protected] = current[is_protected]

    wetland_loss = targets[:, 1] < current[:, 1]
    targets[wetland_loss, 1] = current[wetland_loss, 1]
    return targets


def summarize_policy_reporting(
    context: pd.DataFrame, target_fractions: np.ndarray, config: dict | None = None
) -> dict[str, float]:
    """Return policy summary plus constrained agriculture and wetland deltas."""
    if config is None:
        config = default_config()

    targets = realize_targets(context, target_fractions, config)
    current = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].to_numpy()
    delta = targets - current
    current_agriculture = current[:, 2].sum()

    def agriculture_fraction(value: float) -> float:
        return value / current_agriculture if current_agriculture > 0 else 0.0

    base = summarize_policy(context, target_fractions, config)
    return {
        **base,
        "agriculture_loss": agriculture_fraction(np.clip(-delta[:, 2], 0, None).sum()),
        "agriculture_gain": agriculture_fraction(max(0.0, delta[:, 2].sum())),
        "gross_agriculture_gain": agriculture_fraction(
            np.clip(delta[:, 2], 0, None).sum()
        ),
        "wetland_gain": np.clip(delta[:, 1], 0, None).mean(),
    }
