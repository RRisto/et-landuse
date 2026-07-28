import json
from pathlib import Path

import pytest

NOTEBOOKS = Path(__file__).parents[1] / "notebooks"


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
