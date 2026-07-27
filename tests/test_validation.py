import numpy as np
import pandas as pd
import pytest

from estonia_landuse.optimizer.trainer import train
from estonia_landuse.simulator.simulator import score_policy
from estonia_landuse.validation import resolve_rng


@pytest.mark.parametrize(
    ("targets", "message"),
    [
        (np.ones((1, 3)), r"target_fractions.*\(1, 4\)"),
        (np.ones((2, 4)), "row count"),
        (np.array([[0.5, -0.1, 0.4, 0.2]]), "non-negative"),
        (np.zeros((1, 4)), "positive row totals"),
        (np.array([[0.5, np.nan, 0.3, 0.2]]), "finite"),
    ],
)
def test_score_policy_rejects_invalid_targets(
    minimal_context: pd.DataFrame,
    targets: np.ndarray,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        score_policy(minimal_context, targets)


def test_score_policy_names_missing_context_columns(minimal_context: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="opportunity_cost_proxy"):
        score_policy(minimal_context.drop(columns="opportunity_cost_proxy"), np.ones((1, 4)))


def test_train_rejects_non_finite_features(minimal_context: pd.DataFrame) -> None:
    context = minimal_context.assign(wetland_suitability=np.nan)

    with pytest.raises(ValueError) as exc_info:
        train(context, ["wetland_suitability"], pop_size=4, n_generations=0, verbose=False)
    assert "wetland_suitability" in str(exc_info.value)
    assert "finite" in str(exc_info.value)


def test_train_names_missing_feature(minimal_context: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="missing_feature"):
        train(minimal_context, ["missing_feature"], pop_size=4, n_generations=0, verbose=False)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"pop_size": 1}, "pop_size"),
        ({"n_generations": -1}, "n_generations"),
    ],
)
def test_train_rejects_invalid_hyperparameters(
    minimal_context: pd.DataFrame,
    kwargs: dict,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        train(
            minimal_context,
            ["wetland_suitability"],
            use_seeds=False,
            verbose=False,
            **kwargs,
        )


def test_rng_rejects_seed_and_generator_together() -> None:
    with pytest.raises(ValueError, match="seed.*rng"):
        resolve_rng(seed=42, rng=np.random.default_rng(42))
