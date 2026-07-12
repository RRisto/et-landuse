"""NSGA-II evolutionary trainer for prescriptor networks (continuous actions)."""

import numpy as np
import pandas as pd

from .prescriptor import Prescriptor
from .nsga2 import fast_non_dominated_sort, crowding_distance
from ..simulator.simulator import summarize_policy


def train(
    context: pd.DataFrame,
    feature_columns: list[str],
    pop_size: int = 100,
    n_generations: int = 100,
    hidden_size: int = 16,
    p_mutation: float = 0.2,
    mutation_factor: float = 0.1,
    config: dict | None = None,
    use_seeds: bool = True,
    verbose: bool = True,
) -> list[Prescriptor]:
    """Run NSGA-II evolution. Returns the final population sorted by rank.
    
    Args:
        context: Feature table with derived features.
        feature_columns: Which columns to feed as input to the neural network.
        pop_size: Population size.
        n_generations: How many generations to evolve.
        hidden_size: Hidden layer size.
        p_mutation: Probability of mutating each weight.
        mutation_factor: Std dev of Gaussian mutation noise.
        config: Simulator config.
        use_seeds: If True, inject baseline-imitating seeds into initial population.
        verbose: Print progress.
    
    Returns:
        List of Prescriptor objects (final population), sorted by Pareto rank.
    """
    from .seeds import create_seed_prescriptors
    
    in_size = len(feature_columns)
    features = context[feature_columns].values.astype(np.float32)
    
    # Normalize features for the network
    feat_mean = features.mean(axis=0)
    feat_std = features.std(axis=0)
    feat_std[feat_std == 0] = 1.0
    features_norm = (features - feat_mean) / feat_std
    
    # Initialize population
    if use_seeds:
        seeds = create_seed_prescriptors(features_norm, context, hidden_size=hidden_size)
        if verbose:
            print(f"Created {len(seeds)} seed prescriptors")
        n_random = max(0, pop_size - len(seeds))
        population = seeds + [Prescriptor(in_size, hidden_size) for _ in range(n_random)]
    else:
        population = [Prescriptor(in_size, hidden_size) for _ in range(pop_size)]
    
    # Evaluate initial population and assign ranks/crowding
    _evaluate_population(population, features_norm, context, config)
    population = _select(population, pop_size)
    
    for gen in range(n_generations):
        # Create offspring
        offspring = _create_offspring(population, pop_size, p_mutation, mutation_factor)
        _evaluate_population(offspring, features_norm, context, config)
        
        # Combine and select
        combined = population + offspring
        population = _select(combined, pop_size)
        
        if verbose and (gen + 1) % 10 == 0:
            front0 = [p for p in population if p.rank == 0]
            avg_metrics = np.mean([p.metrics for p in front0], axis=0)
            print(f"Gen {gen+1:>3d} | Front-0: {len(front0):>3d} | "
                  f"Avg: bio={-avg_metrics[0]:.4f} carbon={-avg_metrics[1]:.4f} "
                  f"cost={avg_metrics[2]:.4f} change={avg_metrics[3]:.1%}")
    
    population.sort(key=lambda p: (p.rank, -getattr(p, "crowding", 0)))
    return population


def _evaluate_population(population, features_norm, context, config):
    """Evaluate fitness of each individual."""
    for p in population:
        target_fractions = p.prescribe(features_norm)
        summary = summarize_policy(context, target_fractions, config)
        
        # NSGA-II minimizes all objectives
        p.metrics = (
            -summary["biodiversity_gain"],
            -summary["carbon_gain"],
            summary["cost"],
            summary["changed_pct"],
        )


def _create_offspring(population, n_offspring, p_mutation, mutation_factor):
    """Create offspring via tournament selection + crossover + mutation."""
    offspring = []
    for _ in range(n_offspring):
        p1 = _tournament_select(population)
        p2 = _tournament_select(population)
        
        # Uniform crossover
        child = p1.copy()
        mask = np.random.rand(child.n_params) < 0.5
        child.params[mask] = p2.params[mask]
        
        # Gaussian mutation
        mut_mask = np.random.rand(child.n_params) < p_mutation
        child.params[mut_mask] += np.random.randn(mut_mask.sum()) * mutation_factor
        
        offspring.append(child)
    return offspring


def _tournament_select(population, k=3):
    """Tournament selection: pick k random, prefer lower rank, then higher crowding."""
    candidates = np.random.choice(len(population), size=min(k, len(population)), replace=False)
    best = min(candidates, key=lambda i: (
        population[i].rank if population[i].rank is not None else 999,
        -(getattr(population[i], "crowding", 0) or 0),
    ))
    return population[best]


def _select(combined, pop_size):
    """NSGA-II selection: fill next generation by fronts + crowding distance."""
    metrics_list = [p.metrics for p in combined]
    fronts = fast_non_dominated_sort(metrics_list)
    
    next_gen = []
    for rank, front in enumerate(fronts):
        # Compute crowding distance for ALL fronts
        distances = crowding_distance(metrics_list, front)
        for idx in front:
            combined[idx].rank = rank
            combined[idx].crowding = distances[idx]
        
        if len(next_gen) + len(front) <= pop_size:
            next_gen.extend([combined[idx] for idx in front])
        else:
            sorted_front = sorted(front, key=lambda i: -distances[i])
            remaining = pop_size - len(next_gen)
            next_gen.extend([combined[idx] for idx in sorted_front[:remaining]])
            break
    
    return next_gen
