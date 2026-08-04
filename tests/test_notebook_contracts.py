import json
import warnings
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

NOTEBOOKS = Path(__file__).parents[1] / "notebooks"
MODERNIZED_NOTEBOOKS = [
    "01.1_carbon_dataset.ipynb",
    "01.2_fetch_rohemeeter.ipynb",
    "01.3_validate_features_map.ipynb",
    "01_collect_datasets.ipynb",
    "02_simulator_and_baselines.ipynb",
    "03_neuroevolution.ipynb",
    "03.1_neuroevolution_carbon.ipynb",
    "03.2_neuroevolution_biodiversity.ipynb",
    "04_learned_carbon_predictor.ipynb",
    "05_compare_carbon_models.ipynb",
    "06_download_forest_registry.ipynb",
    "07_fetch_forest_details.ipynb",
    "11.1_stochastic_baseline.ipynb",
    "11.2_one_at_a_time.ipynb",
    "11.3_global_sensitivity.ipynb",
    "11.4_parameter_interactions.ipynb",
]


def _source(name: str) -> str:
    notebook = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )


def _cell_source(name: str, cell_id: str) -> str:
    notebook = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    return next(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("id") == cell_id
    )


@pytest.mark.parametrize(
    "name",
    [
        "01_collect_datasets.ipynb",
        "01.2_fetch_rohemeeter.ipynb",
        "04_learned_carbon_predictor.ipynb",
        "06_download_forest_registry.ipynb",
        "07_fetch_forest_details.ipynb",
    ],
)
def test_network_notebooks_disable_downloads_by_default(name: str) -> None:
    assert "ALLOW_DOWNLOADS = False" in _source(name)


@pytest.mark.parametrize(
    ("name", "guarded_call"),
    [
        ("01_collect_datasets.ipynb", "elif ALLOW_DOWNLOADS:\n    grid_zip"),
        ("01.2_fetch_rohemeeter.ipynb", "if ALLOW_DOWNLOADS:\n    proc"),
        ("04_learned_carbon_predictor.ipynb", "if ALLOW_DOWNLOADS:\n    estonia_all"),
        ("06_download_forest_registry.ipynb", "elif ALLOW_DOWNLOADS:\n    download"),
        ("07_fetch_forest_details.ipynb", "elif ALLOW_DOWNLOADS:\n    details_df"),
    ],
)
def test_network_entry_points_are_guarded(
    name: str, guarded_call: str
) -> None:
    assert guarded_call in _source(name)


def test_rohemeeter_notebook_uses_isolated_500m_paths() -> None:
    source = _source("01.2_fetch_rohemeeter.ipynb")
    assert "data/processed/v1/base_grid.gpkg" in source
    assert "data/processed/rohemeeter_500m" in source
    assert '"--grid-path"' in source
    assert '"--output-dir"' in source


def test_baseline_map_uses_shared_target_realization() -> None:
    source = _source("02_simulator_and_baselines.ipynb")
    assert "from estonia_landuse.simulator.targets import realize_targets" in source
    assert "targets_norm = realize_targets(gdf, targets)" in source
    assert "targets / tgt_sum * available" not in source


def test_biodiversity_scorer_uses_shared_target_realization() -> None:
    source = _source("03.2_neuroevolution_biodiversity.ipynb")
    assert "from estonia_landuse.simulator.targets import realize_targets" in source
    assert "targets = realize_targets(context, target_fractions, config)" in source
    assert "target_fractions / target_sum * available_land" not in source
    assert "biodiversity_gain[is_protected] = 0.0" not in source


@pytest.mark.parametrize(
    ("name", "seed_count"),
    [
        ("03_neuroevolution.ipynb", 1),
        ("03.1_neuroevolution_carbon.ipynb", 1),
        ("03.2_neuroevolution_biodiversity.ipynb", 1),
        ("05_compare_carbon_models.ipynb", 2),
        ("10_scenario_comparison.ipynb", 1),
    ],
)
def test_optimizer_runs_have_explicit_seeds(
    name: str, seed_count: int
) -> None:
    assert _source(name).count("seed=42") == seed_count


def test_biodiversity_trainer_uses_current_optimizer_interfaces() -> None:
    source = _source("03.2_neuroevolution_biodiversity.ipynb")
    assert "rng = np.random.default_rng(seed)" in source
    assert "rng=rng" in source
    assert "p.constraint_violation = summary['constraint_penalty']" in source
    assert "_create_offspring(" in source
    assert "mutation_factor,\n            rng," in source


def test_learned_carbon_notebook_uses_shared_500m_constants() -> None:
    source = _source("04_learned_carbon_predictor.ipynb")
    assert "from estonia_landuse.data.constants import CELL_AREA_HA" in source
    assert "from estonia_landuse.simulator.targets import normalize_targets" in source
    assert "targets = normalize_targets(context_df, target_fractions)" in source
    assert "CELL_AREA_HA = 100.0" not in source
    assert "target_fractions / tgt_sum * available" not in source


@pytest.mark.parametrize("name", MODERNIZED_NOTEBOOKS)
def test_modernized_notebooks_have_no_stale_outputs(name: str) -> None:
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    for cell in document["cells"]:
        if cell["cell_type"] == "code":
            assert cell.get("outputs", []) == []
            assert cell.get("execution_count") is None


@pytest.mark.parametrize(
    "name",
    ["01.1_carbon_dataset.ipynb", "01.3_validate_features_map.ipynb"],
)
def test_legacy_notebooks_are_labelled(name: str) -> None:
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    markdown = "\n".join(
        "".join(cell["source"])
        for cell in document["cells"]
        if cell["cell_type"] == "markdown"
    )
    assert "Legacy 1 km / V1.5 workflow" in markdown
    assert "Use the 500 m operational pipeline" in markdown


@pytest.mark.parametrize("name", MODERNIZED_NOTEBOOKS)
def test_modernized_notebook_code_cells_compile(name: str) -> None:
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    for index, cell in enumerate(document["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        python_source = "\n".join(
            line
            for line in source.splitlines()
            if not line.lstrip().startswith(("%", "!"))
        )
        compile(python_source, f"{name}:cell-{index}", "exec")


def test_spatial_join_predicts_compartments_before_aggregation() -> None:
    source = _source("09_spatial_join_and_model.ipynb")
    prediction = (
        'compartments_with_details["predicted_tco2_ha_yr"] = '
        "predict_tco2(model, compartments_with_details)"
    )
    assert "from carbon_dataset.grid_carbon import aggregate_cell_carbon" in source
    assert (
        "from carbon_dataset.forest_carbon_model import "
        "load_model, predict_tco2"
    ) in source
    assert prediction in source
    assert source.index(prediction) < source.index("overlay = gpd.overlay(")
    assert "carbon_features = aggregate_cell_carbon(overlay)" in source
    assert source.count("cell_features = overlay.groupby") == 1


def test_scenario_notebook_requires_prepared_carbon_predictions() -> None:
    source = _source("10_scenario_comparison.ipynb")
    assert 'if "predicted_tco2_ha_yr" not in features_df.columns:' in source
    assert "Run notebook 09_spatial_join_and_model.ipynb" in source
    assert "raise FileNotFoundError" in source
    assert "load_model()" not in source
    assert "predict_tco2(" not in source
    assert "GBR failed" not in source


def test_scenario_notebook_uses_hard_limits_and_shared_representatives() -> None:
    source = _source("10_scenario_comparison.ipynb")
    assert (
        "from estonia_landuse.scenarios import "
        "build_scenario_summary, select_scenario_representatives"
    ) in source
    assert (
        'config["optimization"]["fourth_objective"] = '
        '"wetland_gain_pct"'
    ) in source
    assert 'config["max_total_agri_gain_pct"] = 0.05' in source
    assert 'config["max_gross_agri_gain_pct"] = 0.15' in source
    assert 'config["scoring"]["agriculture_gain_cost"] = 10.0' in source
    assert 'config["max_total_agri_loss_pct"] = 0.15' in source
    assert 'elif scenario_name == "sustainable_agriculture":' in source
    assert 'config["min_total_agri_gain_pct"] = 0.05' in source
    assert 'config["max_total_agri_gain_pct"] = 0.10' in source
    assert 'config["max_gross_agri_loss_pct"] = 0.02' in source
    assert 'config["min_biodiversity_gain"] = -0.01' in source
    assert 'config["min_carbon_gain"] = -0.01' in source
    assert (
        'config["optimization"]["fourth_objective"] = '
        '"agriculture_gain_pct"'
    ) in source
    assert (
        '"sustainable_agriculture": "Sustainable Agriculture Expansion"'
        in source
    )
    assert '"sustainable_agriculture": "sustainable_agriculture"' in source
    assert "representatives = select_scenario_representatives(" in source
    assert "selected_policies[name]" in source
    assert (
        'map_df["wetland_gain"] = np.clip(delta[:, 1], 0, None)'
        in source
    )
    assert '"Wetland Gain per Scenario Representative"' in source
    assert 'for ax in axes_flat[len(results):]:' in source
    assert 'pdf["biodiversity_gain"].idxmax()' not in source


def test_scenario_pareto_plot_supports_sustainable_agriculture() -> None:
    """The sixth scenario must have styles for every Pareto scatter plot."""
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    scenarios = {
        "green_maximum": "Green Maximum",
        "food_security": "Food Security",
        "low_budget": "Low Budget",
        "wetland_priority": "Wetland Priority",
        "sustainable_agriculture": "Sustainable Agriculture Expansion",
        "balanced": "Balanced",
    }
    frame = pd.DataFrame(
        {
            "carbon_gain": [0.1],
            "biodiversity_gain": [0.1],
            "cost": [0.1],
            "changed_pct": [0.1],
        }
    )
    namespace = {
        "SCENARIOS": scenarios,
        "pareto_dfs": {name: frame for name in scenarios},
        "plt": plt,
    }

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="FigureCanvasAgg is non-interactive",
                category=UserWarning,
            )
            exec(
                _cell_source("10_scenario_comparison.ipynb", "55f27084"),
                namespace,
            )

        assert plt.get_fignums() == []
    finally:
        plt.close("all")


def test_scenario_map_plots_scale_to_all_scenarios_and_close_figures() -> None:
    """Scenario-map figures must not silently omit scenarios or retain memory."""
    for cell_id in ("82bd21fc", "93795ee0", "cfaf92a4-4451-49b0-bea8-2dbdaea14fbd"):
        source = _cell_source("10_scenario_comparison.ipynb", cell_id)

        assert "n_rows = int(np.ceil(len(results) / n_cols))" in source
        assert "if idx >= 6:" not in source
        assert "plt.close(fig)" in source


def test_fast_scenario_reproduction_notebook_contract() -> None:
    """The gate must run the historical model without mutating Notebook 10 outputs."""
    source = _source("10.1_fast_scenario_reproduction.ipynb")

    assert "from estonia_landuse.sensitivity.runner import run_manifest" in source
    assert "from estonia_landuse.sensitivity.reproduction import (" in source
    assert "compare_reference_summary" in source
    assert 'SENSITIVITY_PROFILE", "full"' in source
    assert 'SENSITIVITY_N_WORKERS' in source
    assert 'SENSITIVITY_OUTPUT_ROOT' in source
    assert 'SENSITIVITY_FEATURES_PATH' in source
    assert 'SENSITIVITY_GRID_PATH' in source
    assert 'SENSITIVITY_REFERENCE_SUMMARY_PATH' in source
    assert 'seeds=[42]' in source
    assert "manifest_run_count" in source
    assert "manifest.head(6)" in source
    assert "progress=" in source
    assert "data/processed/legacy_sensitivity" in source
    assert "benchmark_work_root" in source
    assert "work_root=benchmark_work_root" in source
    assert "FULL REPRODUCTION GATE: PENDING" in source
    assert "10_scenario_comparison.ipynb" not in source
    assert "nbconvert" not in source
    assert "data/processed/learned_carbon/scenario_summary.parquet" not in source


SENSITIVITY_NOTEBOOKS = (
    "11.1_stochastic_baseline.ipynb",
    "11.2_one_at_a_time.ipynb",
    "11.3_global_sensitivity.ipynb",
    "11.4_parameter_interactions.ipynb",
)


@pytest.mark.parametrize("name", SENSITIVITY_NOTEBOOKS)
def test_historical_sensitivity_notebooks_share_execution_contract(name: str) -> None:
    """Catch analysis notebooks bypassing the resumable historical runner."""
    source = _source(name)

    assert "from estonia_landuse.sensitivity.runner import run_manifest" in source
    assert "PROFILE = os.environ.get(\"SENSITIVITY_PROFILE\", \"test\")" in source
    assert "SENSITIVITY_N_WORKERS" in source
    assert "SENSITIVITY_OVERWRITE" in source
    assert "SENSITIVITY_OUTPUT_ROOT" in source
    assert "SENSITIVITY_FEATURES_PATH" in source
    assert "HISTORICAL_ROOT" in source
    assert 'PROJECT_ROOT.parent.name == ".worktrees"' in source
    assert 'HISTORICAL_ROOT / "data/processed/learned_carbon/features_with_forest.parquet"' in source
    assert "DEFAULT_SEEDS[PROFILE]" in source
    assert "manifest_run_count(manifest)" in source
    assert "manifest.head(" in source
    assert "run_manifest(" in source
    assert "progress=" in source
    assert "data/processed/legacy_sensitivity" in source
    assert "data/processed/sensitivity" not in source
    assert "10_scenario_comparison.ipynb" not in source


@pytest.mark.parametrize(
    "name", ["11.2_one_at_a_time.ipynb", "11.4_parameter_interactions.ipynb"]
)
def test_noise_comparisons_select_the_current_baseline_cohort(name: str) -> None:
    """Catch recursive baseline discovery silently mixing profiles or stale code/data."""
    source = _source(name)

    assert "select_matched_baseline_runs" in source
    assert "expected_scenarios=SCENARIOS" in source
    assert "expected_seeds=SEEDS" in source


def test_interaction_notebook_reports_residual_magnitude_relative_to_noise() -> None:
    """Catch Notebook 11.4 displaying residual surfaces without a magnitude table."""
    source = _source("11.4_parameter_interactions.ipynb")

    assert "summarize_interaction_noise" in source
    assert "max_abs_residual_to_noise" in source
    assert "rms_residual_to_noise" in source


def test_full_sensitivity_seed_configuration_includes_reproduction_seed() -> None:
    """Catch full analysis notebooks losing the historical reproduction seed."""
    from estonia_landuse.sensitivity.config import DEFAULT_SEEDS

    assert 42 in DEFAULT_SEEDS["full"]
