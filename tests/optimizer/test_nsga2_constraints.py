import math

from estonia_landuse.optimizer.nsga2 import (
    constraint_dominates,
    fast_non_dominated_sort,
)


def test_feasible_solution_dominates_better_scoring_infeasible_solution() -> None:
    assert constraint_dominates((10.0, 10.0), (0.0, 0.0), 0.0, 0.1)
    assert not constraint_dominates((0.0, 0.0), (10.0, 10.0), 0.1, 0.0)


def test_lower_violation_dominates_between_infeasible_solutions() -> None:
    assert constraint_dominates((10.0,), (0.0,), 0.1, 0.2)


def test_feasible_solutions_use_pareto_dominance() -> None:
    assert constraint_dominates((1.0, 2.0), (2.0, 2.0), 0.0, 0.0)
    assert not constraint_dominates((2.0, 1.0), (1.0, 2.0), 0.0, 0.0)


def test_equal_infeasible_violations_fall_back_to_objectives() -> None:
    assert constraint_dominates((1.0, 1.0), (2.0, 1.0), 0.5, 0.5)


def test_non_finite_violation_is_infeasible() -> None:
    assert constraint_dominates((99.0,), (0.0,), 0.0, math.nan)
    assert constraint_dominates((99.0,), (0.0,), 1.0, math.inf)


def test_sort_places_feasible_front_before_infeasible_front() -> None:
    metrics = [(10.0, 10.0), (0.0, 0.0), (5.0, 5.0)]
    violations = [0.0, 0.2, 0.0]

    fronts = fast_non_dominated_sort(metrics, violations)

    assert fronts == [[2], [0], [1]]


def test_sort_rejects_mismatched_violation_count() -> None:
    try:
        fast_non_dominated_sort([(1.0,)], [])
    except ValueError as exc:
        assert "constraint_violations" in str(exc)
    else:
        raise AssertionError("Expected mismatched constraint violations to be rejected")
