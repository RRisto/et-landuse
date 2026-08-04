"""Integration contracts for the sequential historical artifact runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from estonia_landuse.scenarios import select_representative
from estonia_landuse.sensitivity import runner
from estonia_landuse.sensitivity.config import resolve_profile
from estonia_landuse.sensitivity.historical_model import (
    SELECTION_RULES,
    make_historical_scenario_config,
)
from estonia_landuse.sensitivity.runner import run_experiment_row, run_manifest
from estonia_landuse.simulator.simulator import summarize_policy


@dataclass
class FixedPolicy:
    """Small trainer output double; the simulator and selection remain real."""

    target: np.ndarray
    rank: int

    def prescribe(self, features: np.ndarray) -> np.ndarray:
        assert features.ndim == 2
        return np.repeat(self.target[None, :], len(features), axis=0)


@dataclass
class NonFrontPolicy:
    """Fail if the runner evaluates a policy outside historical rank zero."""

    rank: int = 1

    def prescribe(self, features: np.ndarray) -> np.ndarray:
        raise AssertionError("rank-one policies must not be reported")


@pytest.fixture
def runner_context(minimal_context: pd.DataFrame) -> pd.DataFrame:
    first = minimal_context.copy()
    second = minimal_context.assign(
        cell_id=2,
        forest_pct=0.3,
        wetland_pct=0.2,
        agriculture_pct=0.2,
        grassland_pct=0.2,
        wetland_suitability=0.8,
        opportunity_cost_proxy=0.4,
    )
    return pd.concat([first, second], ignore_index=True)


@pytest.fixture
def fixed_population() -> list[object]:
    return [
        FixedPolicy(np.array([0.40, 0.10, 0.30, 0.10]), rank=0),
        FixedPolicy(np.array([0.50, 0.20, 0.10, 0.10]), rank=0),
        NonFrontPolicy(),
    ]


@pytest.fixture
def trainer_spy(
    monkeypatch: pytest.MonkeyPatch,
    fixed_population: list[object],
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_train(
        context: pd.DataFrame,
        feature_columns: list[str],
        **kwargs: object,
    ) -> list[object]:
        calls.append(
            {
                "context": context,
                "feature_columns": feature_columns,
                **kwargs,
            }
        )
        return fixed_population

    monkeypatch.setattr(runner, "train", fake_train)
    return calls


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "experiment": "baseline",
        "sample_id": "baseline",
        "scenario": "wetland_priority",
        "seed": 73,
        "profile": "test",
        "overrides": {},
        "status": "pending",
    }
    row.update(changes)
    return row


def _normalized_features(context: pd.DataFrame, columns: list[str]) -> np.ndarray:
    features = context[columns].to_numpy(dtype=np.float32)
    standard_deviation = features.std(axis=0)
    standard_deviation[standard_deviation == 0] = 1.0
    return (features - features.mean(axis=0)) / standard_deviation


def test_single_run_uses_seed_and_historical_representative(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    fixed_population: list[object],
    trainer_spy: list[dict[str, object]],
) -> None:
    """Catch lost RNG identity or replacement of scenario-specific selection."""
    feature_columns = ["wetland_suitability", "opportunity_cost_proxy"]

    artifacts = run_experiment_row(
        runner_context,
        feature_columns,
        _row(),
        tmp_path,
        resolve_profile("test"),
    )

    assert artifacts.status == "completed"
    assert len(trainer_spy) == 1
    assert trainer_spy[0]["seed"] == 73
    assert trainer_spy[0]["use_seeds"] is False
    effective_config = make_historical_scenario_config("wetland_priority")
    assert trainer_spy[0]["config"] == effective_config

    features = _normalized_features(runner_context, feature_columns)
    expected_front = pd.DataFrame(
        [
            {
                "id": policy_id,
                **summarize_policy(
                    runner_context,
                    policy.prescribe(features),
                    effective_config,
                ),
            }
            for policy_id, policy in enumerate(fixed_population[:2])
        ]
    )
    expected = select_representative(
        expected_front,
        SELECTION_RULES["wetland_priority"],
    )
    stored = pd.read_parquet(artifacts.metrics_path).iloc[0]

    assert stored["policy_id"] == expected["id"]
    assert stored["scenario"] == "wetland_priority"
    assert stored["selection_rule"] == "wetland_priority"
    assert stored["constraint_penalty"] == pytest.approx(expected["constraint_penalty"])
    assert "agriculture_loss" in stored
    assert "agriculture_loss_pct" not in stored.index
    assert json.loads(stored["scenario_config_json"])["optimization"]["fourth_objective"] == (
        "wetland_gain_pct"
    )


def test_artifact_identity_and_resume_require_a_complete_matching_pair(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    trainer_spy: list[dict[str, object]],
) -> None:
    """Catch stale or half-written artifacts being treated as completed work."""
    feature_columns = ["wetland_suitability", "opportunity_cost_proxy"]
    row = _row()

    first = run_experiment_row(
        runner_context,
        feature_columns,
        row,
        tmp_path,
        "test",
    )
    assert first.metrics_path.parts[-5:] == (
        "runs",
        "baseline",
        "baseline",
        "wetland_priority",
        "seed_73.parquet",
    )
    assert first.targets_path.with_suffix(".parquet") == first.metrics_path
    stored = pd.read_parquet(first.metrics_path).iloc[0]
    assert len(stored["configuration_fingerprint"]) == 64
    assert len(stored["input_fingerprint"]) == 64
    with np.load(first.targets_path) as archive:
        assert archive["configuration_fingerprint"].item() == stored["configuration_fingerprint"]
        assert archive["input_fingerprint"].item() == stored["input_fingerprint"]
        assert archive["targets"].shape == (len(runner_context), 4)

    matching = run_experiment_row(
        runner_context,
        feature_columns,
        row,
        tmp_path,
        "test",
    )
    assert matching.status == "skipped"
    assert len(trainer_spy) == 1

    changed = run_experiment_row(
        runner_context,
        feature_columns,
        _row(overrides={"max_changed_pct": 0.05}),
        tmp_path,
        "test",
    )
    assert changed.status == "completed"
    assert len(trainer_spy) == 2
    changed_fingerprint = pd.read_parquet(changed.metrics_path).iloc[0][
        "configuration_fingerprint"
    ]
    assert changed_fingerprint != stored["configuration_fingerprint"]

    changed.targets_path.unlink()
    repaired = run_experiment_row(
        runner_context,
        feature_columns,
        _row(overrides={"max_changed_pct": 0.05}),
        tmp_path,
        "test",
    )
    assert repaired.status == "completed"
    assert len(trainer_spy) == 3
    assert repaired.targets_path.exists()
    assert not [path for path in repaired.targets_path.parent.iterdir() if path.name.startswith(".")]


@pytest.mark.parametrize("corruption", ["empty", "truncated"])
def test_corrupt_target_archive_is_recomputed(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    trainer_spy: list[dict[str, object]],
    corruption: str,
) -> None:
    """Catch an unreadable NPZ aborting resume instead of being repaired."""
    feature_columns = ["wetland_suitability", "opportunity_cost_proxy"]
    first = run_experiment_row(
        runner_context,
        feature_columns,
        _row(),
        tmp_path,
        "test",
    )
    assert first.targets_path is not None
    contents = first.targets_path.read_bytes()
    damaged = b"" if corruption == "empty" else contents[: len(contents) // 2]
    first.targets_path.write_bytes(damaged)

    repaired = run_experiment_row(
        runner_context,
        feature_columns,
        _row(),
        tmp_path,
        "test",
    )

    assert repaired.status == "completed"
    assert len(trainer_spy) == 2
    assert repaired.targets_path is not None
    with np.load(repaired.targets_path) as archive:
        assert archive["targets"].shape == (len(runner_context), 4)


@pytest.mark.parametrize(
    ("scenario", "overrides"),
    [
        ("wetland_priority", {"optimization.fourth_objective": "changed_pct"}),
        ("balanced", {"optimization": {"fourth_objective": "wetland_gain_pct"}}),
    ],
)
def test_overrides_cannot_change_the_historical_fourth_objective(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    trainer_spy: list[dict[str, object]],
    scenario: str,
    overrides: dict[str, object],
) -> None:
    """Catch a sensitivity row silently changing historical objective semantics."""
    with pytest.raises(ValueError, match="historical fourth objective"):
        run_experiment_row(
            runner_context,
            ["wetland_suitability"],
            _row(scenario=scenario, overrides=overrides),
            tmp_path,
            "test",
        )

    assert not trainer_spy
    assert not list(tmp_path.iterdir())


def test_manifest_parent_persists_terminal_statuses_and_cohort_alias(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    trainer_spy: list[dict[str, object]],
) -> None:
    """Catch row failures aborting the cohort or manifests remaining nonterminal."""
    manifest = pd.DataFrame(
        [
            _row(),
            _row(sample_id="invalid", scenario="not_a_scenario", seed=74),
        ]
    )
    progress: list[tuple[int, int, str]] = []

    result = run_manifest(
        runner_context,
        ["wetland_suitability", "opportunity_cost_proxy"],
        manifest,
        tmp_path,
        "test",
        progress=lambda completed, total, status: progress.append((completed, total, status)),
    )

    assert list(result["status"]) == ["completed", "failed"]
    assert result["started_at"].notna().all()
    assert result["finished_at"].notna().all()
    assert result.loc[1, "error_type"] == "ValueError"
    assert progress == [(1, 2, "completed"), (2, 2, "failed")]

    alias = tmp_path / "manifests" / "baseline.csv"
    cohort_paths = list((tmp_path / "manifests").glob("baseline-*.csv"))
    assert alias.exists()
    assert len(cohort_paths) == 1
    persisted = pd.read_csv(alias)
    assert list(persisted["status"]) == ["completed", "failed"]
    assert persisted.loc[1, "error_type"] == "ValueError"


def test_each_experiment_manifest_contains_only_its_own_cohort(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    trainer_spy: list[dict[str, object]],
) -> None:
    """Catch a status update leaking other experiments into an alias file."""
    manifest = pd.DataFrame(
        [
            _row(),
            _row(experiment="oat", sample_id="oat__budget", seed=74),
        ]
    )

    run_manifest(
        runner_context,
        ["wetland_suitability", "opportunity_cost_proxy"],
        manifest,
        tmp_path,
        "test",
    )

    baseline = pd.read_csv(tmp_path / "manifests" / "baseline.csv")
    oat = pd.read_csv(tmp_path / "manifests" / "oat.csv")
    assert list(baseline["experiment"]) == ["baseline"]
    assert list(oat["experiment"]) == ["oat"]


def test_manifest_path_traversal_is_rejected_before_any_write(
    tmp_path: Path,
    runner_context: pd.DataFrame,
) -> None:
    """Catch a raw experiment value escaping the manifest directory."""
    output_dir = tmp_path / "output"
    manifest = pd.DataFrame(
        [
            _row(),
            _row(experiment="../../escaped", sample_id="escaped", seed=74),
        ]
    )

    with pytest.raises(ValueError, match="unsafe artifact path component for experiment"):
        run_manifest(
            runner_context,
            ["wetland_suitability"],
            manifest,
            output_dir,
            "test",
        )

    assert not output_dir.exists()
    assert not list(tmp_path.glob("escaped*"))


@pytest.mark.parametrize(
    "row_changes",
    [
        {"sample_id": "../unsafe"},
        {"seed": "not-an-integer"},
    ],
)
def test_invalid_artifact_key_becomes_a_terminal_row_failure(
    tmp_path: Path,
    runner_context: pd.DataFrame,
    row_changes: dict[str, object],
) -> None:
    """Catch unsafe failure fallback leaving a persisted row as running."""
    output_dir = tmp_path / "output"
    progress: list[tuple[int, int, str]] = []

    result = run_manifest(
        runner_context,
        ["wetland_suitability"],
        pd.DataFrame([_row(**row_changes)]),
        output_dir,
        "test",
        progress=lambda completed, total, status: progress.append((completed, total, status)),
    )

    assert list(result["status"]) == ["failed"]
    assert result.loc[0, "error_type"] in {"ValueError", "TypeError"}
    assert pd.isna(result.loc[0, "metrics_path"])
    assert pd.isna(result.loc[0, "targets_path"])
    assert progress == [(1, 1, "failed")]
    persisted = pd.read_csv(output_dir / "manifests" / "baseline.csv")
    assert list(persisted["status"]) == ["failed"]
    assert not (tmp_path / "unsafe").exists()


def test_sequential_runner_rejects_parallel_workers(
    tmp_path: Path,
    runner_context: pd.DataFrame,
) -> None:
    """Catch Task 3 silently pretending to support parent-safe parallelism."""
    with pytest.raises(ValueError, match="n_workers=1"):
        run_manifest(
            runner_context,
            ["wetland_suitability"],
            pd.DataFrame([_row()]),
            tmp_path,
            "test",
            n_workers=2,
        )
