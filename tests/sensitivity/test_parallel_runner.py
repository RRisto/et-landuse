"""Contracts for parent-owned parallel historical sensitivity execution."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from estonia_landuse.sensitivity import runner
from estonia_landuse.sensitivity.config import ExperimentProfile
from estonia_landuse.sensitivity.runner import run_manifest

TINY_PROFILE = ExperimentProfile(pop_size=8, n_generations=2, hidden_size=4, use_seeds=False)
SCIENTIFIC_COLUMNS = [
    "experiment",
    "sample_id",
    "scenario",
    "seed",
    "front_size",
    "feasible_solutions",
    "policy_id",
    "selection_rule",
    "feasible",
    "biodiversity_gain",
    "carbon_gain",
    "cost",
    "changed_pct",
    "constraint_penalty",
]


@pytest.fixture
def parallel_context(minimal_context: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(
        [
            minimal_context,
            minimal_context.assign(
                cell_id=2,
                forest_pct=0.3,
                wetland_pct=0.2,
                agriculture_pct=0.2,
                grassland_pct=0.2,
                wetland_suitability=0.8,
                opportunity_cost_proxy=0.4,
            ),
        ],
        ignore_index=True,
    )


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "experiment": "baseline",
        "sample_id": "baseline",
        "scenario": "balanced",
        "seed": 2,
        "profile": "test",
        "overrides": {},
        "status": "pending",
    }
    row.update(changes)
    return row


def _manifest() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(),
            _row(sample_id="low-budget", scenario="low_budget", seed=3),
        ]
    )


def _targets(path: str) -> np.ndarray:
    with np.load(path) as archive:
        return np.asarray(archive["targets"])


def _make_directory_alias(target: Path, alias: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    alias.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode:
            pytest.skip(f"Could not create test junction: {completed.stderr}")
        return
    alias.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("n_workers", [0, -1, True])
def test_worker_count_is_positive_integer_before_any_write(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    n_workers: object,
) -> None:
    """Catch invalid concurrency reaching manifest persistence."""
    with pytest.raises(ValueError, match="n_workers must be a positive integer"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            _manifest(),
            tmp_path / "output",
            TINY_PROFILE,
            n_workers=n_workers,  # type: ignore[arg-type]
        )

    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("n_workers", [1, 2])
def test_duplicate_artifact_identities_fail_before_any_write(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    n_workers: int,
) -> None:
    """Catch raw and Windows-canonical aliases racing on one artifact pair."""
    manifest = pd.DataFrame([_row(seed=2), _row(seed="2")])
    output = tmp_path / "output"

    with pytest.raises(ValueError, match="duplicate artifact identity"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            manifest,
            output,
            TINY_PROFILE,
            n_workers=n_workers,
        )

    assert not output.exists()


@pytest.mark.parametrize(
    "experiments",
    [
        ("BASELINE", "baseline"),
        (1, "1"),
    ],
)
def test_duplicate_manifest_aliases_fail_before_any_write(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    experiments: tuple[object, object],
) -> None:
    """Catch distinct artifact rows sharing one Windows manifest identity."""
    manifest = pd.DataFrame(
        [
            _row(experiment=experiments[0], sample_id="first"),
            _row(experiment=experiments[1], sample_id="second", seed=3),
        ]
    )
    output = tmp_path / "output"

    with pytest.raises(ValueError, match="duplicate manifest identity"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            manifest,
            output,
            TINY_PROFILE,
        )

    assert not output.exists()


@pytest.mark.parametrize("n_workers", [1, 2])
def test_resolved_alias_escape_fails_before_manifest_or_artifact_writes(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    n_workers: int,
) -> None:
    """Catch a symlink or junction redirecting safe-looking paths outside the root."""
    output = tmp_path / "output"
    outside = tmp_path / "outside"
    _make_directory_alias(outside, output / "runs" / "baseline" / "escape")
    manifest = pd.DataFrame([_row(sample_id="escape")])

    with pytest.raises(ValueError, match="escapes output directory"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            manifest,
            output,
            TINY_PROFILE,
            n_workers=n_workers,
        )

    assert not (output / "manifests").exists()
    assert not list(outside.rglob("*.parquet"))
    assert not list(outside.rglob("*.npz"))


def test_input_order_does_not_depend_on_dataframe_index(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
) -> None:
    """Catch grouping or index sorting changing the caller's manifest order."""
    manifest = _manifest()
    manifest.index = [10, 5]

    result = run_manifest(
        parallel_context,
        ["wetland_suitability"],
        manifest,
        tmp_path,
        TINY_PROFILE,
        n_workers=1,
    )

    assert list(result["scenario"]) == ["balanced", "low_budget"]
    assert list(result["seed"]) == [2, 3]


def test_sequential_and_parallel_runs_have_identical_scientific_artifacts(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
) -> None:
    """Catch process-only drift in historical training, selection, or row ordering."""
    manifest = _manifest()
    sequential_progress: list[tuple[int, int, str]] = []
    parallel_progress: list[tuple[int, int, str]] = []
    sequential = run_manifest(
        parallel_context,
        ["wetland_suitability", "opportunity_cost_proxy"],
        manifest,
        tmp_path / "sequential",
        TINY_PROFILE,
        n_workers=1,
        progress=lambda done, total, status: sequential_progress.append((done, total, status)),
    )
    parallel = run_manifest(
        parallel_context,
        ["wetland_suitability", "opportunity_cost_proxy"],
        manifest,
        tmp_path / "parallel",
        TINY_PROFILE,
        n_workers=2,
        progress=lambda done, total, status: parallel_progress.append((done, total, status)),
    )

    assert parallel[["scenario", "seed"]].to_records(index=False).tolist() == (
        manifest[["scenario", "seed"]].to_records(index=False).tolist()
    )
    assert list(sequential["status"]) == ["completed", "completed"]
    assert list(parallel["status"]) == ["completed", "completed"]
    assert len(sequential_progress) == len(parallel_progress) == len(manifest)
    assert [event[:2] for event in sequential_progress] == [(1, 2), (2, 2)]
    assert [event[:2] for event in parallel_progress] == [(1, 2), (2, 2)]
    assert set(parallel["worker_pid"]).isdisjoint({os.getpid()})

    sequential_metrics = pd.concat(
        [pd.read_parquet(path) for path in sequential["metrics_path"]], ignore_index=True
    )
    parallel_metrics = pd.concat(
        [pd.read_parquet(path) for path in parallel["metrics_path"]], ignore_index=True
    )
    pd.testing.assert_frame_equal(
        sequential_metrics[SCIENTIFIC_COLUMNS],
        parallel_metrics[SCIENTIFIC_COLUMNS],
        check_exact=False,
        rtol=1e-12,
    )
    np.testing.assert_allclose(
        np.stack([_targets(path) for path in sequential["targets_path"]]),
        np.stack([_targets(path) for path in parallel["targets_path"]]),
    )


def test_only_parent_updates_manifests_and_invokes_progress(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch child processes taking ownership of manifests or callbacks."""
    update_pids: list[int] = []
    callback_pids: list[int] = []
    original_update = runner._update_manifest_row

    def record_update(*args: object, **kwargs: object) -> None:
        update_pids.append(os.getpid())
        original_update(*args, **kwargs)

    monkeypatch.setattr(runner, "_update_manifest_row", record_update)
    run_manifest(
        parallel_context,
        ["wetland_suitability"],
        _manifest(),
        tmp_path,
        TINY_PROFILE,
        n_workers=2,
        progress=lambda *_: callback_pids.append(os.getpid()),
    )

    assert update_pids and set(update_pids) == {os.getpid()}
    assert callback_pids and set(callback_pids) == {os.getpid()}


def test_worker_failure_is_row_level_and_preserves_completed_rows(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
) -> None:
    """Catch one model exception aborting or corrupting the rest of a cohort."""
    manifest = pd.DataFrame(
        [
            _row(sample_id="invalid", scenario="unknown"),
            _row(sample_id="valid", scenario="balanced", seed=3),
        ]
    )
    result = run_manifest(
        parallel_context,
        ["wetland_suitability"],
        manifest,
        tmp_path,
        TINY_PROFILE,
        n_workers=2,
    )

    assert list(result["status"]) == ["failed", "completed"]
    assert result.loc[0, "error_type"] == "ValueError"
    persisted = pd.read_csv(tmp_path / "manifests" / "baseline.csv")
    assert list(persisted["status"]) == ["failed", "completed"]


class _StartupFailure:
    def __init__(self, **_: object) -> None:
        raise RuntimeError("pool startup failed")


def test_pool_startup_failure_terminalizes_all_running_rows(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch executor construction failure leaving stale running rows."""
    monkeypatch.setattr(runner, "ProcessPoolExecutor", _StartupFailure, raising=False)

    with pytest.raises(RuntimeError, match="pool startup failed"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            _manifest(),
            tmp_path,
            TINY_PROFILE,
            n_workers=2,
        )

    persisted = pd.read_csv(tmp_path / "manifests" / "baseline.csv")
    assert set(persisted["status"]) == {"failed"}
    assert "running" not in set(persisted["status"])


def test_stale_running_rows_backed_by_artifacts_are_repaired_without_dispatch(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch interrupted manifest state forcing valid artifacts to rerun."""
    manifest = pd.DataFrame([_row()])
    run_manifest(
        parallel_context,
        ["wetland_suitability"],
        manifest,
        tmp_path,
        TINY_PROFILE,
    )
    for path in (tmp_path / "manifests").glob("*.csv"):
        persisted = pd.read_csv(path)
        persisted.loc[:, "status"] = "running"
        persisted.to_csv(path, index=False, lineterminator="\n")

    def reject_pool(**_: object) -> object:
        raise AssertionError("valid artifacts were dispatched")

    monkeypatch.setattr(runner, "ProcessPoolExecutor", reject_pool, raising=False)
    resumed = run_manifest(
        parallel_context,
        ["wetland_suitability"],
        manifest,
        tmp_path,
        TINY_PROFILE,
        n_workers=2,
    )

    assert list(resumed["status"]) == ["skipped"]
    assert all(
        set(pd.read_csv(path)["status"]) == {"completed"}
        for path in (tmp_path / "manifests").glob("*.csv")
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows lock semantics")
def test_locked_manifest_alias_fails_before_optimizer_dispatch(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a locked stable alias allowing artifact work without status ownership."""
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    alias = manifest_dir / "baseline.csv"
    alias.write_text("locked", encoding="utf-8")

    def reject_pool(**_: object) -> object:
        raise AssertionError("optimizer dispatched before manifests were writable")

    monkeypatch.setattr(runner, "ProcessPoolExecutor", reject_pool, raising=False)
    with alias.open("r+"):
        with pytest.raises(PermissionError):
            run_manifest(
                parallel_context,
                ["wetland_suitability"],
                _manifest(),
                tmp_path,
                TINY_PROFILE,
                n_workers=2,
            )

    assert not (tmp_path / "runs").exists()


class _InlineFutureExecutor:
    """Small deterministic process-pool double for infrastructure recovery."""

    def __init__(self, *, initializer: object, initargs: tuple[object, ...], **_: object) -> None:
        initializer(*initargs)  # type: ignore[operator]
        self.submissions = 0

    def submit(self, function: object, request: object) -> Future[object]:
        self.submissions += 1
        if self.submissions == 2:
            raise RuntimeError("submit infrastructure failed")
        future: Future[object] = Future()
        future.set_result(function(request))  # type: ignore[operator]
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        assert wait
        assert not cancel_futures


def test_submit_failure_reconciles_completed_and_unresolved_rows(
    tmp_path: Path,
    parallel_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch partial pool startup corrupting completed work or stranding rows."""
    monkeypatch.setattr(runner, "ProcessPoolExecutor", _InlineFutureExecutor, raising=False)
    manifest = pd.DataFrame([_row(), _row(sample_id="second", seed=3)])

    with pytest.raises(RuntimeError, match="submit infrastructure failed"):
        run_manifest(
            parallel_context,
            ["wetland_suitability"],
            manifest,
            tmp_path,
            TINY_PROFILE,
            n_workers=2,
        )

    persisted = pd.read_csv(tmp_path / "manifests" / "baseline.csv")
    assert list(persisted["status"]) == ["completed", "failed"]
    assert "running" not in set(persisted["status"])
