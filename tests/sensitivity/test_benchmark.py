"""Contracts for timing historical sequential and parallel manifests."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from estonia_landuse.sensitivity.config import ExperimentProfile
from estonia_landuse.sensitivity.runner import run_manifest

TINY_PROFILE = ExperimentProfile(pop_size=8, n_generations=2, hidden_size=4, use_seeds=False)


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "experiment": "baseline",
        "sample_id": "baseline",
        "scenario": "balanced",
        "seed": 5,
        "profile": "test",
        "overrides": {},
        "status": "pending",
    }
    row.update(changes)
    return row


def test_benchmark_reports_wall_cpu_and_relative_speedup(
    tmp_path: Path,
    minimal_context: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch benchmark runs escaping their caller-owned artifact root."""
    benchmark = importlib.import_module("estonia_landuse.sensitivity.benchmark")
    calls: list[tuple[Path, int, pd.DataFrame]] = []
    clock = iter([10.0, 14.0, 20.0, 22.0])

    def fake_run_manifest(
        context: pd.DataFrame,
        feature_columns: list[str],
        manifest: pd.DataFrame,
        output_dir: Path,
        profile: ExperimentProfile,
        *,
        overwrite: bool,
        n_workers: int,
    ) -> pd.DataFrame:
        assert context is minimal_context
        assert feature_columns == ["wetland_suitability"]
        assert profile == TINY_PROFILE
        assert overwrite
        calls.append((Path(output_dir), n_workers, manifest.copy()))
        cpu = [1.25, 1.75] if n_workers == 1 else [0.75, 1.25]
        return pd.DataFrame(
            {
                "status": ["completed", "completed"],
                "optimizer_cpu_seconds": cpu,
            }
        )

    monkeypatch.setattr(benchmark, "run_manifest", fake_run_manifest)
    monkeypatch.setattr(benchmark, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(benchmark.os, "cpu_count", lambda: 8)
    manifest = pd.DataFrame([_row(), _row(sample_id="second", seed=6)])

    report = benchmark.benchmark_manifest(
        minimal_context,
        ["wetland_suitability"],
        manifest,
        TINY_PROFILE,
        work_root=tmp_path / "benchmark-work",
    )

    assert list(report["execution_mode"]) == ["sequential", "parallel"]
    assert list(report["n_workers"]) == [1, 2]
    assert list(report["wall_seconds"]) == [4.0, 2.0]
    assert list(report["optimizer_cpu_seconds"]) == [3.0, 2.0]
    assert list(report["speedup"]) == [1.0, 2.0]
    assert list(report["run_count"]) == [2, 2]
    assert len(calls) == 2
    assert calls[0][0] == tmp_path / "benchmark-work" / "sequential"
    assert calls[1][0] == tmp_path / "benchmark-work" / "parallel"
    assert all(path.is_relative_to(tmp_path / "benchmark-work") for path, _, _ in calls)
    pd.testing.assert_frame_equal(calls[0][2], manifest)
    pd.testing.assert_frame_equal(calls[1][2], manifest)


def test_runner_records_each_timing_phase(
    tmp_path: Path,
    minimal_context: pd.DataFrame,
) -> None:
    """Catch benchmark inputs omitting optimizer, evaluation, write, or total timing."""
    result = run_manifest(
        minimal_context,
        ["wetland_suitability"],
        pd.DataFrame([_row()]),
        tmp_path,
        TINY_PROFILE,
    )

    timing_columns = [
        "training_seconds",
        "optimizer_cpu_seconds",
        "front_evaluation_seconds",
        "artifact_writing_seconds",
        "total_duration_seconds",
    ]
    assert result[timing_columns].notna().all().all()
    assert (result[timing_columns] >= 0.0).all().all()
    assert result.loc[0, "total_duration_seconds"] >= sum(
        result.loc[
            0,
            ["training_seconds", "front_evaluation_seconds", "artifact_writing_seconds"],
        ]
    )
    metrics = pd.read_parquet(result.loc[0, "metrics_path"])
    assert {
        "duration_seconds",
        "training_seconds",
        "optimizer_cpu_seconds",
        "front_evaluation_seconds",
    }.issubset(metrics.columns)
