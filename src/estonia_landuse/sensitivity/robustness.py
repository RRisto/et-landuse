"""Cross-experiment robustness synthesis for historical sensitivity artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile

import numpy as np
import pandas as pd

from .analysis import rank_parameter_importance, summarize_interaction_noise
from .historical_model import SCENARIO_LABELS
from .runner import (
    ARTIFACT_SCHEMA_VERSION,
    _canonical_json,
    _code_fingerprint,
    _input_fingerprint,
    _manifest_design,
)
from .sampling import EXECUTION_KEY_COLUMNS

IDENTITY_COLUMNS = (
    "profile",
    "input_fingerprint",
    "code_fingerprint",
    "artifact_schema_version",
)
ARTIFACT_IDENTITY_COLUMNS = (
    "artifact_schema_version",
    "input_fingerprint",
    "configuration_fingerprint",
    "code_fingerprint",
    "run_signature",
)
EXPERIMENTS = ("baseline", "oat", "global", "interactions", "biodiversity")
LAND_USES = ("forest", "wetland", "agriculture", "grassland")
OUTCOMES = ("biodiversity_gain", "carbon_gain", "cost", "changed_pct")
MIN_HELD_OUT_R2 = 0.25
PERMUTATION_UNCERTAINTY_Z = 2.0
MAX_INTERACTION_TO_BASELINE_NOISE = 1.0
_POST_RUN_MANIFEST_FIELDS = (
    "worker_pid",
    "training_seconds",
    "optimizer_cpu_seconds",
    "front_evaluation_seconds",
    "artifact_writing_seconds",
    "total_duration_seconds",
)


@dataclass(frozen=True)
class ArtifactInventory:
    """Validated complete artifacts and explicit exclusions for one cohort."""

    complete: pd.DataFrame
    incomplete: pd.DataFrame
    identity: tuple[object, ...] | None


def _target_path(metrics_path: Path) -> Path:
    return metrics_path.with_suffix(".npz")


def _npz_matches(metrics: pd.Series, path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing_targets"
    try:
        with np.load(path) as archive:
            if "targets" not in archive.files or "current_fractions" not in archive.files:
                return False, "incomplete_targets"
            for column in ARTIFACT_IDENTITY_COLUMNS:
                if column not in archive.files or archive[column].item() != metrics[column]:
                    return False, "identity_mismatch"
    except (BadZipFile, EOFError, KeyError, OSError, ValueError):
        return False, "unreadable_targets"
    return True, ""


def current_artifact_identity(
    context: pd.DataFrame, feature_columns: Iterable[str], profile: str
) -> tuple[object, ...]:
    """Return the cohort identity that the current runner would write."""
    columns = tuple(feature_columns)
    return (
        profile,
        _input_fingerprint(context, columns),
        _code_fingerprint(),
        ARTIFACT_SCHEMA_VERSION,
    )


def inventory_artifacts(
    output_root: Path | str,
    profile: str,
    *,
    expected_identity: tuple[object, ...] | None = None,
) -> ArtifactInventory:
    """Inventory complete artifact pairs without mixing execution identities.

    Configuration fingerprints are intentionally run-specific. The cohort identity
    is the profile plus input, code, and artifact-schema fingerprints.
    """
    root = Path(output_root)
    complete_rows: list[dict[str, object]] = []
    incomplete_rows: list[dict[str, object]] = []
    for metrics_path in sorted((root / "runs").rglob("seed_*.parquet")):
        try:
            frame = pd.read_parquet(metrics_path)
        except (OSError, ValueError):
            incomplete_rows.append({"metrics_path": str(metrics_path), "reason": "unreadable_metrics"})
            continue
        if len(frame) != 1:
            incomplete_rows.append({"metrics_path": str(metrics_path), "reason": "invalid_metrics_rows"})
            continue
        row = frame.iloc[0]
        required = {*EXECUTION_KEY_COLUMNS, *IDENTITY_COLUMNS, *ARTIFACT_IDENTITY_COLUMNS}
        if not required.issubset(frame.columns):
            incomplete_rows.append({"metrics_path": str(metrics_path), "reason": "missing_metadata"})
            continue
        if str(row["profile"]) != profile:
            continue
        targets_path = _target_path(metrics_path)
        matches, reason = _npz_matches(row, targets_path)
        record = row.to_dict() | {
            "metrics_path": str(metrics_path),
            "targets_path": str(targets_path),
        }
        if matches:
            complete_rows.append(record)
        else:
            incomplete_rows.append(record | {"reason": reason})

    complete = pd.DataFrame(complete_rows)
    incomplete = pd.DataFrame(incomplete_rows)
    identity: tuple[object, ...] | None = None
    if not complete.empty:
        identities = complete[list(IDENTITY_COLUMNS)].drop_duplicates()
        if expected_identity is not None:
            if len(expected_identity) != len(IDENTITY_COLUMNS):
                raise ValueError("expected artifact identity has the wrong number of fields")
            matching = pd.Series(True, index=complete.index)
            for column, value in zip(IDENTITY_COLUMNS, expected_identity, strict=True):
                matching &= complete[column].eq(value)
            incompatible = complete.loc[~matching].assign(reason="incompatible_identity")
            incomplete = pd.concat([incomplete, incompatible], ignore_index=True)
            complete = complete.loc[matching].reset_index(drop=True)
            identity = expected_identity if not complete.empty else None
        elif len(identities) != 1:
            records = identities.to_dict("records")
            raise ValueError(f"profile {profile!r} contains multiple artifact identities: {records}")
        else:
            identity = tuple(identities.iloc[0][column] for column in IDENTITY_COLUMNS)
    return ArtifactInventory(complete=complete, incomplete=incomplete, identity=identity)


def _manifest_row_design_json(row: pd.Series | dict[str, object]) -> str:
    values = row.to_dict() if isinstance(row, pd.Series) else dict(row)
    overrides = values.get("overrides")
    if isinstance(overrides, str):
        try:
            values["overrides"] = json.loads(overrides)
        except json.JSONDecodeError:
            pass
    # These columns are initialized to None before runner metadata is computed,
    # then filled only after the artifact pair has been written.
    for field in _POST_RUN_MANIFEST_FIELDS:
        values[field] = None
    return _canonical_json(_manifest_design(values))


def _latest_manifests(
    output_root: Path, profile: str
) -> dict[str, pd.DataFrame]:
    manifests: dict[str, pd.DataFrame] = {}
    for experiment in EXPERIMENTS:
        path = output_root / "manifests" / f"{experiment}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        required = {*EXECUTION_KEY_COLUMNS, "profile"}
        if not required.issubset(frame.columns):
            continue
        frame = frame.loc[frame["profile"].astype(str).eq(profile)].copy()
        if frame.empty:
            continue
        if frame.duplicated(list(EXECUTION_KEY_COLUMNS)).any():
            raise ValueError(f"latest {experiment} manifest contains duplicate execution keys")
        frame["manifest_design_json"] = [
            _manifest_row_design_json(row) for _, row in frame.iterrows()
        ]
        manifests[experiment] = frame.reset_index(drop=True)
    return manifests


def _filter_to_latest_manifests(
    artifacts: pd.DataFrame,
    manifests: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if artifacts.empty:
        return artifacts.copy(), pd.DataFrame()
    expected: dict[tuple[object, ...], str] = {}
    for manifest in manifests.values():
        for row in manifest.to_dict("records"):
            key = tuple(row[column] for column in EXECUTION_KEY_COLUMNS)
            expected[key] = str(row["manifest_design_json"])
    compatible_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []
    for row in artifacts.to_dict("records"):
        key = tuple(row[column] for column in EXECUTION_KEY_COLUMNS)
        expected_design = expected.get(key)
        if expected_design is None:
            excluded_rows.append(row | {"reason": "not_in_latest_manifest"})
        elif row.get("manifest_design_json") != expected_design:
            excluded_rows.append(row | {"reason": "manifest_design_mismatch"})
        else:
            compatible_rows.append(row)
    compatible = pd.DataFrame(compatible_rows, columns=artifacts.columns)
    excluded = pd.DataFrame(excluded_rows)
    return compatible, excluded


def _comparison_group_report(
    manifest: pd.DataFrame | None, artifacts: pd.DataFrame
) -> pd.DataFrame:
    columns = (
        "comparison_key",
        "sample_id",
        "seed",
        "expected_scenarios",
        "complete_scenarios",
        "missing_scenarios",
        "status",
    )
    if manifest is None or manifest.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for (sample_id, seed), expected_group in manifest.groupby(
        ["sample_id", "seed"], sort=False
    ):
        expected = tuple(sorted(expected_group["scenario"].astype(str).unique()))
        actual_group = artifacts.loc[
            artifacts["sample_id"].eq(sample_id) & artifacts["seed"].eq(seed)
        ] if not artifacts.empty else artifacts
        actual = tuple(sorted(actual_group["scenario"].astype(str).unique())) if not actual_group.empty else ()
        missing = tuple(sorted(set(expected).difference(actual)))
        rows.append(
            {
                "comparison_key": f"{sample_id}|seed={int(seed)}",
                "sample_id": sample_id,
                "seed": int(seed),
                "expected_scenarios": json.dumps(expected),
                "complete_scenarios": json.dumps(actual),
                "missing_scenarios": json.dumps(missing),
                "status": "complete" if not missing and set(actual) == set(expected) else "excluded",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def missing_manifest_rows(
    manifest: pd.DataFrame, inventory: ArtifactInventory
) -> pd.DataFrame:
    """Return only execution keys without a validated complete artifact pair."""
    missing = set(EXECUTION_KEY_COLUMNS).difference(manifest.columns)
    if missing:
        raise ValueError(f"manifest missing execution keys: {sorted(missing)}")
    if inventory.complete.empty:
        return manifest.copy().reset_index(drop=True)
    completed = inventory.complete.copy()
    if "manifest_design_json" not in completed:
        return manifest.copy().reset_index(drop=True)
    completed_by_key = {
        tuple(row[column] for column in EXECUTION_KEY_COLUMNS): row["manifest_design_json"]
        for row in completed.to_dict("records")
    }
    missing_positions: list[int] = []
    for position, row in manifest.iterrows():
        key = tuple(row[column] for column in EXECUTION_KEY_COLUMNS)
        if completed_by_key.get(key) != _manifest_row_design_json(row):
            missing_positions.append(position)
    return manifest.loc[missing_positions].reset_index(drop=True)


def full_manifest_for_partial_resume(
    expected_manifest: pd.DataFrame, missing_manifest: pd.DataFrame
) -> pd.DataFrame:
    """Return the full cohort so runner alias persistence cannot shrink on resume."""
    key_columns = list(EXECUTION_KEY_COLUMNS)
    expected_keys = set(
        map(tuple, expected_manifest[key_columns].itertuples(index=False, name=None))
    )
    missing_keys = set(
        map(tuple, missing_manifest[key_columns].itertuples(index=False, name=None))
    )
    if not missing_keys.issubset(expected_keys):
        raise ValueError("missing-run manifest is not a subset of the expected cohort")
    return expected_manifest.copy().reset_index(drop=True)


def summarize_scenario_rank_stability(
    runs: pd.DataFrame,
    outcome: str,
    *,
    expected_scenarios: Iterable[str],
    higher_is_better: bool = True,
) -> pd.DataFrame:
    """Rank scenarios only inside complete, comparable sample/seed groups."""
    expected = tuple(map(str, expected_scenarios))
    required = {"sample_id", "seed", "scenario", outcome}
    missing = required.difference(runs.columns)
    if missing:
        raise ValueError(f"rank runs are missing required columns: {sorted(missing)}")
    group_columns = [column for column in ("experiment", "sample_id", "seed") if column in runs]
    complete_groups: list[pd.DataFrame] = []
    expected_set = set(expected)
    for _, group in runs.groupby(group_columns, sort=False, dropna=False):
        if set(group["scenario"].astype(str)) != expected_set:
            continue
        if group["scenario"].duplicated().any():
            continue
        ranked = group.copy()
        ranked["rank"] = ranked[outcome].rank(
            ascending=not higher_is_better, method="average"
        )
        complete_groups.append(ranked)
    if not complete_groups:
        return pd.DataFrame(
            columns=("scenario", "first_place_frequency", "median_rank", "comparison_count")
        )
    rankings = pd.concat(complete_groups, ignore_index=True)
    summary = (
        rankings.groupby("scenario", as_index=False)["rank"]
        .agg(
            first_place_frequency=lambda values: float(np.mean(values.eq(1.0))),
            median_rank="median",
            comparison_count="count",
        )
    )
    order = {scenario: index for index, scenario in enumerate(expected)}
    return summary.assign(_order=summary["scenario"].map(order)).sort_values(
        "_order"
    ).drop(columns="_order").reset_index(drop=True)


def _action(frame: pd.DataFrame, tolerance: float) -> pd.Series:
    target_columns = list(LAND_USES)
    current_columns = [f"current_{name}" for name in LAND_USES]
    changes = frame[target_columns].to_numpy(float) - frame[current_columns].to_numpy(float)
    largest = changes.argmax(axis=1)
    maxima = changes[np.arange(len(changes)), largest]
    actions = np.asarray(LAND_USES, dtype=object)[largest]
    actions[maxima <= tolerance] = "unchanged"
    return pd.Series(actions, index=frame.index)


def summarize_spatial_robustness(
    targets: pd.DataFrame, *, tolerance: float = 1e-9
) -> pd.DataFrame:
    """Summarize cell-level target/action stability across comparable runs."""
    required = {
        "scenario",
        "comparison_id",
        "cell_id",
        *LAND_USES,
        *(f"current_{name}" for name in LAND_USES),
    }
    missing = required.difference(targets.columns)
    if missing:
        raise ValueError(f"spatial targets are missing required columns: {sorted(missing)}")
    if targets.empty:
        return pd.DataFrame()
    frame = targets.copy()
    frame["action"] = _action(frame, tolerance)
    rows: list[dict[str, object]] = []
    for (scenario, cell_id), group in frame.groupby(["scenario", "cell_id"], sort=False):
        counts = group["action"].value_counts()
        modal = sorted(counts[counts.eq(counts.max())].index)[0]
        row: dict[str, object] = {
            "scenario": scenario,
            "cell_id": cell_id,
            "modal_action": modal,
            "action_agreement": float(counts.max() / len(group)),
            "comparison_count": int(group["comparison_id"].nunique()),
        }
        for land_use in LAND_USES:
            row[f"{land_use}_target_mean"] = float(group[land_use].mean())
            row[f"{land_use}_target_sd"] = float(group[land_use].std())
        rows.append(row)
    return pd.DataFrame(rows)


def _load_target_records(artifacts: pd.DataFrame) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    for row in artifacts.itertuples(index=False):
        with np.load(row.targets_path) as archive:
            target = pd.DataFrame(archive["targets"], columns=LAND_USES)
            current = pd.DataFrame(
                archive["current_fractions"],
                columns=[f"current_{name}" for name in LAND_USES],
            )
            records.append(
                pd.concat([target, current], axis=1).assign(
                    scenario=row.scenario,
                    comparison_id=f"{row.sample_id}__seed_{row.seed}",
                    cell_id=archive["cell_ids"],
                )
            )
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def _write_frame(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")
    return path


def _conclusion(available: bool, stable: bool) -> str:
    if not available:
        return "unavailable"
    return "stable" if stable else "unstable"


def classify_parameter_importance(
    frame: pd.DataFrame,
    expected_analyses: set[tuple[str, str]] | None = None,
) -> str:
    """Apply descriptive fit, rank-consistency, and repeat-dispersion screens."""
    required = {
        "held_out_r2",
        "top_parameter_rank_consistent",
        "top_parameter_repeat_dispersion_pass",
        "model_fit_pass",
    }
    if frame.empty or not required.issubset(frame.columns):
        return "unavailable"
    actual = set(zip(frame["scenario"], frame["outcome"], strict=False))
    if expected_analyses is not None and actual != expected_analyses:
        return "unavailable"
    consistent = bool(
        frame[
            [
                "top_parameter_rank_consistent",
                "top_parameter_repeat_dispersion_pass",
                "model_fit_pass",
            ]
        ].all(axis=None)
        and frame["held_out_r2"].ge(MIN_HELD_OUT_R2).all()
    )
    return "screening-consistent" if consistent else "screening-variable"


def classify_interactions(
    frame: pd.DataFrame,
    expected_analyses: set[tuple[str, str, str, str]] | None = None,
) -> str:
    """Screen interaction residuals relative to descriptive baseline seed SD."""
    if frame.empty or "max_abs_residual_to_noise" not in frame:
        return "unavailable"
    actual = set(
        zip(
            frame["scenario"],
            frame["parameter_x"],
            frame["parameter_y"],
            frame["outcome"],
            strict=False,
        )
    )
    if expected_analyses is not None and actual != expected_analyses:
        return "unavailable"
    descriptively_small = bool(
        frame["max_abs_residual_to_noise"].notna().all()
        and frame["max_abs_residual_to_noise"].le(
            MAX_INTERACTION_TO_BASELINE_NOISE
        ).all()
    )
    return (
        "screening-small-relative-to-seed-sd"
        if descriptively_small
        else "screening-large-relative-to-seed-sd"
    )


def _json_scalar(value: object) -> object:
    return value.item() if isinstance(value, np.generic) else value


def build_robustness_report(
    output_root: Path | str,
    report_dir: Path | str,
    profile: str,
    *,
    expected_identity: tuple[object, ...] | None = None,
) -> dict[str, Path]:
    """Reuse validated historical artifacts and write a self-contained report set."""
    root = Path(output_root)
    destination = Path(report_dir)
    destination.mkdir(parents=True, exist_ok=True)
    inventory = inventory_artifacts(root, profile, expected_identity=expected_identity)
    manifests = _latest_manifests(root, profile)
    complete, manifest_exclusions = _filter_to_latest_manifests(
        inventory.complete, manifests
    )

    completeness_rows: list[dict[str, object]] = []
    for experiment in EXPERIMENTS:
        completed = 0 if complete.empty else int(complete["experiment"].eq(experiment).sum())
        expected_manifest = manifests.get(experiment)
        expected = len(expected_manifest) if expected_manifest is not None else None
        missing = None if expected is None else max(expected - completed, 0)
        availability = (
            "unavailable" if expected is None and completed == 0
            else "complete" if expected is not None and missing == 0
            else "incomplete"
        )
        completeness_rows.append(
            {
                "experiment": experiment,
                "profile": profile,
                "complete_runs": completed,
                "expected_runs": expected,
                "missing_runs": missing,
                "availability": availability,
            }
        )
    completeness = pd.DataFrame(completeness_rows)

    biodiversity = (
        complete.loc[complete["experiment"].eq("biodiversity")].copy()
        if not complete.empty else pd.DataFrame()
    )
    biodiversity_manifest = manifests.get("biodiversity")
    expected_scenarios = (
        tuple(dict.fromkeys(biodiversity_manifest["scenario"].astype(str)))
        if biodiversity_manifest is not None
        else tuple(SCENARIO_LABELS)
    )
    comparison_groups = _comparison_group_report(biodiversity_manifest, biodiversity)
    excluded_groups = comparison_groups.loc[comparison_groups["status"].eq("excluded")]
    complete_rank_evidence = (
        not comparison_groups.empty
        and excluded_groups.empty
        and len(expected_scenarios) >= 2
    )
    rank_tables: list[pd.DataFrame] = []
    if complete_rank_evidence:
        for outcome in OUTCOMES:
            if biodiversity.empty or outcome not in biodiversity:
                continue
            ranking = summarize_scenario_rank_stability(
                biodiversity,
                outcome,
                expected_scenarios=expected_scenarios,
                higher_is_better=outcome not in {"cost", "changed_pct"},
            )
            if not ranking.empty:
                rank_tables.append(ranking.assign(outcome=outcome))
    rank_stability = pd.concat(rank_tables, ignore_index=True) if rank_tables else pd.DataFrame(
        columns=("scenario", "first_place_frequency", "median_rank", "comparison_count", "outcome")
    )

    spatial_columns = (
        "scenario",
        "cell_id",
        "modal_action",
        "action_agreement",
        "comparison_count",
        *(f"{land_use}_target_{statistic}" for land_use in LAND_USES for statistic in ("mean", "sd")),
    )
    spatial = (
        summarize_spatial_robustness(_load_target_records(biodiversity))
        if not biodiversity.empty
        else pd.DataFrame(columns=spatial_columns)
    )

    global_runs = (
        complete.loc[complete["experiment"].eq("global")].copy()
        if not complete.empty else pd.DataFrame()
    )
    importance_tables: list[pd.DataFrame] = []
    global_complete = completeness.set_index("experiment").loc["global", "availability"] == "complete"
    if global_complete and not global_runs.empty:
        for scenario, scenario_runs in global_runs.groupby("scenario", sort=False):
            for outcome in OUTCOMES:
                if outcome not in scenario_runs:
                    continue
                try:
                    ranked = rank_parameter_importance(scenario_runs, outcome)
                except (ImportError, ValueError):
                    continue
                held_out_r2 = float(ranked.attrs["held_out_r2"])
                top_permutation = ranked.loc[
                    ranked["permutation_importance_mean"].idxmax(), "parameter"
                ]
                top_spearman = ranked.loc[
                    ranked["spearman_rho"].abs().idxmax(), "parameter"
                ]
                top_row = ranked.loc[ranked["parameter"].eq(top_permutation)].iloc[0]
                repeat_dispersion_pass = bool(
                    top_row["permutation_importance_mean"]
                    - PERMUTATION_UNCERTAINTY_Z * top_row["permutation_importance_sd"]
                    > 0.0
                )
                rank_consistent = bool(top_permutation == top_spearman)
                model_fit_pass = bool(held_out_r2 >= MIN_HELD_OUT_R2)
                importance_tables.append(
                    ranked.assign(
                        scenario=scenario,
                        outcome=outcome,
                        held_out_r2=held_out_r2,
                        min_held_out_r2=MIN_HELD_OUT_R2,
                        top_parameter_rank_consistent=rank_consistent,
                        top_parameter_repeat_dispersion_pass=repeat_dispersion_pass,
                        model_fit_pass=model_fit_pass,
                    )
                )
    parameter_importance = (
        pd.concat(importance_tables, ignore_index=True)
        if importance_tables
        else pd.DataFrame(
            columns=(
                "parameter",
                "spearman_rho",
                "random_forest_importance",
                "permutation_importance_mean",
                "permutation_importance_sd",
                "scenario",
                "outcome",
                "held_out_r2",
                "min_held_out_r2",
                "top_parameter_rank_consistent",
                "top_parameter_repeat_dispersion_pass",
                "model_fit_pass",
            )
        )
    )

    interaction_runs = (
        complete.loc[complete["experiment"].eq("interactions")].copy()
        if not complete.empty else pd.DataFrame()
    )
    baseline_runs = (
        complete.loc[complete["experiment"].eq("baseline")].copy()
        if not complete.empty
        else pd.DataFrame()
    )
    interactions = pd.DataFrame(
        columns=(
            "scenario",
            "parameter_x",
            "parameter_y",
            "outcome",
            "max_abs_interaction_residual",
            "rms_interaction_residual",
            "baseline_sd",
            "max_abs_residual_to_noise",
            "rms_residual_to_noise",
        ),
    )
    interaction_evidence_complete = all(
        completeness.set_index("experiment").loc[name, "availability"] == "complete"
        for name in ("baseline", "interactions")
    )
    if interaction_evidence_complete and not interaction_runs.empty and not baseline_runs.empty:
        try:
            interactions = summarize_interaction_noise(
                interaction_runs, baseline_runs, OUTCOMES
            )
        except ValueError:
            pass

    global_manifest = manifests.get("global")
    expected_importance_analyses = (
        {
            (scenario, outcome)
            for scenario in global_manifest["scenario"].astype(str).unique()
            for outcome in OUTCOMES
        }
        if global_manifest is not None
        else None
    )
    parameter_importance_conclusion = classify_parameter_importance(
        parameter_importance, expected_importance_analyses
    )
    interaction_manifest = manifests.get("interactions")
    expected_interaction_analyses = (
        {
            (str(row.scenario), str(row.parameter_x), str(row.parameter_y), outcome)
            for row in interaction_manifest[
                ["scenario", "parameter_x", "parameter_y"]
            ].drop_duplicates().itertuples(index=False)
            for outcome in OUTCOMES
        }
        if interaction_manifest is not None
        and {"parameter_x", "parameter_y"}.issubset(interaction_manifest.columns)
        else None
    )
    interaction_conclusion = classify_interactions(
        interactions, expected_interaction_analyses
    )
    rank_stable = (
        not rank_stability.empty
        and rank_stability.groupby("outcome")["first_place_frequency"]
        .max()
        .ge(0.8)
        .all()
    )

    conclusions = {
        "profile": profile,
        "identity": (
            [_json_scalar(value) for value in inventory.identity]
            if inventory.identity is not None
            else None
        ),
        "scenario_rank_stability": _conclusion(
            complete_rank_evidence
            and not rank_stability.empty
            and set(rank_stability["outcome"]) == set(OUTCOMES),
            bool(rank_stable),
        ),
        "parameter_importance": parameter_importance_conclusion,
        "interactions": interaction_conclusion,
        "spatial_robustness": _conclusion(
            not spatial.empty and excluded_groups.empty,
            not spatial.empty
            and excluded_groups.empty
            and float(spatial["action_agreement"].median()) >= 0.8,
        ),
        "missing_experiments": completeness.loc[
            completeness["availability"].ne("complete"), "experiment"
        ].tolist(),
        "excluded_incomplete_artifacts": int(len(inventory.incomplete)),
        "excluded_manifest_artifacts": int(len(manifest_exclusions)),
        "rank_evidence_qualification": (
            "complete"
            if complete_rank_evidence
            else "withheld: required comparison groups are incomplete or fewer than two scenarios"
        ),
        "spatial_evidence_qualification": (
            "complete"
            if excluded_groups.empty and not comparison_groups.empty
            else "qualified: one or more required comparison groups are incomplete"
        ),
        "expected_comparison_group_count": int(len(comparison_groups)),
        "complete_comparison_group_count": int(comparison_groups["status"].eq("complete").sum()),
        "excluded_comparison_group_count": int(len(excluded_groups)),
        "excluded_comparison_group_keys": excluded_groups["comparison_key"].tolist(),
        "parameter_importance_criteria": {
            "minimum_held_out_r2": MIN_HELD_OUT_R2,
            "top_rank_must_match_absolute_spearman": True,
            "descriptive_top_permutation_mean_minus_repeat_sd_multiplier_must_exceed_zero": PERMUTATION_UNCERTAINTY_Z,
            "interpretation": "screening diagnostic only; permutation repeats are not independent resamples",
        },
        "interaction_criterion": {
            "maximum_interaction_to_baseline_seed_sd": MAX_INTERACTION_TO_BASELINE_NOISE,
            "interpretation": "descriptive screening only; baseline seed SD is not a confidence interval",
        },
    }

    paths = {
        "completeness": _write_frame(completeness, destination / "run_completeness.csv"),
        "comparison_groups": _write_frame(
            comparison_groups, destination / "comparison_groups.csv"
        ),
        "rank_stability": _write_frame(rank_stability, destination / "scenario_rank_stability.csv"),
        "parameter_importance": _write_frame(parameter_importance, destination / "parameter_importance.csv"),
        "interactions": _write_frame(interactions, destination / "interactions.csv"),
        "spatial_robustness": _write_frame(spatial, destination / "spatial_robustness.csv"),
        "conclusions": destination / "conclusions.json",
    }
    paths["conclusions"].write_text(
        json.dumps(conclusions, indent=2, sort_keys=True), encoding="utf-8"
    )
    return paths
