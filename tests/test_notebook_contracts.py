import json
from pathlib import Path

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
]


def _source(name: str) -> str:
    notebook = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
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
