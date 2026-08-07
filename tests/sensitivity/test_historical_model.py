"""Regression tests for the immutable Notebook 10 scenario contract."""

import hashlib
import json
from pathlib import Path

import pytest

from estonia_landuse.sensitivity.historical_model import (
    SCENARIO_LABELS,
    SELECTION_RULES,
    make_historical_scenario_config,
)
from estonia_landuse.simulator.config import default_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_10 = PROJECT_ROOT / "notebooks" / "10_scenario_comparison.ipynb"
SCENARIO_IDS = (
    "green_maximum",
    "food_security",
    "low_budget",
    "wetland_priority",
    "sustainable_agriculture",
    "balanced",
)


def _normalized_file_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest().upper()


def _notebook_scenarios() -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
    notebook = json.loads(NOTEBOOK_10.read_text(encoding="utf-8"))
    definition_cell = next(
        cell
        for cell in notebook["cells"]
        if "def make_scenario_config" in "".join(cell["source"])
    )
    namespace = {"default_config": default_config}
    exec("".join(definition_cell["source"]), namespace)
    return (
        {
            scenario: namespace["make_scenario_config"](scenario)
            for scenario in SCENARIO_IDS
        },
        namespace["SCENARIOS"],
        namespace["SELECTION_RULES"],
    )


def test_reference_hash_ignores_platform_line_endings(tmp_path: Path) -> None:
    lf_path = tmp_path / "lf.ipynb"
    crlf_path = tmp_path / "crlf.ipynb"
    lf_path.write_bytes(b'{\n  "cells": []\n}\n')
    crlf_path.write_bytes(b'{\r\n  "cells": []\r\n}\r\n')

    assert _normalized_file_sha256(lf_path) == _normalized_file_sha256(crlf_path)


def test_notebook_10_reference_hash_is_unchanged() -> None:
    """Catch an edit to the scientific reference artifact."""
    digest = _normalized_file_sha256(NOTEBOOK_10)
    assert digest == "6207136B9239BCF2E702611C2855B5691896A2299DD7CBC87947DDB2FF2FB827"


def test_historical_configurations_match_notebook_10() -> None:
    """Catch an adapter branch that diverges from the historical experiment."""
    configs, labels, selection_rules = _notebook_scenarios()

    assert SCENARIO_LABELS == labels
    assert SELECTION_RULES == selection_rules
    assert {
        scenario: make_historical_scenario_config(scenario) for scenario in SCENARIO_IDS
    } == configs
    assert configs["wetland_priority"]["optimization"]["fourth_objective"] == "wetland_gain_pct"
    assert (
        configs["sustainable_agriculture"]["optimization"]["fourth_objective"]
        == "agriculture_gain_pct"
    )
    assert configs["balanced"]["max_changed_pct"] == 0.20


def test_historical_configurations_are_independent() -> None:
    """Catch reuse of a mutable historical configuration between runs."""
    initial = make_historical_scenario_config("balanced")
    initial["scoring"]["base_change_cost"] = -1.0

    fresh = make_historical_scenario_config("balanced")

    assert fresh["scoring"]["base_change_cost"] != -1.0


def test_unknown_historical_scenario_is_rejected() -> None:
    """Catch a misspelled scenario silently using the base configuration."""
    with pytest.raises(ValueError, match="unknown historical scenario: typo"):
        make_historical_scenario_config("typo")
