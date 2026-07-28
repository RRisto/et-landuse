import numpy as np
import pandas as pd

from estonia_landuse.simulator.carbon_nir import score_carbon_nir
from estonia_landuse.simulator.simulator import score_policy
from estonia_landuse.simulator.targets import realize_targets


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


def test_realize_targets_preserves_unmodelled_residual_land(
    minimal_context: pd.DataFrame,
) -> None:
    context = minimal_context.copy()
    context["grassland_pct"] = 0.05
    current = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].to_numpy()

    realized = realize_targets(context, _normalized_current(context))

    np.testing.assert_allclose(realized, current)
    assert realized.sum() < 1.0 - context.loc[0, "urban_pct"] - context.loc[0, "water_pct"]


def test_realize_targets_blocks_change_in_protected_cells(
    minimal_context: pd.DataFrame,
) -> None:
    context = minimal_context.copy()
    context["protected_overlap_pct"] = 0.8
    proposal = np.array([[1.0, 0.0, 0.0, 0.0]])
    current = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].to_numpy()

    realized = realize_targets(context, proposal)
    outcomes = score_policy(context, proposal, {"carbon_model": "flat"})

    np.testing.assert_allclose(realized, current)
    assert outcomes.loc[0, "constraint_penalty"] == 0.0
    assert outcomes.loc[0, "change_pct"] == 0.0


def test_realize_targets_repairs_wetland_loss_without_changing_capacity(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[1.0, 0.0, 0.0, 0.0]])
    current_total = minimal_context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].sum(axis=1).iloc[0]

    realized = realize_targets(minimal_context, proposal)
    outcomes = score_policy(minimal_context, proposal, {"carbon_model": "flat"})

    assert realized[0, 1] == minimal_context.loc[0, "wetland_pct"]
    assert abs(realized.sum() - current_total) < 1e-12
    assert outcomes.loc[0, "constraint_penalty"] == 0.0


def test_realize_targets_caps_wetland_gain_by_suitability(
    minimal_context: pd.DataFrame,
) -> None:
    context = pd.concat([minimal_context, minimal_context], ignore_index=True)
    context["wetland_suitability"] = [0.0, 0.5]
    proposal = np.array([[0.0, 1.0, 0.0, 0.0]] * 2)
    current_total = context[
        ["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]
    ].sum(axis=1).to_numpy()

    realized = realize_targets(context, proposal)
    outcomes = score_policy(context, proposal, {"carbon_model": "flat"})

    np.testing.assert_allclose(realized[:, 1], [0.1, 0.25])
    np.testing.assert_allclose(realized.sum(axis=1), current_total)
    np.testing.assert_allclose(outcomes["constraint_penalty"], 0.0)
