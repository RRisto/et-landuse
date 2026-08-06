from estonia_landuse.optimizer.prescriptor import Prescriptor
from estonia_landuse.optimizer.trainer import _select


def _candidate(metrics: tuple[float, ...], violation: float) -> Prescriptor:
    candidate = Prescriptor(1, 1)
    candidate.metrics = metrics
    candidate.constraint_violation = violation
    return candidate


def test_selection_prefers_feasible_candidate_over_better_objectives() -> None:
    feasible = _candidate((10.0, 10.0, 10.0, 10.0), 0.0)
    infeasible = _candidate((0.0, 0.0, 0.0, 0.0), 0.1)

    selected = _select([infeasible, feasible], 1)

    assert selected == [feasible]
    assert feasible.rank == 0
