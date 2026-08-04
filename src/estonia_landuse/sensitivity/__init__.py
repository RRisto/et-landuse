"""Sensitivity-analysis adapters for the preserved historical optimizer."""

from .historical_model import (
    SCENARIO_LABELS,
    SELECTION_RULES,
    make_historical_scenario_config,
)

__all__ = [
    "SCENARIO_LABELS",
    "SELECTION_RULES",
    "make_historical_scenario_config",
]
