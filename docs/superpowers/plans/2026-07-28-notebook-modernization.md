# Notebook Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every operational notebook safe by default, reproducible, and consistent with the 500 m feasible-first pipeline without downloading or recomputing data.

**Architecture:** Notebook JSON remains the user-facing workflow, while shared source modules remain authoritative for grid geometry, target realization, and optimizer behavior. Static notebook-contract tests validate source cells without executing them; pure unit tests validate the 500 m Rohemeeter point generator without network access.

**Tech Stack:** Python 3.12, Jupyter notebook JSON, pytest, NumPy, pandas, GeoPandas, Shapely, Ruff.

## Global Constraints

- Every network-capable notebook defines `ALLOW_DOWNLOADS = False`.
- Existing local files are reused automatically.
- Missing cache plus disabled downloads raises a clear error naming the missing path and the opt-in flag.
- No task may set `ALLOW_DOWNLOADS = True`, invoke Rohemeeter, contact the Forest Registry, or download UNFCCC/Zenodo data.
- Rohemeeter refreshes use the 500 m grid and 200 m-spaced interior sample points.
- Optimizer notebooks use `seed=42`.
- Maps and spatial biodiversity calculations use `realize_targets()`.
- Carbon area comes from shared `CELL_AREA_HA`, which is 25 ha for the current grid.
- Modified notebooks have stale outputs and execution counts cleared.
- Existing files under `data/raw` and `data/processed` must not be modified by implementation or verification.

---

### Task 1: Make the Rohemeeter fetcher geometry-aware and configurable

**Files:**
- Modify: `src/carbon_dataset/09_fetch_rohemeeter.py`
- Create: `tests/carbon_dataset/test_rohemeeter.py`

**Interfaces:**
- Consumes: `GRID_CELL_SIZE = 500` from `estonia_landuse.data.constants`.
- Produces: `RohemeeterPaths`, `build_paths(grid_path, output_dir)`,
  `generate_query_points(grid, water_cells, step, offset)`,
  `run_fetch(paths, delay, batch_size)`, and `export_parquet(paths)`.

- [ ] **Step 1: Write the failing pure point-generation test**

```python
import importlib.util
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box


SCRIPT = Path(__file__).parents[2] / "src/carbon_dataset/09_fetch_rohemeeter.py"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("rohemeeter_fetcher", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_query_points_uses_500m_cell_geometry():
    fetcher = _load_fetcher()
    grid = gpd.GeoDataFrame(
        {"cell_id": [7], "geometry": [box(0, 0, 500, 500)]},
        crs="EPSG:3301",
    )

    points = fetcher.generate_query_points(
        grid,
        water_cells=set(),
        step=200,
        offset=100,
    )

    assert points == [
        ("7_0_0", 7, 100.0, 100.0),
        ("7_0_1", 7, 100.0, 300.0),
        ("7_1_0", 7, 300.0, 100.0),
        ("7_1_1", 7, 300.0, 300.0),
    ]


def test_build_paths_keeps_refresh_outputs_in_selected_directory(tmp_path):
    fetcher = _load_fetcher()
    grid_path = tmp_path / "grid.gpkg"
    output_dir = tmp_path / "refresh"

    paths = fetcher.build_paths(grid_path, output_dir)

    assert paths.grid == grid_path
    assert paths.progress == output_dir / "rohemeeter_progress.json"
    assert paths.raw == output_dir / "rohemeeter_scores_raw.parquet"
    assert paths.aggregate == output_dir / "rohemeeter_scores.parquet"
```

- [ ] **Step 2: Run the test and verify the old hard-coded interface fails**

Run:

```powershell
uv run --extra dev pytest tests/carbon_dataset/test_rohemeeter.py -q
```

Expected: FAIL because `generate_query_points()` does not accept `water_cells`, `step`, or `offset` and assumes five points per side.

- [ ] **Step 3: Implement configurable paths and geometry-derived points**

Replace global operational paths with:

```python
from dataclasses import dataclass
from pathlib import Path

from estonia_landuse.data.constants import GRID_CELL_SIZE


@dataclass(frozen=True)
class RohemeeterPaths:
    grid: Path
    progress: Path
    raw: Path
    aggregate: Path


DEFAULT_OUTPUT_DIR = Path("data/processed/rohemeeter_500m")
DEFAULT_PATHS = RohemeeterPaths(
    grid=Path("data/processed/v1/base_grid.gpkg"),
    progress=DEFAULT_OUTPUT_DIR / "rohemeeter_progress.json",
    raw=DEFAULT_OUTPUT_DIR / "rohemeeter_scores_raw.parquet",
    aggregate=DEFAULT_OUTPUT_DIR / "rohemeeter_scores.parquet",
)


def build_paths(grid_path: Path, output_dir: Path) -> RohemeeterPaths:
    return RohemeeterPaths(
        grid=grid_path,
        progress=output_dir / "rohemeeter_progress.json",
        raw=output_dir / "rohemeeter_scores_raw.parquet",
        aggregate=output_dir / "rohemeeter_scores.parquet",
    )
```

Implement point generation without reading data internally:

```python
def generate_query_points(
    grid,
    *,
    water_cells: set[int],
    step: int = 200,
    offset: int = 100,
):
    points = []
    skipped = 0
    for idx, row in grid.iterrows():
        cell_id = int(row["cell_id"] if "cell_id" in grid.columns else idx)
        if cell_id in water_cells:
            skipped += 1
            continue
        minx, miny, maxx, maxy = row.geometry.bounds
        xs = np.arange(minx + offset, maxx, step)
        ys = np.arange(miny + offset, maxy, step)
        for xi, x in enumerate(xs):
            for yi, y in enumerate(ys):
                points.append(
                    (f"{cell_id}_{xi}_{yi}", cell_id, float(x), float(y))
                )
    print(
        f"Grid cell size: {GRID_CELL_SIZE}m; skipped {skipped} water cells; "
        f"querying {len(points)} points",
        flush=True,
    )
    return points
```

Move water-cell loading to `run_fetch()`. Pass `paths.progress` to
`_save_progress()`, pass `paths` into `run_fetch()` and `export_parquet()`, and
add CLI arguments:

```python
parser.add_argument(
    "--grid-path",
    type=Path,
    default=DEFAULT_PATHS.grid,
)
parser.add_argument(
    "--output-dir",
    type=Path,
    default=DEFAULT_OUTPUT_DIR,
)
```

Call `build_paths(args.grid_path, args.output_dir)` from the CLI. Do not fall
back to the old `carbon_v1_5/grid.gpkg`.

- [ ] **Step 4: Run focused tests and lint**

Run:

```powershell
uv run --extra dev pytest tests/carbon_dataset/test_rohemeeter.py -q
uv run --extra dev ruff check src/carbon_dataset/09_fetch_rohemeeter.py tests/carbon_dataset/test_rohemeeter.py
```

Expected: point-generation test passes; Ruff reports no errors; no browser or
network process starts.

- [ ] **Step 5: Commit**

```powershell
git add src/carbon_dataset/09_fetch_rohemeeter.py tests/carbon_dataset/test_rohemeeter.py
git commit -m "fix: make Rohemeeter refresh 500m aware"
```

### Task 2: Add safe-by-default download guards

**Files:**
- Create: `tests/test_notebook_contracts.py`
- Modify: `notebooks/01_collect_datasets.ipynb`
- Modify: `notebooks/01.2_fetch_rohemeeter.ipynb`
- Modify: `notebooks/04_learned_carbon_predictor.ipynb`
- Modify: `notebooks/06_download_forest_registry.ipynb`
- Modify: `notebooks/07_fetch_forest_details.ipynb`

**Interfaces:**
- Consumes: `RohemeeterPaths` and CLI behavior from Task 1.
- Produces: notebook-level `ALLOW_DOWNLOADS: bool = False` contract.

- [ ] **Step 1: Write the failing download-safety contract test**

```python
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
NOTEBOOKS = ROOT / "notebooks"


def notebook_code(name: str) -> str:
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell["source"])
        for cell in document["cells"]
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
def test_network_notebooks_disable_downloads_by_default(name: str):
    code = notebook_code(name)
    assert "ALLOW_DOWNLOADS = False" in code
    assert "if ALLOW_DOWNLOADS" in code
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_network_notebooks_disable_downloads_by_default -q
```

Expected: five failures because none of the notebooks yet defines the flag.

- [ ] **Step 3: Add the common guard pattern to each notebook**

Add near each notebook's path/config cell:

```python
# Safety default: reuse local data. Change only for a deliberate refresh.
ALLOW_DOWNLOADS = False
```

Wrap every network entry point with the relevant cache check. Use this exact
shape, substituting the notebook's expected path and download call:

```python
if EXPECTED_OUTPUT.exists():
    print(f"Using cached data: {EXPECTED_OUTPUT}")
elif ALLOW_DOWNLOADS:
    download_or_fetch()
else:
    raise FileNotFoundError(
        f"Required cached data is missing: {EXPECTED_OUTPUT}. "
        "Set ALLOW_DOWNLOADS = True to refresh it deliberately."
    )
```

For notebook 01.2, point the optional command at:

```python
SCRIPT = PROJECT_ROOT / "src" / "carbon_dataset" / "09_fetch_rohemeeter.py"
GRID_PATH = PROJECT_ROOT / "data" / "processed" / "v1" / "base_grid.gpkg"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "rohemeeter_500m"

if OUTPUT_AGG.exists():
    print(f"Using cached Rohemeeter data: {OUTPUT_AGG}")
elif ALLOW_DOWNLOADS:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--grid-path",
            str(GRID_PATH),
            "--output-dir",
            str(OUTPUT_DIR),
            "--delay",
            "1.5",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
else:
    raise FileNotFoundError(
        f"Rohemeeter cache is missing: {OUTPUT_AGG}. "
        "Set ALLOW_DOWNLOADS = True for a deliberate refresh."
    )
```

Notebook 04 must guard both live UNFCCC and Zenodo retrieval. Notebooks 06 and
07 must use their existing local GeoPackage/parquet outputs before considering
network calls.

- [ ] **Step 4: Run the focused contract test**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_network_notebooks_disable_downloads_by_default -q
```

Expected: five passes without executing notebook cells.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_notebook_contracts.py notebooks/01_collect_datasets.ipynb notebooks/01.2_fetch_rohemeeter.ipynb notebooks/04_learned_carbon_predictor.ipynb notebooks/06_download_forest_registry.ipynb notebooks/07_fetch_forest_details.ipynb
git commit -m "fix: guard notebook downloads by default"
```

### Task 3: Align notebook target calculations with the simulator

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/02_simulator_and_baselines.ipynb`
- Modify: `notebooks/03.2_neuroevolution_biodiversity.ipynb`

**Interfaces:**
- Consumes: `realize_targets(context, target_fractions, config)` from
  `estonia_landuse.simulator.targets`.
- Produces: visualization and spatial-biodiversity deltas identical to scored
  realized targets.

- [ ] **Step 1: Add failing realized-target contract tests**

```python
@pytest.mark.parametrize(
    "name",
    [
        "02_simulator_and_baselines.ipynb",
        "03.2_neuroevolution_biodiversity.ipynb",
    ],
)
def test_policy_notebooks_use_shared_target_realization(name: str):
    code = notebook_code(name)
    assert "from estonia_landuse.simulator.targets import realize_targets" in code
    assert "realize_targets(" in code
    assert "target_fractions / target_sum * available_land" not in code
    assert "targets / tgt_sum * available" not in code
```

- [ ] **Step 2: Run the tests and verify old normalization is detected**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_policy_notebooks_use_shared_target_realization -q
```

Expected: two failures because both notebooks contain manual available-land
normalization.

- [ ] **Step 3: Replace notebook 02's map normalization**

Add:

```python
from estonia_landuse.simulator.targets import realize_targets
```

Replace the `urban`, `water`, `available`, and `tgt_sum` block with:

```python
targets_norm = realize_targets(gdf, targets, config)
delta = targets_norm - current
```

- [ ] **Step 4: Replace notebook 03.2's spatial-scoring normalization**

Add the same import and replace its manual normalization with:

```python
targets = realize_targets(context, target_fractions, config)
delta = targets - current
```

Remove the notebook-local protected threshold and zeroing block. The realized
targets already enforce the configured protected threshold, and the base
outcomes already zero protected benefits.

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_policy_notebooks_use_shared_target_realization -q
```

Expected: two passes.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_notebook_contracts.py notebooks/02_simulator_and_baselines.ipynb notebooks/03.2_neuroevolution_biodiversity.ipynb
git commit -m "fix: realize notebook policy targets consistently"
```

### Task 4: Make optimizer notebooks deterministic and repair notebook 03.2

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/03_neuroevolution.ipynb`
- Modify: `notebooks/03.1_neuroevolution_carbon.ipynb`
- Modify: `notebooks/03.2_neuroevolution_biodiversity.ipynb`
- Modify: `notebooks/05_compare_carbon_models.ipynb`

**Interfaces:**
- Consumes: `_create_offspring(..., rng)`, `create_seed_prescriptors(..., rng)`,
  `Prescriptor(..., rng)`, and feasible-first `constraint_violation`.
- Produces: deterministic notebook experiments with `seed=42`.

- [ ] **Step 1: Add failing optimizer notebook contract tests**

```python
@pytest.mark.parametrize(
    ("name", "minimum_seed_count"),
    [
        ("03_neuroevolution.ipynb", 1),
        ("03.1_neuroevolution_carbon.ipynb", 1),
        ("03.2_neuroevolution_biodiversity.ipynb", 1),
        ("05_compare_carbon_models.ipynb", 2),
        ("10_scenario_comparison.ipynb", 1),
    ],
)
def test_optimizer_notebooks_use_fixed_seed(name: str, minimum_seed_count: int):
    assert notebook_code(name).count("seed=42") >= minimum_seed_count


def test_biodiversity_trainer_uses_current_feasible_first_interfaces():
    code = notebook_code("03.2_neuroevolution_biodiversity.ipynb")
    assert "p.constraint_violation = summary['constraint_penalty']" in code
    assert "_create_offspring(" in code
    assert "rng=rng" in code
    assert "np.random.default_rng(seed)" in code
```

- [ ] **Step 2: Run tests and verify deterministic/compatibility failures**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_optimizer_notebooks_use_fixed_seed tests/test_notebook_contracts.py::test_biodiversity_trainer_uses_current_feasible_first_interfaces -q
```

Expected: failures for notebooks 03, 03.1, 03.2, and 05; notebook 10 passes.

- [ ] **Step 3: Add seeds to shared-trainer notebooks**

Add `seed=42` to the train calls in notebooks 03 and 03.1. Add `seed=42` to
both train calls in notebook 05 so flat and NIR runs begin from matching
initial populations.

- [ ] **Step 4: Repair notebook 03.2's custom trainer**

Change the signature to:

```python
def train_biodiversity(
    context,
    feature_columns,
    pop_size=100,
    n_generations=100,
    hidden_size=16,
    p_mutation=0.2,
    mutation_factor=0.1,
    config=None,
    use_seeds=True,
    verbose=True,
    seed=None,
):
```

Initialize and thread one generator:

```python
rng = np.random.default_rng(seed)
seeds = create_seed_prescriptors(
    features_norm,
    context,
    hidden_size=hidden_size,
    rng=rng,
)
population = seeds + [
    Prescriptor(in_size, hidden_size, rng=rng) for _ in range(n_random)
]
offspring = _create_offspring(
    population,
    pop_size,
    p_mutation,
    mutation_factor,
    rng=rng,
)
```

In `_evaluate_population_bio()`, add:

```python
p.constraint_violation = summary["constraint_penalty"]
```

Call `train_biodiversity(..., seed=42)`.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_optimizer_notebooks_use_fixed_seed tests/test_notebook_contracts.py::test_biodiversity_trainer_uses_current_feasible_first_interfaces -q
```

Expected: all optimizer notebook contracts pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_notebook_contracts.py notebooks/03_neuroevolution.ipynb notebooks/03.1_neuroevolution_carbon.ipynb notebooks/03.2_neuroevolution_biodiversity.ipynb notebooks/05_compare_carbon_models.ipynb
git commit -m "fix: make notebook evolution reproducible"
```

### Task 5: Correct notebook 04's 500 m carbon calculation

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/04_learned_carbon_predictor.ipynb`

**Interfaces:**
- Consumes: `CELL_AREA_HA` from `estonia_landuse.data.constants` and
  `normalize_targets()` from `estonia_landuse.simulator.targets`.
- Produces: a 25 ha, residual-preserving local NIR comparison.

- [ ] **Step 1: Add a failing carbon notebook contract test**

```python
def test_learned_carbon_notebook_uses_shared_500m_constants():
    code = notebook_code("04_learned_carbon_predictor.ipynb")
    assert "from estonia_landuse.data.constants import CELL_AREA_HA" in code
    assert "from estonia_landuse.simulator.targets import normalize_targets" in code
    assert "CELL_AREA_HA = 100" not in code
    assert "normalize_targets(context_df, target_fractions)" in code
```

- [ ] **Step 2: Run the test and verify the hard-coded area fails**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_learned_carbon_notebook_uses_shared_500m_constants -q
```

Expected: FAIL because notebook 04 defines `CELL_AREA_HA = 100.0` and manually
normalizes to all available land.

- [ ] **Step 3: Use shared area and normalization**

Add:

```python
from estonia_landuse.data.constants import CELL_AREA_HA
from estonia_landuse.simulator.targets import normalize_targets
```

Remove the local `CELL_AREA_HA = 100.0` assignment and replace the `urban`,
`water`, `available`, and `tgt_sum` block with:

```python
targets = normalize_targets(context_df, target_fractions)
```

Update explanatory markdown from “1 km² = 100 ha” to “500 m × 500 m = 25 ha”.

- [ ] **Step 4: Run the focused test**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_learned_carbon_notebook_uses_shared_500m_constants -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_notebook_contracts.py notebooks/04_learned_carbon_predictor.ipynb
git commit -m "fix: use 500m area in carbon notebook"
```

### Task 6: Mark legacy notebooks, clear stale outputs, and verify the suite

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/01.1_carbon_dataset.ipynb`
- Modify: `notebooks/01.3_validate_features_map.ipynb`
- Modify: every notebook changed in Tasks 2–5

**Interfaces:**
- Consumes: notebook list and contracts established in Tasks 2–5.
- Produces: honest source-only notebooks with no stale execution results.

- [ ] **Step 1: Add failing legacy/output contract tests**

```python
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


@pytest.mark.parametrize("name", MODERNIZED_NOTEBOOKS)
def test_modernized_notebooks_have_no_stale_outputs(name: str):
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    for cell in document["cells"]:
        if cell["cell_type"] == "code":
            assert cell.get("outputs", []) == []
            assert cell.get("execution_count") is None


@pytest.mark.parametrize(
    "name",
    ["01.1_carbon_dataset.ipynb", "01.3_validate_features_map.ipynb"],
)
def test_legacy_notebooks_are_labelled(name: str):
    document = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
    markdown = "\n".join(
        "".join(cell["source"])
        for cell in document["cells"]
        if cell["cell_type"] == "markdown"
    )
    assert "Legacy 1 km / V1.5 workflow" in markdown
    assert "Use the 500 m operational pipeline" in markdown


@pytest.mark.parametrize("name", MODERNIZED_NOTEBOOKS)
def test_modernized_notebook_code_cells_compile(name: str):
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
```

- [ ] **Step 2: Run the tests and verify stale outputs/notices fail**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py::test_modernized_notebooks_have_no_stale_outputs tests/test_notebook_contracts.py::test_legacy_notebooks_are_labelled -q
```

Expected: failures because saved outputs remain and the two legacy notices do
not exist.

- [ ] **Step 3: Add legacy notices**

Insert this markdown immediately after the title cell in notebooks 01.1 and
01.3:

```markdown
> **Legacy 1 km / V1.5 workflow**
>
> This notebook is retained as a historical reproducibility reference. Use the
> 500 m operational pipeline (`01_collect_datasets`, `01.4`, and `06`–`10`) for
> current work. Do not use this notebook to overwrite current processed data.
```

- [ ] **Step 4: Clear outputs without executing notebooks**

Run the local notebook preprocessor on exactly `MODERNIZED_NOTEBOOKS`:

```powershell
uv run --extra notebook jupyter nbconvert --to notebook --ClearOutputPreprocessor.enabled=True --inplace notebooks/01.1_carbon_dataset.ipynb notebooks/01.2_fetch_rohemeeter.ipynb notebooks/01.3_validate_features_map.ipynb notebooks/01_collect_datasets.ipynb notebooks/02_simulator_and_baselines.ipynb notebooks/03_neuroevolution.ipynb notebooks/03.1_neuroevolution_carbon.ipynb notebooks/03.2_neuroevolution_biodiversity.ipynb notebooks/04_learned_carbon_predictor.ipynb notebooks/05_compare_carbon_models.ipynb notebooks/06_download_forest_registry.ipynb notebooks/07_fetch_forest_details.ipynb
```

This command clears stored outputs only; it must not include `--execute`.

- [ ] **Step 5: Run notebook contracts**

Run:

```powershell
uv run --extra dev pytest tests/test_notebook_contracts.py -q
```

Expected: all notebook contract tests pass.

- [ ] **Step 6: Run complete verification**

Run:

```powershell
uv run --extra dev ruff check src tests
uv run --extra dev pytest -q
git diff --check
git status --short
```

Expected:

- Ruff reports no errors.
- The complete pytest suite passes.
- `git diff --check` is silent.
- Git status lists only planned source, test, notebook, and documentation files.
- No path under `data/raw` or `data/processed` is listed.

- [ ] **Step 7: Commit**

```powershell
git add tests/test_notebook_contracts.py notebooks/01.1_carbon_dataset.ipynb notebooks/01.2_fetch_rohemeeter.ipynb notebooks/01.3_validate_features_map.ipynb notebooks/01_collect_datasets.ipynb notebooks/02_simulator_and_baselines.ipynb notebooks/03_neuroevolution.ipynb notebooks/03.1_neuroevolution_carbon.ipynb notebooks/03.2_neuroevolution_biodiversity.ipynb notebooks/04_learned_carbon_predictor.ipynb notebooks/05_compare_carbon_models.ipynb notebooks/06_download_forest_registry.ipynb notebooks/07_fetch_forest_details.ipynb
git commit -m "docs: modernize operational notebooks"
```
