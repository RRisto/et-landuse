import numpy as np
import pandas as pd

from estonia_landuse.simulator.carbon_nir import score_carbon_nir
from estonia_landuse.simulator.simulator import score_policy


def _normalized_current(context: pd.DataFrame) -> np.ndarray:
    current = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].to_numpy()
    return current / current.sum(axis=1, keepdims=True)


def test_no_change_policy_has_zero_flat_transition_effect(
    minimal_context: pd.DataFrame,
) -> None:
    result = score_policy(
        minimal_context,
        _normalized_current(minimal_context),
        {"carbon_model": "flat"},
    )

    assert abs(result.loc[0, "change_pct"]) < 1e-12
    assert abs(result.loc[0, "carbon_gain"]) < 1e-12
    assert np.isfinite(result.to_numpy()).all()


def test_no_change_policy_has_zero_nir_carbon(minimal_context: pd.DataFrame) -> None:
    result = score_carbon_nir(minimal_context, _normalized_current(minimal_context))

    assert abs(result[0]) < 1e-12


def test_afforestation_and_suitable_peat_rewetting_have_positive_nir_carbon(
    minimal_context: pd.DataFrame,
) -> None:
    context = pd.concat([minimal_context, minimal_context], ignore_index=True)
    context["peat_overlap_pct"] = [0.0, 1.0]
    context["wetland_suitability"] = [0.5, 1.0]
    context[["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]] = [
        [0.0, 0.0, 0.9, 0.0],
        [0.0, 0.0, 0.9, 0.0],
    ]
    targets = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
    )

    result = score_carbon_nir(context, targets)

    assert result[0] > 0
    assert result[1] > result[0]
