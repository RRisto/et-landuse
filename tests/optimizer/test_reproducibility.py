import numpy as np
import pandas as pd

from estonia_landuse.optimizer.trainer import train


def _context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cell_id": [1, 2],
            "forest_pct": [0.4, 0.2],
            "wetland_pct": [0.1, 0.2],
            "agriculture_pct": [0.3, 0.4],
            "grassland_pct": [0.1, 0.1],
            "urban_pct": [0.05, 0.05],
            "water_pct": [0.05, 0.05],
            "wetland_suitability": [0.4, 0.8],
            "protected_overlap_pct": [0.0, 0.0],
            "opportunity_cost_proxy": [0.2, 0.4],
        }
    )


def test_training_is_reproducible_with_same_seed() -> None:
    kwargs = {
        "context": _context(),
        "feature_columns": ["wetland_suitability", "opportunity_cost_proxy"],
        "pop_size": 4,
        "n_generations": 2,
        "hidden_size": 2,
        "use_seeds": False,
        "verbose": False,
    }

    first = train(**kwargs, seed=42)
    second = train(**kwargs, seed=42)

    for left, right in zip(first, second, strict=True):
        np.testing.assert_array_equal(left.params, right.params)
        assert left.rank == right.rank
        assert left.crowding == right.crowding
        assert left.metrics == right.metrics
        assert left.constraint_violation == right.constraint_violation


def test_training_changes_with_different_seed() -> None:
    kwargs = {
        "context": _context(),
        "feature_columns": ["wetland_suitability", "opportunity_cost_proxy"],
        "pop_size": 4,
        "n_generations": 1,
        "hidden_size": 2,
        "use_seeds": False,
        "verbose": False,
    }

    first = train(**kwargs, seed=1)
    second = train(**kwargs, seed=2)

    assert any(
        not np.array_equal(left.params, right.params)
        for left, right in zip(first, second, strict=True)
    )
