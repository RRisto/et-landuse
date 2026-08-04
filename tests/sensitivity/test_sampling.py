"""Contracts for staged, reproducible historical sensitivity designs."""

import pandas as pd
import pytest

from estonia_landuse.sensitivity.config import ExperimentProfile, resolve_profile
from estonia_landuse.sensitivity.sampling import (
    build_baseline_manifest,
    build_biodiversity_manifest,
    build_global_manifest,
    build_interaction_manifest,
    build_oat_manifest,
    manifest_run_count,
    manifest_summary,
)


def _assert_unique_execution_keys(manifest: pd.DataFrame) -> None:
    key_columns = ["experiment", "sample_id", "scenario", "seed"]
    assert not manifest.duplicated(key_columns).any()


def test_profiles_define_exact_staged_optimizer_budgets() -> None:
    """Catch a reduced profile accidentally being used as the full experiment."""
    assert resolve_profile("test") == ExperimentProfile(8, 2, 4, False)
    assert resolve_profile("screen") == ExperimentProfile(80, 60, 16, True)
    assert resolve_profile("full") == ExperimentProfile(200, 200, 16, True)


def test_unknown_profile_is_rejected() -> None:
    """Catch a typo silently selecting an unintended compute budget."""
    with pytest.raises(ValueError, match="Unknown experiment profile: typo"):
        resolve_profile("typo")


def test_baseline_manifest_has_unique_execution_keys() -> None:
    """Catch baseline rows that would overwrite one another's artifacts."""
    manifest = build_baseline_manifest(
        profile="screen", scenarios=("balanced", "low_budget"), seeds=(42, 73)
    )

    _assert_unique_execution_keys(manifest)
    assert set(manifest["seed"]) == {42, 73}
    assert set(manifest["profile"]) == {"screen"}


def test_oat_rows_change_exactly_one_historical_dotted_path() -> None:
    """Catch an OAT design that changes a confounding second parameter."""
    manifest = build_oat_manifest(
        profile="screen", scenarios=("balanced",), seeds=(42,)
    )

    _assert_unique_execution_keys(manifest)
    assert 42 in set(manifest["seed"])
    assert manifest["overrides"].map(len).eq(1).all()
    assert manifest.apply(
        lambda row: row["overrides"] == {row["parameter"]: row["value"]}, axis="columns"
    ).all()


def test_screen_oat_design_is_a_strict_subset_of_full() -> None:
    """Catch a screen value outside the prespecified full confirmation design."""
    screen = build_oat_manifest(profile="screen", scenarios=("balanced",), seeds=(42,))
    full = build_oat_manifest(profile="full", scenarios=("balanced",), seeds=(42,))

    screen_values = set(zip(screen["parameter"], screen["value"], strict=True))
    full_values = set(zip(full["parameter"], full["value"], strict=True))
    assert screen_values < full_values


def test_global_design_is_reproducible_for_its_sampler_seed() -> None:
    """Catch an unseeded Latin-hypercube sampler producing irreproducible runs."""
    first = build_global_manifest(
        profile="screen", n_samples=4, sampler_seed=17, scenarios=("balanced",), seeds=(42,)
    )
    second = build_global_manifest(
        profile="screen", n_samples=4, sampler_seed=17, scenarios=("balanced",), seeds=(42,)
    )

    _assert_unique_execution_keys(first)
    assert 42 in set(first["seed"])
    pd.testing.assert_frame_equal(first, second)


def test_interaction_rows_change_exactly_two_paths() -> None:
    """Catch an interaction design that omits one factor or adds a confounder."""
    manifest = build_interaction_manifest(
        profile="screen",
        pair=("scoring.base_change_cost", "max_changed_pct"),
        levels=3,
        scenarios=("balanced",),
        seeds=(42,),
    )

    _assert_unique_execution_keys(manifest)
    assert 42 in set(manifest["seed"])
    assert manifest["overrides"].map(len).eq(2).all()


def test_biodiversity_design_includes_reproduction_seed() -> None:
    """Catch a reproduction-capable biodiversity design without seed 42."""
    manifest = build_biodiversity_manifest(
        profile="screen", scenarios=("balanced",), seeds=(42,)
    )

    _assert_unique_execution_keys(manifest)
    assert 42 in set(manifest["seed"])


def test_screen_biodiversity_design_is_a_strict_subset_of_full() -> None:
    """Catch a screen-only assumption that cannot be confirmed in the full design."""
    screen = build_biodiversity_manifest(
        profile="screen", scenarios=("balanced",), seeds=(42,)
    )
    full = build_biodiversity_manifest(profile="full", scenarios=("balanced",), seeds=(42,))

    assert set(screen["biodiversity_assumption"]) < set(full["biodiversity_assumption"])


def test_manifest_run_count_and_summary_report_optimizer_total(capsys: pytest.CaptureFixture[str]) -> None:
    """Catch a preflight total that differs from the rows the runner will execute."""
    manifest = build_baseline_manifest(
        profile="screen", scenarios=("balanced",), seeds=(42, 73)
    )

    assert manifest_run_count(manifest) == 2
    assert manifest_summary(manifest) == "baseline: 2 optimizer runs (profile=screen)"
    assert "2 optimizer runs" in capsys.readouterr().out


def test_manifest_run_count_rejects_duplicate_execution_keys() -> None:
    """Catch a manifest that would execute and record one run identity twice."""
    manifest = build_baseline_manifest(
        profile="screen", scenarios=("balanced",), seeds=(42,)
    )
    duplicate = pd.concat([manifest, manifest], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate execution keys"):
        manifest_run_count(duplicate)
