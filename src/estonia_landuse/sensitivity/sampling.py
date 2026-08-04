"""Deterministic, auditable sensitivity manifests for the historical model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .config import (
    BIODIVERSITY_ASSUMPTIONS,
    DEFAULT_SEEDS,
    GLOBAL_BOUNDS,
    GLOBAL_SAMPLE_COUNTS,
    INTERACTION_LEVELS,
    OAT_PARAMETERS,
    SCREEN_BIODIVERSITY_ASSUMPTIONS,
    SCREEN_OAT_PARAMETERS,
    resolve_profile,
)
from .historical_model import SCENARIO_LABELS

EXECUTION_KEY_COLUMNS = ("experiment", "sample_id", "scenario", "seed")
DEFAULT_SCENARIOS = tuple(SCENARIO_LABELS)

INTERACTION_PAIRS: tuple[tuple[str, str], ...] = (
    ("scoring.base_change_cost", "max_changed_pct"),
    ("scoring.agriculture_loss_cost", "scoring.max_agriculture_loss_pct"),
    ("scoring.biodiversity_value.wetland", "constraints.wetland_suit_min_for_restore"),
    ("scoring.connectivity_bonus", "constraints.protected_pct_blocks_change"),
)

INTERACTION_BOUNDS: dict[str, tuple[float, float]] = {
    **GLOBAL_BOUNDS,
    "scoring.biodiversity_value.wetland": (0.0, 1.0),
    "constraints.protected_pct_blocks_change": (0.05, 0.50),
}

_BIODIVERSITY_COMPONENT_INDICES = {"forest": 0, "wetland": 1, "agriculture": 2, "grassland": 3}


def apply_overrides(config: dict, overrides: Mapping[str, object]) -> dict:
    """Deep-copy a historical configuration and replace its dotted-path values."""
    changed = deepcopy(config)
    for dotted_path, value in overrides.items():
        path = dotted_path.split(".")
        if path[:2] == ["scoring", "biodiversity_value"] and len(path) == 3:
            _replace_biodiversity_component(changed, path[2], value)
            continue
        target = changed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
    return changed


def _replace_biodiversity_component(config: dict, component: str, value: object) -> None:
    try:
        index = _BIODIVERSITY_COMPONENT_INDICES[component]
    except KeyError as exc:
        raise ValueError(f"Unknown biodiversity component: {component}") from exc
    values = list(config["scoring"]["biodiversity_value"])
    values[index] = value
    config["scoring"]["biodiversity_value"] = values


def _profile_inputs(
    profile: str, scenarios: Sequence[str] | None, seeds: Sequence[int] | None
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    resolve_profile(profile)
    resolved_scenarios = tuple(DEFAULT_SCENARIOS if scenarios is None else scenarios)
    unknown_scenarios = set(resolved_scenarios).difference(SCENARIO_LABELS)
    if unknown_scenarios:
        raise ValueError(f"unknown historical scenario: {sorted(unknown_scenarios)[0]}")
    resolved_seeds = tuple(DEFAULT_SEEDS[profile] if seeds is None else map(int, seeds))
    if not resolved_scenarios or not resolved_seeds:
        raise ValueError("scenarios and seeds must each be non-empty")
    return resolved_scenarios, resolved_seeds


def _manifest(rows: list[dict[str, object]]) -> pd.DataFrame:
    manifest = pd.DataFrame(rows)
    manifest_run_count(manifest)
    return manifest


def build_baseline_manifest(
    profile: str = "full",
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Build baseline runs across the requested historical scenarios and seeds."""
    scenarios, seeds = _profile_inputs(profile, scenarios, seeds)
    return _manifest(
        [
            {
                "experiment": "baseline",
                "sample_id": "baseline",
                "scenario": scenario,
                "seed": seed,
                "profile": profile,
                "overrides": {},
                "status": "pending",
            }
            for scenario in scenarios
            for seed in seeds
        ]
    )


def build_oat_manifest(
    profile: str = "full",
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Build one-at-a-time changes using only historical configuration paths."""
    scenarios, seeds = _profile_inputs(profile, scenarios, seeds)
    parameters = SCREEN_OAT_PARAMETERS if profile == "screen" else OAT_PARAMETERS
    return _manifest(
        [
            {
                "experiment": "oat",
                "sample_id": f"oat__{parameter}__{value}",
                "scenario": scenario,
                "seed": seed,
                "profile": profile,
                "parameter": parameter,
                "value": value,
                "overrides": {parameter: value},
                "status": "pending",
            }
            for scenario in scenarios
            for parameter, values in parameters.items()
            for value in values
            for seed in seeds
        ]
    )


def build_global_manifest(
    profile: str = "full",
    n_samples: int | None = None,
    sampler_seed: int = 42,
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Build deterministic Latin-hypercube global samples and optimizer replicates."""
    scenarios, seeds = _profile_inputs(profile, scenarios, seeds)
    requested_samples = GLOBAL_SAMPLE_COUNTS[profile] if n_samples is None else n_samples
    if requested_samples < 1:
        raise ValueError("n_samples must be positive")
    full_samples = max(requested_samples, GLOBAL_SAMPLE_COUNTS["full"])
    parameter_names = tuple(GLOBAL_BOUNDS)
    lower_bounds = [GLOBAL_BOUNDS[name][0] for name in parameter_names]
    upper_bounds = [GLOBAL_BOUNDS[name][1] for name in parameter_names]
    samples = qmc.scale(
        qmc.LatinHypercube(d=len(parameter_names), seed=sampler_seed).random(full_samples),
        lower_bounds,
        upper_bounds,
    )[:requested_samples]
    return _manifest(
        [
            {
                "experiment": "global",
                "sample_id": f"global__{sample_index:04d}",
                "scenario": scenario,
                "seed": seed,
                "profile": profile,
                **dict(zip(parameter_names, sample, strict=True)),
                "overrides": dict(zip(parameter_names, sample, strict=True)),
                "status": "pending",
            }
            for sample_index, sample in enumerate(samples)
            for scenario in scenarios
            for seed in seeds
        ]
    )


def build_interaction_manifest(
    profile: str = "full",
    pair: tuple[str, str] | None = None,
    levels: int | None = None,
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Build prespecified two-factor grids, each with exactly two overrides."""
    scenarios, seeds = _profile_inputs(profile, scenarios, seeds)
    pairs = INTERACTION_PAIRS if pair is None else (pair,)
    n_levels = INTERACTION_LEVELS[profile] if levels is None else levels
    if n_levels < 2:
        raise ValueError("levels must be at least two")
    rows: list[dict[str, object]] = []
    for parameter_x, parameter_y in pairs:
        try:
            x_bounds = INTERACTION_BOUNDS[parameter_x]
            y_bounds = INTERACTION_BOUNDS[parameter_y]
        except KeyError as exc:
            raise ValueError(f"No interaction bounds defined for parameter: {exc.args[0]}") from exc
        pair_id = "__".join(parameter.replace(".", "_") for parameter in (parameter_x, parameter_y))
        for x_index, value_x in enumerate(np.linspace(*x_bounds, num=n_levels)):
            for y_index, value_y in enumerate(np.linspace(*y_bounds, num=n_levels)):
                for scenario in scenarios:
                    for seed in seeds:
                        rows.append(
                            {
                                "experiment": "interactions",
                                "sample_id": f"interactions__{pair_id}__{x_index:02d}__{y_index:02d}",
                                "scenario": scenario,
                                "seed": seed,
                                "profile": profile,
                                "parameter_x": parameter_x,
                                "parameter_y": parameter_y,
                                "value_x": float(value_x),
                                "value_y": float(value_y),
                                "overrides": {
                                    parameter_x: float(value_x),
                                    parameter_y: float(value_y),
                                },
                                "status": "pending",
                            }
                        )
    return _manifest(rows)


def build_biodiversity_manifest(
    profile: str = "full",
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Build the prespecified biodiversity-value alternatives and replications."""
    scenarios, seeds = _profile_inputs(profile, scenarios, seeds)
    assumptions = (
        SCREEN_BIODIVERSITY_ASSUMPTIONS if profile == "screen" else BIODIVERSITY_ASSUMPTIONS
    )
    return _manifest(
        [
            {
                "experiment": "biodiversity",
                "sample_id": f"biodiversity__{assumption}",
                "scenario": scenario,
                "seed": seed,
                "profile": profile,
                "biodiversity_assumption": assumption,
                "overrides": {"scoring.biodiversity_value": list(values)},
                "status": "pending",
            }
            for assumption, values in assumptions.items()
            for scenario in scenarios
            for seed in seeds
        ]
    )


def manifest_run_count(frame: pd.DataFrame) -> int:
    """Return optimizer runs after rejecting duplicate execution identities."""
    missing = set(EXECUTION_KEY_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"manifest missing execution keys: {sorted(missing)}")
    if frame.duplicated(list(EXECUTION_KEY_COLUMNS)).any():
        raise ValueError("manifest contains duplicate execution keys")
    return len(frame)


def manifest_summary(frame: pd.DataFrame) -> str:
    """Print and return the exact optimizer-run total before execution."""
    count = manifest_run_count(frame)
    experiments = sorted(frame["experiment"].unique())
    profiles = sorted(frame["profile"].unique()) if "profile" in frame else []
    experiment = ", ".join(experiments)
    profile = ", ".join(profiles) if profiles else "unspecified"
    summary = f"{experiment}: {count} optimizer runs (profile={profile})"
    print(summary)
    return summary


summarize_manifest = manifest_summary
