"""Seed-42 comparison gate against Notebook 10's saved scenario summary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .historical_model import SCENARIO_LABELS

# Notebook 10 uses presentation labels while the historical runner persists
# stable, machine-readable names. Keeping this mapping explicit makes schema
# drift visible in the comparison output instead of silently dropping fields.
REFERENCE_TO_ARTIFACT_COLUMNS: Mapping[str, str] = {
    "Scenario": "scenario",
    "Status": "feasible",
    "Selection rule": "selection_rule",
    "Policy ID": "policy_id",
    "Biodiversity gain": "biodiversity_gain",
    "Carbon gain": "carbon_gain",
    "Cost": "cost",
    "Changed land": "changed_pct",
    "Agriculture loss": "agriculture_loss",
    "Agriculture gain": "agriculture_gain",
    "Gross agriculture loss": "gross_agriculture_loss",
    "Gross agriculture gain": "gross_agriculture_gain",
    "Wetland gain": "wetland_gain",
    "Constraint violation": "constraint_penalty",
    "Feasible solutions": "feasible_solutions",
    "Front size": "front_size",
}

_EXACT_FIELDS = {
    "Status",
    "Selection rule",
    "Policy ID",
    "Feasible solutions",
    "Front size",
}
_MISMATCH_COLUMNS = ["scenario", "field", "reference", "candidate", "reason"]
_LABEL_TO_SCENARIO = {label: scenario for scenario, label in SCENARIO_LABELS.items()}


def _scenario_key(value: object) -> str:
    text = str(value)
    return _LABEL_TO_SCENARIO.get(text, text)


def _indexed_rows(frame: pd.DataFrame, scenario_column: str, side: str) -> dict[str, pd.Series]:
    keys = frame[scenario_column].map(_scenario_key)
    duplicates = keys[keys.duplicated(keep=False)]
    if not duplicates.empty:
        names = sorted(set(duplicates))
        raise ValueError(f"{side} summary contains duplicate scenarios: {names}")
    return {
        key: frame.iloc[position]
        for position, key in enumerate(keys)
    }


def _feasible(value: object) -> object:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "feasible":
            return True
        if normalized == "infeasible":
            return False
    return value


def _is_missing(value: object) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _values_match(
    field: str,
    reference: object,
    candidate: object,
    *,
    rtol: float,
    atol: float,
) -> bool:
    if _is_missing(reference) or _is_missing(candidate):
        return _is_missing(reference) and _is_missing(candidate)
    if field == "Status":
        return _feasible(reference) == _feasible(candidate)
    if field in _EXACT_FIELDS:
        return reference == candidate
    try:
        return bool(
            np.isclose(
                float(reference),
                float(candidate),
                rtol=rtol,
                atol=atol,
                equal_nan=True,
            )
        )
    except (TypeError, ValueError):
        return reference == candidate


def _mismatch(
    scenario: str,
    field: str,
    reference: Any,
    candidate: Any,
    reason: str,
) -> dict[str, object]:
    return {
        "scenario": scenario,
        "field": field,
        "reference": reference,
        "candidate": candidate,
        "reason": reason,
    }


def compare_reference_summary(
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    rtol: float = 1e-6,
    atol: float = 1e-8,
) -> pd.DataFrame:
    """Return one row per mismatch between Notebook 10 and runner summaries.

    Candidate frames may use either Notebook 10's presentation columns or the
    historical runner's artifact columns. Runtime-only ``Time (s)`` is
    deliberately excluded because it is not a scientific reproduction field.
    """
    if rtol < 0 or atol < 0:
        raise ValueError("rtol and atol must be non-negative")
    if "Scenario" not in reference.columns:
        raise ValueError("reference summary missing scenario column: 'Scenario'")
    candidate_scenario = next(
        (name for name in ("scenario", "Scenario") if name in candidate.columns),
        None,
    )
    if candidate_scenario is None:
        raise ValueError("candidate summary missing scenario column: 'scenario' or 'Scenario'")

    reference_rows = _indexed_rows(reference, "Scenario", "reference")
    candidate_rows = _indexed_rows(candidate, candidate_scenario, "candidate")
    rows: list[dict[str, object]] = []

    for scenario in reference_rows.keys() - candidate_rows.keys():
        rows.append(
            _mismatch(
                scenario,
                "Scenario",
                reference_rows[scenario]["Scenario"],
                None,
                "missing_in_candidate",
            )
        )
    for scenario in candidate_rows.keys() - reference_rows.keys():
        rows.append(
            _mismatch(
                scenario,
                "Scenario",
                None,
                candidate_rows[scenario][candidate_scenario],
                "missing_in_reference",
            )
        )

    for scenario in reference_rows.keys() & candidate_rows.keys():
        reference_row = reference_rows[scenario]
        candidate_row = candidate_rows[scenario]
        for reference_column, artifact_column in REFERENCE_TO_ARTIFACT_COLUMNS.items():
            if reference_column == "Scenario":
                continue
            if reference_column not in reference.columns:
                rows.append(
                    _mismatch(
                        scenario,
                        reference_column,
                        None,
                        None,
                        "missing_reference_field",
                    )
                )
                continue
            candidate_column = next(
                (
                    name
                    for name in (artifact_column, reference_column)
                    if name in candidate.columns
                ),
                None,
            )
            if candidate_column is None:
                rows.append(
                    _mismatch(
                        scenario,
                        reference_column,
                        reference_row[reference_column],
                        None,
                        "missing_candidate_field",
                    )
                )
                continue
            reference_value = reference_row[reference_column]
            candidate_value = candidate_row[candidate_column]
            if not _values_match(
                reference_column,
                reference_value,
                candidate_value,
                rtol=rtol,
                atol=atol,
            ):
                rows.append(
                    _mismatch(
                        scenario,
                        reference_column,
                        reference_value,
                        candidate_value,
                        "value_mismatch",
                    )
                )

    scenario_order = {
        scenario: position
        for position, scenario in enumerate(
            [*reference_rows.keys(), *candidate_rows.keys()]
        )
    }
    field_order = {
        field: position
        for position, field in enumerate(REFERENCE_TO_ARTIFACT_COLUMNS)
    }
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            field_order[str(row["field"])],
        )
    )
    return pd.DataFrame(rows, columns=_MISMATCH_COLUMNS)
