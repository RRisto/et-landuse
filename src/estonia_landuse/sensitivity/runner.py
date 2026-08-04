"""Resumable artifact runner for independent historical optimizer executions."""

from __future__ import annotations

import json
import ntpath
import os
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from time import perf_counter, process_time
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
_WINDOWS_RESERVED_COMPONENTS = {
    "aux",
    "clock$",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{suffix}" for suffix in (*range(1, 10), "¹", "²", "³")),
    *(f"lpt{suffix}" for suffix in (*range(1, 10), "¹", "²", "³")),
}
_WINDOWS_ILLEGAL_COMPONENT_CHARACTERS = frozenset('<>:"/\\|?*')


@dataclass(frozen=True)
class RunArtifacts:
    """Terminal paths and status for one historical optimizer execution."""

    status: str
    metrics_path: Path | None
    targets_path: Path | None
    error_type: str | None = None
    error_message: str | None = None
    training_seconds: float | None = None
    optimizer_cpu_seconds: float | None = None
    front_evaluation_seconds: float | None = None
    artifact_writing_seconds: float | None = None
    total_duration_seconds: float | None = None


@dataclass(frozen=True)
class _WorkerRequest:
    """Pickle-safe request for one independent manifest row."""

    position: int
    row: dict[str, object]


@dataclass(frozen=True)
class _WorkerResult:
    """Pickle-safe result returned for parent-side reconciliation."""

    position: int
    artifacts: RunArtifacts
    worker_pid: int


_WORKER_STATE: tuple[
    pd.DataFrame,
    tuple[str, ...],
    Path,
    str | ExperimentProfile,
    bool,
] | None = None


def _initialize_worker(
    context: pd.DataFrame,
    feature_columns: tuple[str, ...],
    output_dir: Path,
    profile: str | ExperimentProfile,
    overwrite: bool,
) -> None:
    """Install immutable run-wide inputs once in each worker process."""
    global _WORKER_STATE
    _WORKER_STATE = (context, feature_columns, output_dir, profile, overwrite)


def _run_worker(request: _WorkerRequest) -> _WorkerResult:
    """Execute one row without access to parent-owned manifest state."""
    if _WORKER_STATE is None:
        raise RuntimeError("historical manifest worker was not initialized")
    context, feature_columns, output_dir, profile, overwrite = _WORKER_STATE
    artifacts = _execute_row(
        context,
        feature_columns,
        request.row,
        output_dir,
        profile,
        overwrite,
    )
    return _WorkerResult(request.position, artifacts, os.getpid())


def _resolved_profile(profile: str | ExperimentProfile) -> ExperimentProfile:
    if isinstance(profile, ExperimentProfile):
        return profile
    return resolve_profile(profile)


def _safe_component(value: object, field: str) -> str:
    component = str(value)
    windows_path = PureWindowsPath(component)
    reserved_stem = component.split(".", 1)[0].rstrip(" .").casefold()
    unsafe = (
        not component
        or component in {".", ".."}
        or windows_path.drive
        or windows_path.root
        or component.endswith((" ", "."))
        or reserved_stem in _WINDOWS_RESERVED_COMPONENTS
        or any(
            character in _WINDOWS_ILLEGAL_COMPONENT_CHARACTERS
            or ord(character) < 32
            for character in component
        )
        or len(component.encode("utf-16-le")) // 2 > 255
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
    paths = run_dir / f"{stem}.parquet", run_dir / f"{stem}.npz"
    runs_root = root.resolve(strict=False) / "runs"
    for path in paths:
        try:
            path.resolve(strict=False).relative_to(runs_root)
        except ValueError as error:
            raise ValueError(f"artifact path escapes output directory: {path}") from error
    return paths


def _artifact_identity(row: Mapping[str, object]) -> tuple[str, str, str, int]:
    """Return the Windows-canonical identity of one artifact pair."""
    seed = int(row["seed"])
    _safe_component(f"seed_{seed}", "seed")
    return (
        ntpath.normcase(_safe_component(row["experiment"], "experiment")),
        ntpath.normcase(_safe_component(row["sample_id"], "sample_id")),
        ntpath.normcase(_safe_component(row["scenario"], "scenario")),
        seed,
    )


def _preflight_artifacts(manifest: pd.DataFrame, output_dir: Path) -> None:
    """Reject colliding or escaping paths before any manifest is persisted."""
    valid_rows: list[dict[str, object]] = []
    identities: list[tuple[str, str, str, int]] = []
    manifest_identities: dict[str, set[tuple[str, str]]] = {}
    for row in manifest.to_dict("records"):
        experiment = _safe_component(row["experiment"], "experiment")
        manifest_identities.setdefault(ntpath.normcase(experiment), set()).add(
            (type(row["experiment"]).__name__, experiment)
        )
        try:
            identity = _artifact_identity(row)
        except (TypeError, ValueError):
            # Other invalid execution keys remain row-level failures,
            # preserving resumable cohorts.
            continue
        identities.append(identity)
        valid_rows.append(row)
    duplicate_manifests = {
        identity: variants
        for identity, variants in manifest_identities.items()
        if len(variants) > 1
    }
    if duplicate_manifests:
        formatted = "; ".join(
            f"{identity!r}: {sorted(variants)!r}"
            for identity, variants in sorted(duplicate_manifests.items())
        )
        raise ValueError(f"duplicate manifest identity: {formatted}")
    duplicate_identities = {
        identity for identity, count in Counter(identities).items() if count > 1
    }
    if duplicate_identities:
        formatted = "; ".join(map(repr, sorted(duplicate_identities)))
        raise ValueError(f"duplicate artifact identity: {formatted}")

    resolved: list[tuple[str, str]] = []
    displayed: dict[tuple[str, str], tuple[Path, Path]] = {}
    for row in valid_rows:
        metrics_path, targets_path = _artifact_paths(output_dir, row)
        identity = (
            os.path.normcase(str(metrics_path.resolve(strict=False))),
            os.path.normcase(str(targets_path.resolve(strict=False))),
        )
        resolved.append(identity)
        displayed.setdefault(identity, (metrics_path, targets_path))
    duplicate_paths = {identity for identity, count in Counter(resolved).items() if count > 1}
    if duplicate_paths:
        formatted = "; ".join(
            f"metrics={displayed[identity][0]}, targets={displayed[identity][1]}"
            for identity in sorted(duplicate_paths)
        )
        raise ValueError(f"duplicate resolved artifact paths: {formatted}")


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

    total_started = perf_counter()
    training_started = perf_counter()
    cpu_started = process_time()
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
    optimizer_cpu_seconds = process_time() - cpu_started
    training_seconds = perf_counter() - training_started
    front_started = perf_counter()
    front, proposals = summarize_front(population, context, feature_columns, config)
    selection_rule = SELECTION_RULES[str(row["scenario"])]
    selected = select_representative(front, selection_rule)
    policy_id = int(selected["id"])
    targets = realize_targets(context, proposals[policy_id], config)
    feasible_solutions = int(
        (front["constraint_penalty"] <= CONSTRAINT_TOLERANCE).sum()
    )
    front_evaluation_seconds = perf_counter() - front_started

    metric_row = {
        **_scalar_design_fields(row),
        "experiment": str(row["experiment"]),
        "sample_id": str(row["sample_id"]),
        "scenario": str(row["scenario"]),
        "seed": int(row["seed"]),
        **metadata,
        "duration_seconds": training_seconds,
        "training_seconds": training_seconds,
        "optimizer_cpu_seconds": optimizer_cpu_seconds,
        "front_evaluation_seconds": front_evaluation_seconds,
        "front_size": len(front),
        "feasible_solutions": feasible_solutions,
        "policy_id": policy_id,
        "selection_rule": selection_rule,
        "feasible": bool(selected["is_feasible"]),
        **_serialized_metrics(selected),
    }
    writing_started = perf_counter()
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
    artifact_writing_seconds = perf_counter() - writing_started
    total_duration_seconds = perf_counter() - total_started
    return RunArtifacts(
        "completed",
        metrics_path,
        targets_path,
        training_seconds=training_seconds,
        optimizer_cpu_seconds=optimizer_cpu_seconds,
        front_evaluation_seconds=front_evaluation_seconds,
        artifact_writing_seconds=artifact_writing_seconds,
        total_duration_seconds=total_duration_seconds,
    )


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


def _execute_row(
    context: pd.DataFrame,
    feature_columns: Sequence[str],
    row: Mapping[str, object],
    output_dir: Path,
    profile: str | ExperimentProfile,
    overwrite: bool,
) -> RunArtifacts:
    """Execute one row and convert model failures into terminal row state."""
    metrics_path: Path | None = None
    targets_path: Path | None = None
    try:
        metrics_path, targets_path = _artifact_paths(output_dir, row)
        return run_experiment_row(
            context,
            list(feature_columns),
            row,
            output_dir,
            profile,
            overwrite=overwrite,
        )
    except Exception as error:  # noqa: BLE001 - isolate arbitrary model failures
        return RunArtifacts(
            "failed",
            metrics_path,
            targets_path,
            type(error).__name__,
            str(error),
        )


def _optional_artifact_paths(
    output_dir: Path,
    row: Mapping[str, object],
) -> tuple[Path | None, Path | None]:
    """Return safe recovery paths without replacing an infrastructure error."""
    try:
        return _artifact_paths(output_dir, row)
    except Exception:  # noqa: BLE001 - recovery must retain the original failure
        return None, None


def _row_has_complete_artifacts(
    context: pd.DataFrame,
    feature_columns: Sequence[str],
    row: Mapping[str, object],
    output_dir: Path,
    profile: str | ExperimentProfile,
) -> bool:
    """Return whether a row already owns a complete current artifact pair."""
    try:
        metrics_path, targets_path = _artifact_paths(output_dir, row)
        config = _effective_config(row)
        metadata = _run_metadata(context, feature_columns, row, profile, config)
        return (
            metrics_path.exists()
            and targets_path.exists()
            and _stored_pair_matches(
                metrics_path,
                targets_path,
                metadata,
                len(context),
            )
        )
    except Exception:  # noqa: BLE001 - invalid model rows belong in worker results
        return False


def _terminal_result(
    prepared: pd.DataFrame,
    paths: tuple[Path, Path],
    position: int,
    row: Mapping[str, object],
    artifacts: RunArtifacts,
    started_at: str,
    worker_pid: int | None,
) -> dict[str, object]:
    """Persist one terminal result in the parent and return its audit row."""
    finished_at = _utc_now()
    returned_status = artifacts.status
    persisted_status = "completed" if returned_status == "skipped" else returned_status
    terminal = {
        "status": persisted_status,
        "finished_at": finished_at,
        "metrics_path": (
            str(artifacts.metrics_path) if artifacts.metrics_path is not None else None
        ),
        "targets_path": (
            str(artifacts.targets_path) if artifacts.targets_path is not None else None
        ),
        "error_type": artifacts.error_type,
        "error_message": artifacts.error_message,
        "worker_pid": worker_pid,
        "training_seconds": artifacts.training_seconds,
        "optimizer_cpu_seconds": artifacts.optimizer_cpu_seconds,
        "front_evaluation_seconds": artifacts.front_evaluation_seconds,
        "artifact_writing_seconds": artifacts.artifact_writing_seconds,
        "total_duration_seconds": artifacts.total_duration_seconds,
    }
    _update_manifest_row(prepared, paths, position, **terminal)
    return dict(row) | {
        "status": returned_status,
        "started_at": started_at,
        **{key: value for key, value in terminal.items() if key != "status"},
    }


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
    """Execute independent rows while the parent owns manifests and callbacks."""
    if isinstance(n_workers, bool) or not isinstance(n_workers, int) or n_workers < 1:
        raise ValueError("n_workers must be a positive integer")
    manifest_run_count(manifest)
    output_root = Path(output_dir)
    _preflight_artifacts(manifest, output_root)
    if manifest.empty:
        return manifest.copy()
    prepared = manifest.copy().reset_index(drop=True)
    prepared["cohort_signature"] = pd.Series(
        [None] * len(prepared), index=prepared.index, dtype=object
    )
    for positions in prepared.groupby("experiment", sort=False).groups.values():
        rows = prepared.loc[positions]
        prepared.loc[positions, "cohort_signature"] = _cohort_signature(
            rows,
            context,
            feature_columns,
            profile,
        )
    prepared["status"] = "pending"
    for column in (
        "started_at",
        "finished_at",
        "metrics_path",
        "targets_path",
        "error_type",
        "error_message",
        "worker_pid",
        "training_seconds",
        "optimizer_cpu_seconds",
        "front_evaluation_seconds",
        "artifact_writing_seconds",
        "total_duration_seconds",
    ):
        prepared[column] = pd.Series([None] * len(prepared), index=prepared.index, dtype=object)
    paths_by_experiment = _persist_manifest_copies(output_root, prepared)

    total = len(prepared)
    results: list[dict[str, object] | None] = [None] * total
    completed = 0
    pending: list[tuple[int, dict[str, object], str]] = []

    for position, row_series in prepared.iterrows():
        row = row_series.to_dict()
        started_at = _utc_now()
        manifest_paths = paths_by_experiment[str(row["experiment"])]
        if not overwrite and _row_has_complete_artifacts(
            context,
            feature_columns,
            row,
            output_root,
            profile,
        ):
            artifacts = RunArtifacts("skipped", *_artifact_paths(output_root, row))
            results[position] = _terminal_result(
                prepared,
                manifest_paths,
                position,
                row,
                artifacts,
                started_at,
                os.getpid(),
            )
            completed += 1
            if progress is not None:
                progress(completed, total, artifacts.status)
            continue

        _update_manifest_row(
            prepared,
            manifest_paths,
            position,
            status="running",
            started_at=started_at,
            error_type=None,
            error_message=None,
        )
        if n_workers == 1:
            artifacts = _execute_row(
                context,
                tuple(feature_columns),
                row,
                output_root,
                profile,
                overwrite,
            )
            results[position] = _terminal_result(
                prepared,
                manifest_paths,
                position,
                row,
                artifacts,
                started_at,
                os.getpid(),
            )
            completed += 1
            if progress is not None:
                progress(completed, total, artifacts.status)
        else:
            pending.append((position, row, started_at))

    if n_workers > 1 and pending:
        completed, infrastructure_error = _run_parallel_rows(
            context=context,
            feature_columns=tuple(feature_columns),
            output_root=output_root,
            profile=profile,
            overwrite=overwrite,
            n_workers=n_workers,
            prepared=prepared,
            paths_by_experiment=paths_by_experiment,
            pending=pending,
            results=results,
            completed=completed,
            total=total,
            progress=progress,
        )
        if infrastructure_error is not None:
            for position, row, started_at in pending:
                if results[position] is not None:
                    continue
                metrics_path, targets_path = _optional_artifact_paths(output_root, row)
                artifacts = RunArtifacts(
                    "failed",
                    metrics_path,
                    targets_path,
                    type(infrastructure_error).__name__,
                    str(infrastructure_error),
                )
                results[position] = _terminal_result(
                    prepared,
                    paths_by_experiment[str(row["experiment"])],
                    position,
                    row,
                    artifacts,
                    started_at,
                    None,
                )
                completed += 1
                if progress is not None:
                    progress(completed, total, artifacts.status)
            raise infrastructure_error

    return pd.DataFrame([result for result in results if result is not None])


def _run_parallel_rows(
    *,
    context: pd.DataFrame,
    feature_columns: tuple[str, ...],
    output_root: Path,
    profile: str | ExperimentProfile,
    overwrite: bool,
    n_workers: int,
    prepared: pd.DataFrame,
    paths_by_experiment: dict[str, tuple[Path, Path]],
    pending: list[tuple[int, dict[str, object], str]],
    results: list[dict[str, object] | None],
    completed: int,
    total: int,
    progress: Callable[[int, int, str], None] | None,
) -> tuple[int, Exception | None]:
    """Submit, drain, and reconcile every observable pool result."""
    executor: ProcessPoolExecutor | None = None
    futures: dict[object, tuple[int, dict[str, object], str]] = {}
    processed: set[object] = set()
    infrastructure_error: Exception | None = None
    try:
        executor = ProcessPoolExecutor(
            max_workers=n_workers,
            initializer=_initialize_worker,
            initargs=(context, feature_columns, output_root, profile, overwrite),
        )
        for position, row, started_at in pending:
            try:
                future = executor.submit(_run_worker, _WorkerRequest(position, row))
            except Exception as error:  # noqa: BLE001 - pool infrastructure
                infrastructure_error = error
                break
            futures[future] = (position, row, started_at)

        try:
            for future in as_completed(futures):
                processed.add(future)
                completed, error = _reconcile_future(
                    future,
                    futures[future],
                    prepared,
                    paths_by_experiment,
                    results,
                    completed,
                    total,
                    progress,
                )
                if infrastructure_error is None and error is not None:
                    infrastructure_error = error
        except Exception as error:  # noqa: BLE001 - pool infrastructure
            if infrastructure_error is None:
                infrastructure_error = error

        for future, request in futures.items():
            if future in processed:
                continue
            completed, error = _reconcile_future(
                future,
                request,
                prepared,
                paths_by_experiment,
                results,
                completed,
                total,
                progress,
            )
            if infrastructure_error is None and error is not None:
                infrastructure_error = error
    except Exception as error:  # noqa: BLE001 - pool startup infrastructure
        infrastructure_error = error
    finally:
        if executor is not None:
            try:
                executor.shutdown(wait=True)
            except Exception as error:  # noqa: BLE001 - pool infrastructure
                if infrastructure_error is None:
                    infrastructure_error = error
    return completed, infrastructure_error


def _reconcile_future(
    future: object,
    request: tuple[int, dict[str, object], str],
    prepared: pd.DataFrame,
    paths_by_experiment: dict[str, tuple[Path, Path]],
    results: list[dict[str, object] | None],
    completed: int,
    total: int,
    progress: Callable[[int, int, str], None] | None,
) -> tuple[int, Exception | None]:
    """Persist a completed future or report a process-pool infrastructure error."""
    position, row, started_at = request
    try:
        worker_result = future.result()  # type: ignore[attr-defined]
    except Exception as error:  # noqa: BLE001 - pool infrastructure
        return completed, error
    results[position] = _terminal_result(
        prepared,
        paths_by_experiment[str(row["experiment"])],
        position,
        row,
        worker_result.artifacts,
        started_at,
        worker_result.worker_pid,
    )
    completed += 1
    if progress is not None:
        progress(completed, total, worker_result.artifacts.status)
    return completed, None
