"""Seed policies: train prescriptor networks to imitate target land-use distributions.

Following RHEA from Project Resilience, we inject pre-trained networks so
evolution starts from known-good regions of the search space.
"""

import numpy as np
import pandas as pd

from .prescriptor import Prescriptor, N_OUTPUTS


def create_seed_prescriptors(
    features_norm: np.ndarray,
    context: pd.DataFrame,
    n_epochs: int = 200,
    lr: float = 0.01,
    hidden_size: int = 16,
) -> list[Prescriptor]:
    """Create seed prescriptors trained to imitate simple strategies.
    
    Seeds:
    1. No change — output current fractions (identity)
    2. Max forest — shift everything to forest
    3. Max wetland — shift to wetland where suitable
    4. Balanced — slight increase in forest + wetland at expense of agriculture
    """
    in_size = features_norm.shape[1]
    
    # Get current fractions [forest, wetland, agriculture, grassland]
    current = np.column_stack([
        context["forest_pct"].values,
        context["wetland_pct"].values,
        context["agriculture_pct"].values,
        context["grassland_pct"].values,
    ]).astype(np.float32)
    
    available = np.clip(1.0 - context["urban_pct"].values - context["water_pct"].values, 0, 1)
    
    # Normalize current to sum to 1 (for softmax targets)
    current_sum = current.sum(axis=1, keepdims=True)
    current_norm = np.where(current_sum > 0, current / current_sum, 0.25)
    
    seeds = []
    
    # Seed 1: No change (output = current distribution)
    seeds.append(_train_seed(features_norm, current_norm, in_size, hidden_size, n_epochs, lr))
    
    # Seed 2: Max forest (mostly forest, keep some current)
    target_forest = current_norm.copy()
    target_forest[:, 0] = 0.8  # forest
    target_forest[:, 1] = 0.1  # wetland
    target_forest[:, 2] = 0.05  # agriculture
    target_forest[:, 3] = 0.05  # grassland
    seeds.append(_train_seed(features_norm, target_forest, in_size, hidden_size, n_epochs, lr))
    
    # Seed 3: Restore wetland where suitable
    wetland_suit = context["wetland_suitability"].values
    target_wetland = current_norm.copy()
    # Increase wetland proportionally to suitability, decrease agriculture
    shift = np.clip(wetland_suit * 0.4, 0, current_norm[:, 2])  # take from agri
    target_wetland[:, 1] += shift
    target_wetland[:, 2] -= shift
    # Renormalize
    target_wetland = target_wetland / target_wetland.sum(axis=1, keepdims=True)
    seeds.append(_train_seed(features_norm, target_wetland, in_size, hidden_size, n_epochs, lr))
    
    # Seed 4: Balanced conservation (more forest + wetland, less agriculture)
    target_balanced = current_norm.copy()
    agri_share = target_balanced[:, 2]
    shift = np.clip(agri_share * 0.3, 0, None)
    target_balanced[:, 0] += shift * 0.6  # 60% to forest
    target_balanced[:, 1] += shift * 0.4  # 40% to wetland
    target_balanced[:, 2] -= shift
    target_balanced = target_balanced / target_balanced.sum(axis=1, keepdims=True)
    seeds.append(_train_seed(features_norm, target_balanced, in_size, hidden_size, n_epochs, lr))
    
    return seeds


def _train_seed(
    features: np.ndarray,
    target_fractions: np.ndarray,
    in_size: int,
    hidden_size: int,
    n_epochs: int,
    lr: float,
) -> Prescriptor:
    """Train a prescriptor to output target fractions via gradient descent.
    
    Uses KL-divergence / cross-entropy loss between softmax output and targets.
    """
    p = Prescriptor(in_size, hidden_size)
    n = len(features)
    
    # Ensure targets are valid probability distributions
    target_fractions = np.clip(target_fractions, 1e-8, None)
    target_fractions = target_fractions / target_fractions.sum(axis=1, keepdims=True)
    
    for epoch in range(n_epochs):
        w1, b1, w2, b2 = p._unpack_params()
        
        # Forward
        hidden = np.tanh(features @ w1 + b1)
        logits = hidden @ w2 + b2
        
        # Softmax
        exp_logits = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp_logits / exp_logits.sum(axis=1, keepdims=True)
        
        # Cross-entropy gradient: dL/d_logits = probs - targets
        d_logits = (probs - target_fractions) / n
        
        # Backward
        d_w2 = hidden.T @ d_logits
        d_b2 = d_logits.sum(axis=0)
        d_hidden = d_logits @ w2.T
        d_tanh = d_hidden * (1 - hidden ** 2)
        d_w1 = features.T @ d_tanh
        d_b1 = d_tanh.sum(axis=0)
        
        grad = np.concatenate([d_w1.ravel(), d_b1.ravel(), d_w2.ravel(), d_b2.ravel()])
        p.params -= lr * grad
    
    return p
