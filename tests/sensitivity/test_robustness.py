"""Robustness synthesis contracts for historical sensitivity artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from estonia_landuse.sensitivity.robustness import (
    build_robustness_report,
    classify_interactions,
    classify_parameter_importance,
    inventory_artifacts,
    missing_manifest_rows,
    summarize_scenario_rank_stability,
    summarize_spatial_robustness,
)

IDENTITY = {
    "artifact_schema_version": 1,
    "profile": "test",
    "input_fingerprint": "input-a",
    "code_fingerprint": "code-a",
}


def _write_artifact(
    root: Path,
    *,
    experiment: str = "biodiversity",
    sample_id: str = "biodiversity__current",
    scenario: str = "balanced",
    seed: int = 0,
    metric: float = 1.0,
    identity: dict[str, object] | None = None,
    with_targets: bool = True,
    overrides: dict[str, object] | None = None,
) -> None:
    run_identity = {**IDENTITY, **(identity or {})}
    run_signature = f"{experiment}-{sample_id}-{scenario}-{seed}"
    configuration = f"config-{sample_id}-{scenario}"
    assumption = sample_id.removeprefix("biodiversity__")
    design = {
        "experiment": experiment,
        "sample_id": sample_id,
        "scenario": scenario,
        "seed": seed,
        "profile": str(run_identity["profile"]),
        "overrides": overrides or {},
    }
    if experiment == "biodiversity":
        design["biodiversity_assumption"] = assumption
    design.update(
        {
            "worker_pid": None,
            "training_seconds": None,
            "optimizer_cpu_seconds": None,
            "front_evaluation_seconds": None,
            "artifact_writing_seconds": None,
            "total_duration_seconds": None,
        }
    )
    directory = root / "runs" / experiment / sample_id / scenario
    directory.mkdir(parents=True, exist_ok=True)
    metrics_path = directory / f"seed_{seed}.parquet"
    pd.DataFrame(
        [
            {
                "experiment": experiment,
                "sample_id": sample_id,
                "scenario": scenario,
                "seed": seed,
                **run_identity,
                "configuration_fingerprint": configuration,
                "run_signature": run_signature,
                "manifest_design_json": json.dumps(
                    design, sort_keys=True, separators=(",", ":")
                ),
                "biodiversity_gain": metric,
                "carbon_gain": metric / 2,
                "cost": 2 - metric,
                "changed_pct": metric / 3,
                "biodiversity_assumption": assumption,
            }
        ]
    ).to_parquet(metrics_path, index=False)
    if with_targets:
        np.savez_compressed(
            metrics_path.with_suffix(".npz"),
            targets=np.array([[0.7, 0.1, 0.1, 0.1], [0.1, 0.7, 0.1, 0.1]]),
            current_fractions=np.array([[0.4, 0.2, 0.2, 0.2], [0.2, 0.3, 0.3, 0.2]]),
            cell_ids=np.array([10, 11]),
            artifact_schema_version=run_identity["artifact_schema_version"],
            input_fingerprint=run_identity["input_fingerprint"],
            configuration_fingerprint=configuration,
            code_fingerprint=run_identity["code_fingerprint"],
            run_signature=run_signature,
        )


def _write_latest_manifest(
    root: Path, experiment: str, rows: list[dict[str, object]]
) -> None:
    prepared: list[dict[str, object]] = []
    for supplied in rows:
        row = {
            "experiment": experiment,
            "sample_id": "biodiversity__current",
            "scenario": "balanced",
            "seed": 0,
            "profile": "test",
            "overrides": {},
            "status": "completed",
            **supplied,
        }
        if experiment == "biodiversity":
            row.setdefault(
                "biodiversity_assumption",
                str(row["sample_id"]).removeprefix("biodiversity__"),
            )
        row["overrides"] = json.dumps(
            row["overrides"], sort_keys=True, separators=(",", ":")
        )
        prepared.append(row)
    path = root / "manifests" / f"{experiment}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prepared).to_csv(path, index=False)


def test_inventory_reuses_only_complete_single_identity_artifacts(tmp_path: Path) -> None:
    _write_artifact(tmp_path, seed=0)
    _write_artifact(tmp_path, seed=1, with_targets=False)
    _write_artifact(tmp_path, seed=2, identity={"profile": "screen"})

    inventory = inventory_artifacts(tmp_path, "test")

    assert list(inventory.complete["seed"]) == [0]
    assert inventory.incomplete["reason"].tolist() == ["missing_targets"]
    assert inventory.identity == ("test", "input-a", "code-a", 1)


def test_inventory_rejects_mixed_model_or_input_identity(tmp_path: Path) -> None:
    _write_artifact(tmp_path, seed=0)
    _write_artifact(tmp_path, seed=1, identity={"code_fingerprint": "code-b"})

    with pytest.raises(ValueError, match="multiple artifact identities"):
        inventory_artifacts(tmp_path, "test")


def test_missing_manifest_rows_never_reschedules_completed_execution_keys(
    tmp_path: Path,
) -> None:
    _write_artifact(tmp_path, seed=0)
    inventory = inventory_artifacts(tmp_path, "test")
    manifest = pd.DataFrame(
        [
            {
                "experiment": "biodiversity",
                "sample_id": "biodiversity__current",
                "scenario": "balanced",
                "seed": seed,
                "profile": "test",
                "overrides": {},
                "biodiversity_assumption": "current",
            }
            for seed in (0, 1)
        ]
    )

    missing = missing_manifest_rows(manifest, inventory)

    assert list(missing["seed"]) == [1]


def test_missing_manifest_rows_reschedules_same_key_with_different_design(
    tmp_path: Path,
) -> None:
    _write_artifact(tmp_path, overrides={"scoring.base_change_cost": 0.3})
    inventory = inventory_artifacts(tmp_path, "test")
    manifest = pd.DataFrame(
        [
            {
                "experiment": "biodiversity",
                "sample_id": "biodiversity__current",
                "scenario": "balanced",
                "seed": 0,
                "profile": "test",
                "biodiversity_assumption": "current",
                "overrides": {"scoring.base_change_cost": 1.0},
            }
        ]
    )

    assert len(missing_manifest_rows(manifest, inventory)) == 1


def test_incompatible_expected_identity_is_not_reused(tmp_path: Path) -> None:
    _write_artifact(tmp_path, seed=0)
    expected = ("test", "different-input", "code-a", 1)

    inventory = inventory_artifacts(tmp_path, "test", expected_identity=expected)

    assert inventory.complete.empty
    assert inventory.incomplete["reason"].tolist() == ["incompatible_identity"]


def test_rank_stability_excludes_incomplete_comparison_groups() -> None:
    runs = pd.DataFrame(
        [
            {"sample_id": "a", "seed": 0, "scenario": "green", "biodiversity_gain": 3.0},
            {"sample_id": "a", "seed": 0, "scenario": "balanced", "biodiversity_gain": 1.0},
            {"sample_id": "b", "seed": 0, "scenario": "green", "biodiversity_gain": 1.0},
            {"sample_id": "b", "seed": 0, "scenario": "balanced", "biodiversity_gain": 2.0},
            {"sample_id": "incomplete", "seed": 0, "scenario": "green", "biodiversity_gain": 99.0},
        ]
    )

    result = summarize_scenario_rank_stability(
        runs, "biodiversity_gain", expected_scenarios=("green", "balanced")
    ).set_index("scenario")

    assert result.loc["green", "first_place_frequency"] == pytest.approx(0.5)
    assert result.loc["green", "median_rank"] == pytest.approx(1.5)
    assert result.loc["green", "comparison_count"] == 2
    assert result.loc["balanced", "comparison_count"] == 2


def test_spatial_robustness_reports_modal_action_agreement_and_target_moments() -> None:
    targets = pd.DataFrame(
        [
            {"scenario": "balanced", "comparison_id": "a", "cell_id": 10, "forest": 0.7, "wetland": 0.1, "agriculture": 0.1, "grassland": 0.1, "current_forest": 0.4, "current_wetland": 0.2, "current_agriculture": 0.2, "current_grassland": 0.2},
            {"scenario": "balanced", "comparison_id": "b", "cell_id": 10, "forest": 0.6, "wetland": 0.2, "agriculture": 0.1, "grassland": 0.1, "current_forest": 0.4, "current_wetland": 0.2, "current_agriculture": 0.2, "current_grassland": 0.2},
            {"scenario": "balanced", "comparison_id": "c", "cell_id": 10, "forest": 0.3, "wetland": 0.5, "agriculture": 0.1, "grassland": 0.1, "current_forest": 0.4, "current_wetland": 0.2, "current_agriculture": 0.2, "current_grassland": 0.2},
        ]
    )

    result = summarize_spatial_robustness(targets).iloc[0]

    assert result["modal_action"] == "forest"
    assert result["action_agreement"] == pytest.approx(2 / 3)
    assert result["forest_target_mean"] == pytest.approx(0.5333333333)
    assert result["forest_target_sd"] == pytest.approx(np.std([0.7, 0.6, 0.3], ddof=1))
    assert result["comparison_count"] == 3


def test_report_writes_completeness_and_unavailable_evidence(tmp_path: Path) -> None:
    _write_artifact(tmp_path, seed=0)
    _write_latest_manifest(tmp_path, "biodiversity", [{"seed": 0}])
    paths = build_robustness_report(tmp_path, tmp_path / "report", "test")

    assert set(paths) >= {"completeness", "rank_stability", "spatial_robustness", "conclusions"}
    completeness = pd.read_csv(paths["completeness"]).set_index("experiment")
    assert completeness.loc["biodiversity", "complete_runs"] == 1
    assert completeness.loc["baseline", "availability"] == "unavailable"
    conclusions = pd.read_json(paths["conclusions"], typ="series")
    assert conclusions["parameter_importance"] == "unavailable"
    for name in ("rank_stability", "parameter_importance", "interactions", "spatial_robustness"):
        pd.read_csv(paths[name])


def test_report_rejects_false_complete_same_count_custom_cohort(tmp_path: Path) -> None:
    _write_artifact(tmp_path, sample_id="biodiversity__custom-a", seed=0)
    _write_artifact(tmp_path, sample_id="biodiversity__custom-b", seed=0)
    _write_latest_manifest(
        tmp_path,
        "biodiversity",
        [
            {"sample_id": "biodiversity__current", "seed": 0},
            {"sample_id": "biodiversity__forest_focused", "seed": 0},
        ],
    )

    paths = build_robustness_report(tmp_path, tmp_path / "report", "test")
    completeness = pd.read_csv(paths["completeness"]).set_index("experiment")
    conclusions = json.loads(paths["conclusions"].read_text(encoding="utf-8"))

    assert completeness.loc["biodiversity", "expected_runs"] == 2
    assert completeness.loc["biodiversity", "complete_runs"] == 0
    assert completeness.loc["biodiversity", "availability"] == "incomplete"
    assert conclusions["excluded_manifest_artifacts"] == 2


def test_report_counts_and_withholds_incomplete_comparison_groups(tmp_path: Path) -> None:
    _write_artifact(tmp_path, scenario="green", seed=0)
    _write_latest_manifest(
        tmp_path,
        "biodiversity",
        [
            {"scenario": "green", "seed": 0},
            {"scenario": "balanced", "seed": 0},
        ],
    )

    paths = build_robustness_report(tmp_path, tmp_path / "report", "test")
    groups = pd.read_csv(paths["comparison_groups"])
    conclusions = json.loads(paths["conclusions"].read_text(encoding="utf-8"))

    assert len(groups) == 1
    assert groups.loc[0, "status"] == "excluded"
    assert json.loads(groups.loc[0, "missing_scenarios"]) == ["balanced"]
    assert conclusions["expected_comparison_group_count"] == 1
    assert conclusions["complete_comparison_group_count"] == 0
    assert conclusions["excluded_comparison_group_keys"] == [
        "biodiversity__current|seed=0"
    ]
    assert conclusions["scenario_rank_stability"] == "unavailable"
    assert pd.read_csv(paths["rank_stability"]).empty


def test_parameter_importance_requires_fit_rank_and_uncertainty() -> None:
    base = pd.DataFrame(
        [
            {
                "held_out_r2": 0.6,
                "top_parameter_rank_consistent": True,
                "top_parameter_uncertainty_pass": True,
                "model_fit_pass": True,
            }
        ]
    )

    assert classify_parameter_importance(base) == "stable"
    assert classify_parameter_importance(base.assign(held_out_r2=0.0)) == "unstable"
    assert classify_parameter_importance(
        base.assign(top_parameter_uncertainty_pass=False)
    ) == "unstable"
    assert classify_parameter_importance(pd.DataFrame()) == "unavailable"


def test_interaction_conclusion_uses_baseline_noise_scale() -> None:
    tiny_absolute_but_large_relative = pd.DataFrame(
        [{"max_abs_interaction_residual": 0.001, "max_abs_residual_to_noise": 2.0}]
    )
    large_absolute_but_small_relative = pd.DataFrame(
        [{"max_abs_interaction_residual": 1.0, "max_abs_residual_to_noise": 0.5}]
    )

    assert classify_interactions(tiny_absolute_but_large_relative) == "unstable"
    assert classify_interactions(large_absolute_but_small_relative) == "stable"
