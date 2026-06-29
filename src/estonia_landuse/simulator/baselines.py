"""Baseline policies for continuous actions (target land-use fractions).

Each baseline returns an (n_cells, 4) array of target fractions:
[forest, wetland, agriculture, grassland]
"""

import numpy as np
import pandas as pd


def _get_current(context: pd.DataFrame) -> np.ndarray:
    """Get current fractions as (n, 4) array."""
    return np.column_stack([
        context["forest_pct"].values,
        context["wetland_pct"].values,
        context["agriculture_pct"].values,
        context["grassland_pct"].values,
    ])


def policy_no_change(context: pd.DataFrame) -> np.ndarray:
    """Keep current land use (no intervention)."""
    return _get_current(context)


def policy_max_forest(context: pd.DataFrame, strength: float = 0.5) -> np.ndarray:
    """Shift agriculture and grassland toward forest."""
    current = _get_current(context)
    target = current.copy()
    # Take from agriculture and grassland, give to forest
    shift_agri = current[:, 2] * strength
    shift_grass = current[:, 3] * strength * 0.3
    target[:, 0] += shift_agri + shift_grass
    target[:, 2] -= shift_agri
    target[:, 3] -= shift_grass
    return target


def policy_restore_wetland(context: pd.DataFrame, strength: float = 0.4) -> np.ndarray:
    """Restore wetland where suitable, taking from agriculture."""
    current = _get_current(context)
    target = current.copy()
    wetland_suit = context["wetland_suitability"].values
    # Shift proportional to suitability
    shift = np.clip(wetland_suit * strength * current[:, 2], 0, current[:, 2])
    target[:, 1] += shift
    target[:, 2] -= shift
    return target


def policy_balanced(context: pd.DataFrame) -> np.ndarray:
    """Balanced conservation: increase forest + wetland at expense of agriculture."""
    current = _get_current(context)
    target = current.copy()
    agri = current[:, 2]
    shift = agri * 0.3
    target[:, 0] += shift * 0.6  # forest gets 60%
    target[:, 1] += shift * 0.4  # wetland gets 40%
    target[:, 2] -= shift
    return target


def policy_biodiversity_priority(context: pd.DataFrame) -> np.ndarray:
    """Shift toward highest biodiversity value per cell (context-dependent)."""
    current = _get_current(context)
    target = current.copy()
    biodiv = context["biodiversity_proxy"].values
    wetland_suit = context["wetland_suitability"].values
    
    # High biodiversity cells: increase forest
    # High wetland suitability: increase wetland
    # Low both: minimal change
    strength = 0.3
    for i in range(len(context)):
        avail = current[i, 2] * strength  # take from agriculture
        if wetland_suit[i] > 0.4:
            target[i, 1] += avail * 0.7
            target[i, 0] += avail * 0.3
        elif biodiv[i] > 0.5:
            target[i, 0] += avail * 0.8
            target[i, 1] += avail * 0.2
        else:
            avail *= 0.3  # less change in low-value cells
            target[i, 0] += avail
        target[i, 2] -= avail if wetland_suit[i] > 0.4 or biodiv[i] > 0.5 else avail
    
    return np.clip(target, 0, None)
