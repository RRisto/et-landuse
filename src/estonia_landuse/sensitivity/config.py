"""Immutable compute profiles and prespecified historical sensitivity inputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentProfile:
    """Optimizer budget for one explicitly labelled experiment stage.

    ``use_seeds`` enables baseline-imitating seed prescriptors in the historical
    trainer. It does not remove the integer random seed from a manifest row:
    every profile may still request distinct stochastic repetitions.
    """

    pop_size: int
    n_generations: int
    hidden_size: int
    use_seeds: bool


@dataclass(frozen=True)
class ParameterSpec:
    """A scalar historical configuration value and its full screening grid."""

    path: tuple[str, ...]
    values: tuple[float, ...]
    bounds: tuple[float, float]


TEST_PROFILE = ExperimentProfile(8, 2, 4, False)
SCREEN_PROFILE = ExperimentProfile(80, 60, 16, True)
FULL_PROFILE = ExperimentProfile(200, 200, 16, True)

PROFILES: dict[str, ExperimentProfile] = {
    "test": TEST_PROFILE,
    "screen": SCREEN_PROFILE,
    "full": FULL_PROFILE,
}

# Integer random seeds identify stochastic repetitions for every profile.  The
# ``use_seeds`` flag above independently controls historical seed prescriptors.
# Seed-capable defaults include the published reproduction seed, 42.
DEFAULT_SEEDS: dict[str, tuple[int, ...]] = {
    "test": (0,),
    "screen": (42, 73, 101),
    "full": (42, 73, 101),
}

# These are all dotted paths in the preserved Notebook 10 configuration schema.
OAT_PARAMETERS: dict[str, tuple[float, ...]] = {
    "scoring.base_change_cost": (0.0, 0.1, 0.3, 0.5, 1.0, 2.0),
    "scoring.agriculture_loss_cost": (0.0, 1.0, 2.0, 5.0, 10.0, 15.0),
    "scoring.max_agriculture_loss_pct": (0.10, 0.20, 0.30, 0.40, 0.50),
    "scoring.connectivity_bonus": (0.0, 0.10, 0.20, 0.40),
    "budget_penalty_weight": (0.0, 5.0, 10.0, 20.0, 50.0),
    "max_changed_pct": (0.05, 0.10, 0.15, 0.20, 0.30),
    "constraints.wetland_suit_min_for_restore": (0.05, 0.15, 0.30, 0.40, 0.50),
}

# The screen is deliberately contained by the full confirmation design.
SCREEN_OAT_PARAMETERS: dict[str, tuple[float, ...]] = {
    "scoring.base_change_cost": (0.0, 0.3, 1.0, 2.0),
    "scoring.agriculture_loss_cost": (0.0, 2.0, 10.0, 15.0),
    "scoring.max_agriculture_loss_pct": (0.10, 0.30, 0.50),
    "scoring.connectivity_bonus": (0.0, 0.20, 0.40),
    "budget_penalty_weight": (0.0, 10.0, 50.0),
    "max_changed_pct": (0.05, 0.15, 0.30),
    "constraints.wetland_suit_min_for_restore": (0.05, 0.30, 0.50),
}

OAT_PARAMETER_SPECS: tuple[ParameterSpec, ...] = tuple(
    ParameterSpec(
        path=tuple(parameter.split(".")), values=values, bounds=(min(values), max(values))
    )
    for parameter, values in OAT_PARAMETERS.items()
)

GLOBAL_BOUNDS: dict[str, tuple[float, float]] = {
    "scoring.base_change_cost": (0.0, 1.0),
    "scoring.agriculture_loss_cost": (0.0, 10.0),
    "scoring.max_agriculture_loss_pct": (0.05, 0.50),
    "scoring.connectivity_bonus": (0.0, 0.50),
    "budget_penalty_weight": (0.0, 50.0),
    "max_changed_pct": (0.05, 0.30),
    "constraints.wetland_suit_min_for_restore": (0.05, 0.50),
}

GLOBAL_SAMPLE_COUNTS: dict[str, int] = {"test": 4, "screen": 24, "full": 96}
INTERACTION_LEVELS: dict[str, int] = {"test": 2, "screen": 3, "full": 5}

# Land-use order is forest, wetland, agriculture, grassland throughout the model.
BIODIVERSITY_ASSUMPTIONS: dict[str, tuple[float, float, float, float]] = {
    "current": (0.7, 0.9, 0.2, 0.6),
    "forest_focused": (0.9, 0.8, 0.2, 0.5),
    "open_habitat_focused": (0.6, 0.9, 0.2, 0.8),
    "lower_contrast": (0.6, 0.7, 0.4, 0.6),
}

SCREEN_BIODIVERSITY_ASSUMPTIONS: dict[str, tuple[float, float, float, float]] = {
    "current": BIODIVERSITY_ASSUMPTIONS["current"],
    "forest_focused": BIODIVERSITY_ASSUMPTIONS["forest_focused"],
    "open_habitat_focused": BIODIVERSITY_ASSUMPTIONS["open_habitat_focused"],
}


def resolve_profile(name: str) -> ExperimentProfile:
    """Return a named profile or reject a label that could misstate run scale."""
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown experiment profile: {name}") from exc
