"""Shared validation and random-generator helpers."""

from collections.abc import Iterable

import numpy as np
import pandas as pd


def validate_context_columns(context: pd.DataFrame, required: Iterable[str]) -> None:
    """Require named, finite numeric context columns."""
    required_columns = list(dict.fromkeys(required))
    missing = [column for column in required_columns if column not in context.columns]
    if missing:
        raise ValueError(f"context is missing required columns: {', '.join(missing)}")

    non_finite = []
    for column in required_columns:
        values = pd.to_numeric(context[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            non_finite.append(column)
    if non_finite:
        raise ValueError(f"context columns must contain finite values: {', '.join(non_finite)}")


def validate_target_fractions(
    context: pd.DataFrame,
    target_fractions: np.ndarray,
) -> np.ndarray:
    """Validate and return land-use targets as a float array."""
    targets = np.asarray(target_fractions, dtype=float)
    expected_shape = (len(context), 4)
    if targets.ndim != 2 or targets.shape[1:] != (4,):
        raise ValueError(
            f"target_fractions must have shape (n_rows, 4); expected {expected_shape}"
        )
    if targets.shape[0] != len(context):
        raise ValueError(
            "target_fractions row count must match context "
            f"({targets.shape[0]} != {len(context)})"
        )
    if not np.isfinite(targets).all():
        raise ValueError("target_fractions must contain only finite values")
    if (targets < 0).any():
        raise ValueError("target_fractions must be non-negative")
    if (targets.sum(axis=1) <= 0).any():
        raise ValueError("target_fractions must have positive row totals")
    return targets


def resolve_rng(
    seed: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.random.Generator:
    """Return one generator, rejecting ambiguous random-state configuration."""
    if seed is not None and rng is not None:
        raise ValueError("Provide either seed or rng, not both")
    if rng is not None:
        if not isinstance(rng, np.random.Generator):
            raise TypeError("rng must be a numpy.random.Generator")
        return rng
    return np.random.default_rng(seed)
