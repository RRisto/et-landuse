"""NSGA-II: non-dominated sorting and crowding distance for multi-objective optimization."""

import numpy as np

CONSTRAINT_TOLERANCE = 1e-12


def fast_non_dominated_sort(
    metrics_list: list[tuple],
    constraint_violations: list[float] | None = None,
) -> list[list[int]]:
    """Sort population into Pareto fronts.
    
    Args:
        metrics_list: list of tuples, one per individual. All objectives are MINIMIZED.
    
    Returns:
        List of fronts. Each front is a list of indices into the population.
        fronts[0] = rank-0 (Pareto-optimal), fronts[1] = rank-1, etc.
    """
    n = len(metrics_list)
    if constraint_violations is None:
        constraint_violations = [0.0] * n
    elif len(constraint_violations) != n:
        raise ValueError("constraint_violations must match metrics_list length")

    domination_count = [0] * n  # how many dominate me
    dominated_set = [[] for _ in range(n)]  # who I dominate
    fronts = [[]]
    
    for i in range(n):
        for j in range(i + 1, n):
            if constraint_dominates(
                metrics_list[i],
                metrics_list[j],
                constraint_violations[i],
                constraint_violations[j],
            ):
                dominated_set[i].append(j)
                domination_count[j] += 1
            elif constraint_dominates(
                metrics_list[j],
                metrics_list[i],
                constraint_violations[j],
                constraint_violations[i],
            ):
                dominated_set[j].append(i)
                domination_count[i] += 1
    
    # First front: not dominated by anyone
    for i in range(n):
        if domination_count[i] == 0:
            fronts[0].append(i)
    
    # Build subsequent fronts
    k = 0
    while fronts[k]:
        next_front = []
        for i in fronts[k]:
            for j in dominated_set[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    next_front.append(j)
        k += 1
        fronts.append(next_front)
    
    # Remove last empty front
    return fronts[:-1]


def constraint_dominates(
    a: tuple,
    b: tuple,
    violation_a: float,
    violation_b: float,
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> bool:
    """Compare solutions using feasible-first constraint dominance."""
    normalized_a = _normalized_violation(violation_a)
    normalized_b = _normalized_violation(violation_b)
    feasible_a = normalized_a <= tolerance
    feasible_b = normalized_b <= tolerance

    if feasible_a != feasible_b:
        return feasible_a
    if not feasible_a and normalized_a != normalized_b:
        return normalized_a < normalized_b
    return _dominates(a, b)


def _normalized_violation(value: float) -> float:
    value = float(value)
    if not np.isfinite(value):
        return float("inf")
    return max(0.0, value)


def crowding_distance(metrics_list: list[tuple], front: list[int]) -> dict[int, float]:
    """Compute crowding distance for individuals in a front.
    
    Returns dict mapping index → crowding distance.
    """
    n = len(front)
    if n <= 2:
        return {idx: float("inf") for idx in front}
    
    n_objectives = len(metrics_list[0])
    distances = {idx: 0.0 for idx in front}
    
    for obj in range(n_objectives):
        # Sort front by this objective
        sorted_front = sorted(front, key=lambda i: metrics_list[i][obj])
        
        # Boundary individuals get infinite distance
        distances[sorted_front[0]] = float("inf")
        distances[sorted_front[-1]] = float("inf")
        
        # Range for normalization
        obj_range = metrics_list[sorted_front[-1]][obj] - metrics_list[sorted_front[0]][obj]
        if obj_range == 0:
            continue
        
        # Interior individuals
        for k in range(1, n - 1):
            distances[sorted_front[k]] += (
                (metrics_list[sorted_front[k + 1]][obj] - metrics_list[sorted_front[k - 1]][obj])
                / obj_range
            )
    
    return distances


def _dominates(a: tuple, b: tuple) -> bool:
    """Does solution a dominate b? (all objectives minimized)"""
    better_in_any = False
    for ai, bi in zip(a, b, strict=True):
        if ai > bi:
            return False
        if ai < bi:
            better_in_any = True
    return better_in_any
