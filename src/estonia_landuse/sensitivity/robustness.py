"""Cross-experiment robustness synthesis for historical sensitivity artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile

import numpy as np
import pandas as pd

from .analysis import estimate_interaction_surface, rank_parameter_importance
from .historical_model import SCENARIO_LABELS
from .runner import ARTIFACT_SCHEMA_VERSION, _code_fingerprint, _input_fingerprint
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


def missing_manifest_rows(
    manifest: pd.DataFrame, inventory: ArtifactInventory
) -> pd.DataFrame:
    """Return only execution keys without a validated complete artifact pair."""
    missing = set(EXECUTION_KEY_COLUMNS).difference(manifest.columns)
    if missing:
        raise ValueError(f"manifest missing execution keys: {sorted(missing)}")
    if inventory.complete.empty:
        return manifest.copy().reset_index(drop=True)
    completed = inventory.complete[list(EXECUTION_KEY_COLUMNS)].drop_duplicates()
    marked = manifest.merge(
        completed.assign(_already_complete=True),
        on=list(EXECUTION_KEY_COLUMNS),
        how="left",
        validate="many_to_one",
    )
    return marked.loc[marked["_already_complete"].isna()].drop(
        columns="_already_complete"
    ).reset_index(drop=True)


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


def _expected_count(output_root: Path, experiment: str, profile: str) -> int | None:
    path = output_root / "manifests" / f"{experiment}.csv"
    if not path.exists():
        return None
    manifest = pd.read_csv(path)
    if "profile" not in manifest or "status" not in manifest:
        return None
    return int(manifest["profile"].astype(str).eq(profile).sum())


def _write_frame(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")
    return path


def _conclusion(available: bool, stable: bool) -> str:
    if not available:
        return "unavailable"
    return "stable" if stable else "unstable"


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
    complete = inventory.complete

    completeness_rows: list[dict[str, object]] = []
    for experiment in EXPERIMENTS:
        completed = 0 if complete.empty else int(complete["experiment"].eq(experiment).sum())
        expected = _expected_count(root, experiment, profile)
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
    expected_scenarios: tuple[str, ...] = tuple(SCENARIO_LABELS)
    biodiversity_manifest = root / "manifests" / "biodiversity.csv"
    if biodiversity_manifest.exists():
        manifest = pd.read_csv(biodiversity_manifest)
        cohort = manifest.loc[manifest.get("profile", pd.Series(dtype=str)).astype(str).eq(profile)]
        if not cohort.empty:
            expected_scenarios = tuple(dict.fromkeys(cohort["scenario"].astype(str)))
    rank_tables: list[pd.DataFrame] = []
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
    if not global_runs.empty:
        for outcome in OUTCOMES:
            if outcome not in global_runs:
                continue
            try:
                ranked = rank_parameter_importance(global_runs, outcome)
            except (ImportError, ValueError):
                continue
            importance_tables.append(ranked.assign(outcome=outcome))
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
                "outcome",
            )
        )
    )

    interaction_runs = (
        complete.loc[complete["experiment"].eq("interactions")].copy()
        if not complete.empty else pd.DataFrame()
    )
    interaction_rows: list[dict[str, object]] = []
    required_interaction = {"parameter_x", "parameter_y", "value_x", "value_y"}
    if not interaction_runs.empty and required_interaction.issubset(interaction_runs.columns):
        for (scenario, parameter_x, parameter_y), group in interaction_runs.groupby(
            ["scenario", "parameter_x", "parameter_y"], sort=False
        ):
            for outcome in OUTCOMES:
                try:
                    surface = estimate_interaction_surface(group, outcome)
                except ValueError:
                    continue
                interaction_rows.append(
                    {
                        "scenario": scenario,
                        "parameter_x": parameter_x,
                        "parameter_y": parameter_y,
                        "outcome": outcome,
                        "max_abs_interaction_residual": float(surface["interaction_residual"].abs().max()),
                        "rms_interaction_residual": float(np.sqrt(np.mean(np.square(surface["interaction_residual"])))),
                    }
                )
    interactions = pd.DataFrame(
        interaction_rows,
        columns=(
            "scenario",
            "parameter_x",
            "parameter_y",
            "outcome",
            "max_abs_interaction_residual",
            "rms_interaction_residual",
        ),
    )

    conclusions = {
        "profile": profile,
        "identity": (
            [_json_scalar(value) for value in inventory.identity]
            if inventory.identity is not None
            else None
        ),
        "scenario_rank_stability": _conclusion(
            not rank_stability.empty,
            not rank_stability.empty and float(rank_stability["first_place_frequency"].max()) >= 0.8,
        ),
        "parameter_importance": _conclusion(
            not parameter_importance.empty,
            not parameter_importance.empty and parameter_importance["outcome"].nunique() >= 2,
        ),
        "interactions": _conclusion(
            not interactions.empty,
            not interactions.empty and float(interactions["max_abs_interaction_residual"].max()) <= 0.01,
        ),
        "spatial_robustness": _conclusion(
            not spatial.empty,
            not spatial.empty and float(spatial["action_agreement"].median()) >= 0.8,
        ),
        "missing_experiments": completeness.loc[
            completeness["availability"].ne("complete"), "experiment"
        ].tolist(),
        "excluded_incomplete_artifacts": int(len(inventory.incomplete)),
    }

    paths = {
        "completeness": _write_frame(completeness, destination / "run_completeness.csv"),
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
