"""Sequential, resumable artifact runner for the preserved historical optimizer."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any
from zipfile import BadZipFile

import numpy as np
import pandas as pd

from estonia_landuse.optimizer.nsga2 import CONSTRAINT_TOLERANCE
from estonia_landuse.optimizer.trainer import train
from estonia_landuse.scenarios import select_representative
from estonia_landuse.simulator.simulator import summarize_policy
from estonia_landuse.simulator.targets import GROUP_COLUMNS, realize_targets

from .config import ExperimentProfile, resolve_profile
from .historical_model import SELECTION_RULES, make_historical_scenario_config
from .sampling import apply_overrides, manifest_run_count

ARTIFACT_SCHEMA_VERSION = 1
_RUNTIME_ROW_FIELDS = {
    "status",
    "started_at",
    "finished_at",
    "metrics_path",
    "targets_path",
    "error_type",
    "error_message",
    "cohort_signature",
    "run_signature",
}
_SERIALIZED_METRIC_NAMES = {
    "agriculture_loss_pct": "agriculture_loss",
    "agriculture_gain_pct": "agriculture_gain",
    "gross_agriculture_loss_pct": "gross_agriculture_loss",
    "gross_agriculture_gain_pct": "gross_agriculture_gain",
    "wetland_gain_pct": "wetland_gain",
}


@dataclass(frozen=True)
class RunArtifacts:
    """Terminal paths and status for one historical optimizer execution."""

    status: str
    metrics_path: Path | None
    targets_path: Path | None
    error_type: str | None = None
    error_message: str | None = None


def _resolved_profile(profile: str | ExperimentProfile) -> ExperimentProfile:
    if isinstance(profile, ExperimentProfile):
        return profile
    return resolve_profile(profile)


def _safe_component(value: object, field: str) -> str:
    component = str(value)
    unsafe = (
        not component
        or component in {".", ".."}
        or Path(component).name != component
        or "/" in component
        or "\\" in component
        or ":" in component
    )
    if unsafe:
        raise ValueError(f"unsafe artifact path component for {field}: {component!r}")
    return component


def _artifact_paths(
    output_dir: Path | str,
    row: Mapping[str, object],
) -> tuple[Path, Path]:
    root = Path(output_dir)
    experiment = _safe_component(row["experiment"], "experiment")
    sample_id = _safe_component(row["sample_id"], "sample_id")
    scenario = _safe_component(row["scenario"], "scenario")
    seed = int(row["seed"])
    run_dir = root / "runs" / experiment / sample_id / scenario
    stem = f"seed_{seed}"
    return run_dir / f"{stem}.parquet", run_dir / f"{stem}.npz"


def _json_ready(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _json_ready(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _input_fingerprint(
    context: pd.DataFrame,
    feature_columns: Sequence[str],
) -> str:
    digest = sha256()
    schema = {
        "columns": [str(column) for column in context.columns],
        "dtypes": [str(dtype) for dtype in context.dtypes],
        "feature_columns": list(feature_columns),
    }
    digest.update(_canonical_json(schema).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(context, index=True).to_numpy().tobytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _code_fingerprint() -> str:
    digest = sha256()
    package_root = Path(__file__).resolve().parents[1]
    for source in sorted(package_root.rglob("*.py")):
        digest.update(source.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(source.read_bytes())
    return digest.hexdigest()


def _manifest_design(row: Mapping[str, object]) -> dict[str, object]:
    return {
        str(key): _json_ready(value)
        for key, value in row.items()
        if str(key) not in _RUNTIME_ROW_FIELDS
    }


def _effective_config(row: Mapping[str, object]) -> dict:
    config = make_historical_scenario_config(str(row["scenario"]))
    historical_fourth_objective = config.get("optimization", {}).get(
        "fourth_objective", "changed_pct"
    )
    overrides = row.get("overrides", {})
    if overrides is None:
        return config
    if not isinstance(overrides, Mapping):
        raise ValueError("manifest overrides must be a mapping of dotted paths to values")
    changed = apply_overrides(config, overrides)
    changed_fourth_objective = changed.get("optimization", {}).get(
        "fourth_objective", "changed_pct"
    )
    if changed_fourth_objective != historical_fourth_objective:
        raise ValueError(
            "sensitivity overrides cannot change the historical fourth objective "
            f"from {historical_fourth_objective!r} to {changed_fourth_objective!r}"
        )
    return changed


def _run_metadata(
    context: pd.DataFrame,
    feature_columns: Sequence[str],
    row: Mapping[str, object],
    profile: str | ExperimentProfile,
    config: Mapping[str, object],
) -> dict[str, object]:
    resolved = _resolved_profile(profile)
    scenario_config_json = _canonical_json(config)
    configuration_fingerprint = sha256(scenario_config_json.encode("utf-8")).hexdigest()
    profile_label = row.get("profile", profile if isinstance(profile, str) else "custom")
    metadata: dict[str, object] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "profile": str(profile_label),
        "pop_size": resolved.pop_size,
        "n_generations": resolved.n_generations,
        "hidden_size": resolved.hidden_size,
        "use_seeds": resolved.use_seeds,
        "input_fingerprint": _input_fingerprint(context, feature_columns),
        "configuration_fingerprint": configuration_fingerprint,
        "scenario_config_fingerprint": configuration_fingerprint,
        "scenario_config_json": scenario_config_json,
        "code_fingerprint": _code_fingerprint(),
        "manifest_design_json": _canonical_json(_manifest_design(row)),
    }
    signature_fields = {
        "experiment": str(row["experiment"]),
        "sample_id": str(row["sample_id"]),
        "scenario": str(row["scenario"]),
        "seed": int(row["seed"]),
        **metadata,
    }
    metadata["run_signature"] = sha256(
        _canonical_json(signature_fields).encode("utf-8")
    ).hexdigest()
    return metadata


def _normalized_features(
    context: pd.DataFrame,
    feature_columns: Sequence[str],
) -> np.ndarray:
    features = context[list(feature_columns)].to_numpy(dtype=np.float32)
    standard_deviation = features.std(axis=0)
    standard_deviation[standard_deviation == 0] = 1.0
    return (features - features.mean(axis=0)) / standard_deviation


def summarize_front(
    population: Sequence[Any],
    context: pd.DataFrame,
    feature_columns: Sequence[str],
    config: dict,
) -> tuple[pd.DataFrame, list[np.ndarray]]:
    """Evaluate only rank-zero policies using historical reporting names."""
    front = [policy for policy in population if policy.rank == 0]
    if not front:
        raise RuntimeError("historical trainer returned no rank-zero policies")
    normalized = _normalized_features(context, feature_columns)
    rows: list[dict[str, object]] = []
    proposals: list[np.ndarray] = []
    for policy_id, policy in enumerate(front):
        proposal = policy.prescribe(normalized)
        proposals.append(proposal)
        rows.append(
            {
                "id": policy_id,
                **summarize_policy(context, proposal, config),
            }
        )
    return pd.DataFrame(rows), proposals


def _serialized_metrics(selected: pd.Series) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for name, value in selected.items():
        if name in {"id", "is_feasible", "feasibility"}:
            continue
        serialized[_SERIALIZED_METRIC_NAMES.get(str(name), str(name))] = value
    return serialized


def _scalar_design_fields(row: Mapping[str, object]) -> dict[str, object]:
    return {
        str(key): _json_ready(value)
        for key, value in _manifest_design(row).items()
        if key not in {"overrides", "profile"}
        and isinstance(value, (str, int, float, bool))
    }


def _stored_pair_matches(
    metrics_path: Path,
    targets_path: Path,
    metadata: Mapping[str, object],
    n_cells: int,
) -> bool:
    try:
        metrics = pd.read_parquet(metrics_path)
        if len(metrics) != 1:
            return False
        stored = metrics.iloc[0]
        identity_fields = (
            "artifact_schema_version",
            "input_fingerprint",
            "configuration_fingerprint",
            "code_fingerprint",
            "run_signature",
        )
        if not all(stored.get(field) == metadata[field] for field in identity_fields):
            return False
        with np.load(targets_path) as targets:
            required = {
                "targets",
                "current_fractions",
                "cell_ids",
                *identity_fields,
            }
            return (
                required.issubset(targets.files)
                and targets["targets"].shape == (n_cells, 4)
                and targets["current_fractions"].shape == (n_cells, 4)
                and targets["cell_ids"].shape == (n_cells,)
                and all(targets[field].item() == metadata[field] for field in identity_fields)
            )
    except (BadZipFile, EOFError, IndexError, KeyError, OSError, ValueError):
        return False


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{os.getpid()}.tmp.parquet")
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_npz(path: Path, **arrays: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.",
        suffix=".tmp.npz",
        dir=path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_experiment_row(
    context: pd.DataFrame,
    feature_columns: list[str],
    row: Mapping[str, object],
    output_dir: Path | str,
    profile: str | ExperimentProfile,
    overwrite: bool = False,
) -> RunArtifacts:
    """Execute one historical optimizer row or reuse its complete artifact pair."""
    metrics_path, targets_path = _artifact_paths(output_dir, row)
    resolved = _resolved_profile(profile)
    config = _effective_config(row)
    metadata = _run_metadata(context, feature_columns, row, profile, config)
    if (
        not overwrite
        and metrics_path.exists()
        and targets_path.exists()
        and _stored_pair_matches(
            metrics_path,
            targets_path,
            metadata,
            len(context),
        )
    ):
        return RunArtifacts("skipped", metrics_path, targets_path)

    started = perf_counter()
    population = train(
        context,
        feature_columns,
        pop_size=resolved.pop_size,
        n_generations=resolved.n_generations,
        hidden_size=resolved.hidden_size,
        config=config,
        use_seeds=resolved.use_seeds,
        verbose=False,
        seed=int(row["seed"]),
    )
    duration_seconds = perf_counter() - started
    front, proposals = summarize_front(population, context, feature_columns, config)
    selection_rule = SELECTION_RULES[str(row["scenario"])]
    selected = select_representative(front, selection_rule)
    policy_id = int(selected["id"])
    targets = realize_targets(context, proposals[policy_id], config)
    feasible_solutions = int(
        (front["constraint_penalty"] <= CONSTRAINT_TOLERANCE).sum()
    )

    metric_row = {
        **_scalar_design_fields(row),
        "experiment": str(row["experiment"]),
        "sample_id": str(row["sample_id"]),
        "scenario": str(row["scenario"]),
        "seed": int(row["seed"]),
        **metadata,
        "duration_seconds": duration_seconds,
        "front_size": len(front),
        "feasible_solutions": feasible_solutions,
        "policy_id": policy_id,
        "selection_rule": selection_rule,
        "feasible": bool(selected["is_feasible"]),
        **_serialized_metrics(selected),
    }
    _atomic_parquet(pd.DataFrame([metric_row]), metrics_path)
    cell_ids = (
        context["cell_id"].to_numpy()
        if "cell_id" in context.columns
        else context.index.to_numpy()
    )
    identity_fields = {
        name: metadata[name]
        for name in (
            "artifact_schema_version",
            "input_fingerprint",
            "configuration_fingerprint",
            "code_fingerprint",
            "run_signature",
        )
    }
    _atomic_npz(
        targets_path,
        targets=targets,
        current_fractions=context[GROUP_COLUMNS].to_numpy(dtype=float),
        cell_ids=cell_ids,
        selection_rule=selection_rule,
        policy_id=policy_id,
        **identity_fields,
    )
    return RunArtifacts("completed", metrics_path, targets_path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cohort_signature(
    rows: pd.DataFrame,
    context: pd.DataFrame,
    feature_columns: Sequence[str],
    profile: str | ExperimentProfile,
) -> str:
    identity = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "profile": asdict(_resolved_profile(profile)),
        "input_fingerprint": _input_fingerprint(context, feature_columns),
        "code_fingerprint": _code_fingerprint(),
        "rows": [_manifest_design(row) for row in rows.to_dict("records")],
    }
    return sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _serializable_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    serialized = frame.copy()
    for column in serialized.columns:
        if serialized[column].dtype == object:
            serialized[column] = serialized[column].map(
                lambda value: _canonical_json(value)
                if isinstance(value, (Mapping, list, tuple))
                else value
            )
    return serialized


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{os.getpid()}.tmp.csv")
    try:
        _serializable_manifest(frame).to_csv(temporary, index=False, lineterminator="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_paths(
    output_dir: Path,
    experiment: object,
    cohort_signature: str,
) -> tuple[Path, Path]:
    """Build safe manifest paths contained by the requested manifest root."""
    component = _safe_component(experiment, "experiment")
    manifest_root = output_dir.resolve(strict=False) / "manifests"
    paths = (
        output_dir / "manifests" / f"{component}-{cohort_signature[:16]}.csv",
        output_dir / "manifests" / f"{component}.csv",
    )
    for path in paths:
        try:
            path.resolve(strict=False).relative_to(manifest_root)
        except ValueError as error:
            raise ValueError(f"manifest path escapes output directory: {path}") from error
    return paths


def _persist_manifest_copies(
    output_dir: Path,
    manifest: pd.DataFrame,
) -> dict[str, tuple[Path, Path]]:
    cohorts: list[tuple[object, pd.DataFrame, tuple[Path, Path]]] = []
    for experiment, rows in manifest.groupby("experiment", sort=False):
        signature = str(rows["cohort_signature"].iloc[0])
        cohorts.append((experiment, rows, _manifest_paths(output_dir, experiment, signature)))

    paths: dict[str, tuple[Path, Path]] = {}
    for experiment, rows, (cohort_path, alias_path) in cohorts:
        _atomic_csv(rows, cohort_path)
        _atomic_csv(rows, alias_path)
        paths[str(experiment)] = (cohort_path, alias_path)
    return paths


def _update_manifest_row(
    manifest: pd.DataFrame,
    paths: tuple[Path, Path],
    position: int,
    **updates: object,
) -> None:
    for field, value in updates.items():
        if field not in manifest.columns:
            manifest[field] = pd.Series([None] * len(manifest), dtype=object)
        manifest.at[position, field] = value
    experiment = manifest.at[position, "experiment"]
    cohort = manifest.loc[manifest["experiment"] == experiment]
    for path in paths:
        _atomic_csv(cohort, path)


def run_manifest(
    context: pd.DataFrame,
    feature_columns: list[str],
    manifest: pd.DataFrame,
    output_dir: Path | str,
    profile: str | ExperimentProfile,
    overwrite: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
    n_workers: int = 1,
) -> pd.DataFrame:
    """Execute a manifest sequentially while the parent owns all status writes."""
    if n_workers != 1:
        raise ValueError("the sequential runner requires n_workers=1")
    manifest_run_count(manifest)
    output_root = Path(output_dir)
    prepared_groups: list[pd.DataFrame] = []
    for _, rows in manifest.groupby("experiment", sort=False):
        group = rows.copy()
        group["cohort_signature"] = _cohort_signature(
            group,
            context,
            feature_columns,
            profile,
        )
        prepared_groups.append(group)
    prepared = pd.concat(prepared_groups).sort_index().copy()
    prepared["status"] = "pending"
    for column in (
        "started_at",
        "finished_at",
        "metrics_path",
        "targets_path",
        "error_type",
        "error_message",
    ):
        prepared[column] = pd.Series([None] * len(prepared), index=prepared.index, dtype=object)
    paths_by_experiment = _persist_manifest_copies(output_root, prepared)

    results: list[dict[str, object]] = []
    total = len(prepared)
    for completed, (position, row) in enumerate(prepared.iterrows(), start=1):
        started_at = _utc_now()
        manifest_paths = paths_by_experiment[str(row["experiment"])]
        _update_manifest_row(
            prepared,
            manifest_paths,
            position,
            status="running",
            started_at=started_at,
            error_type=None,
            error_message=None,
        )
        metrics_path: Path | None = None
        targets_path: Path | None = None
        try:
            metrics_path, targets_path = _artifact_paths(output_root, row)
            artifacts = run_experiment_row(
                context,
                feature_columns,
                row,
                output_root,
                profile,
                overwrite=overwrite,
            )
        except Exception as error:  # noqa: BLE001 - isolate row-level failures
            artifacts = RunArtifacts(
                "failed",
                metrics_path,
                targets_path,
                type(error).__name__,
                str(error),
            )
        finished_at = _utc_now()
        terminal = {
            "status": artifacts.status,
            "finished_at": finished_at,
            "metrics_path": (
                str(artifacts.metrics_path) if artifacts.metrics_path is not None else None
            ),
            "targets_path": (
                str(artifacts.targets_path) if artifacts.targets_path is not None else None
            ),
            "error_type": artifacts.error_type,
            "error_message": artifacts.error_message,
        }
        _update_manifest_row(prepared, manifest_paths, position, **terminal)
        result = row.to_dict() | {
            "started_at": started_at,
            **terminal,
        }
        results.append(result)
        if progress is not None:
            progress(completed, total, artifacts.status)
    return pd.DataFrame(results)
