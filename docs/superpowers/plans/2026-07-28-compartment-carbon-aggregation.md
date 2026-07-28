# Compartment-First Carbon Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the existing Forest Registry GBR to individual compartments, aggregate predictions by intersection area into 500 m cells, and make Notebook 10 consume only those prepared predictions.

**Architecture:** A pure pandas helper will own the area-weighted aggregation contract. Notebook 09 will predict on original compartment rows, retain predictions through the spatial overlay, merge aggregated carbon values with its existing cell features, and save them. Notebook 10 will fail early if Notebook 09 has not prepared the required column instead of silently using a fallback.

**Tech Stack:** Python 3.12, pandas, NumPy, GeoPandas, scikit-learn/joblib, pytest, Ruff, Jupyter nbconvert.

## Global Constraints

- Use only existing local data; do not download Forest Registry, Rohemeeter, or other remote data.
- Reuse the existing `forest_carbon_gbr.joblib`; do not retrain it in this trial.
- Preserve the user's executed `notebooks/10_scenario_comparison.ipynb` outputs in the working tree.
- Do not rerun Notebook 10's two-hour scenario experiment.
- Do not change scenario constraints, objectives, or representative-policy selection.
- Write a failing test before each production behavior change.

---

## File Structure

- Create `src/carbon_dataset/grid_carbon.py`: pure cell-level carbon aggregation from predicted overlay pieces.
- Create `tests/carbon_dataset/test_grid_carbon.py`: numerical and invalid-input contracts for the helper.
- Modify `notebooks/09_spatial_join_and_model.ipynb`: compartment prediction, overlay retention, aggregation, and saved columns.
- Modify `notebooks/10_scenario_comparison.ipynb`: require the prepared cell prediction and remove the incompatible inference fallback.
- Modify `tests/test_notebook_contracts.py`: source-level contracts for Notebooks 09 and 10 and syntax compilation.

### Task 1: Pure Area-Weighted Carbon Aggregation

**Files:**
- Create: `src/carbon_dataset/grid_carbon.py`
- Create: `tests/carbon_dataset/test_grid_carbon.py`

**Interfaces:**
- Consumes: a `pandas.DataFrame` with `cell_id`, `predicted_tco2_ha_yr`, and `intersect_area_ha`.
- Produces: `aggregate_cell_carbon(overlay: pd.DataFrame) -> pd.DataFrame` with `cell_id`, `predicted_forest_area_ha`, `predicted_tco2_ha_yr`, and `predicted_tco2_yr`.

- [ ] **Step 1: Write the failing numerical aggregation test**

Create `tests/carbon_dataset/test_grid_carbon.py`:

```python
import numpy as np
import pandas as pd
import pytest

from carbon_dataset.grid_carbon import aggregate_cell_carbon


def test_aggregate_cell_carbon_uses_intersection_area_weights() -> None:
    overlay = pd.DataFrame(
        {
            "cell_id": [1, 1, 2],
            "predicted_tco2_ha_yr": [6.0, 3.0, 6.0],
            "intersect_area_ha": [10.0, 5.0, 2.0],
        }
    )

    result = aggregate_cell_carbon(overlay).set_index("cell_id")

    assert result.loc[1, "predicted_forest_area_ha"] == pytest.approx(15.0)
    assert result.loc[1, "predicted_tco2_yr"] == pytest.approx(75.0)
    assert result.loc[1, "predicted_tco2_ha_yr"] == pytest.approx(5.0)
    assert result.loc[2, "predicted_forest_area_ha"] == pytest.approx(2.0)
    assert result.loc[2, "predicted_tco2_yr"] == pytest.approx(12.0)
    assert result.loc[2, "predicted_tco2_ha_yr"] == pytest.approx(6.0)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/carbon_dataset/test_grid_carbon.py::test_aggregate_cell_carbon_uses_intersection_area_weights -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'carbon_dataset.grid_carbon'`.

- [ ] **Step 3: Implement the minimal aggregation helper**

Create `src/carbon_dataset/grid_carbon.py`:

```python
"""Aggregate compartment carbon predictions into operational grid cells."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "cell_id",
    "predicted_tco2_ha_yr",
    "intersect_area_ha",
}


def aggregate_cell_carbon(overlay: pd.DataFrame) -> pd.DataFrame:
    """Area-weight valid compartment predictions into one row per grid cell."""
    missing = sorted(REQUIRED_COLUMNS.difference(overlay.columns))
    if missing:
        raise ValueError(f"overlay is missing required columns: {', '.join(missing)}")

    cell_ids = pd.Index(pd.unique(overlay["cell_id"]), name="cell_id")
    prediction = pd.to_numeric(
        overlay["predicted_tco2_ha_yr"], errors="coerce"
    )
    area = pd.to_numeric(overlay["intersect_area_ha"], errors="coerce")
    valid = (
        np.isfinite(prediction.to_numpy(float))
        & np.isfinite(area.to_numpy(float))
        & (area.to_numpy(float) > 0)
    )

    contributions = pd.DataFrame(
        {
            "cell_id": overlay.loc[valid, "cell_id"],
            "predicted_forest_area_ha": area.loc[valid],
            "predicted_tco2_yr": (
                prediction.loc[valid] * area.loc[valid]
            ),
        }
    )
    grouped = contributions.groupby("cell_id", sort=False).sum()
    grouped = grouped.reindex(cell_ids, fill_value=0.0)
    grouped["predicted_tco2_ha_yr"] = np.divide(
        grouped["predicted_tco2_yr"],
        grouped["predicted_forest_area_ha"],
        out=np.full(len(grouped), np.nan),
        where=grouped["predicted_forest_area_ha"].to_numpy() > 0,
    )
    return grouped.reset_index()[
        [
            "cell_id",
            "predicted_forest_area_ha",
            "predicted_tco2_ha_yr",
            "predicted_tco2_yr",
        ]
    ]
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/carbon_dataset/test_grid_carbon.py::test_aggregate_cell_carbon_uses_intersection_area_weights -q
```

Expected: `1 passed`.

- [ ] **Step 5: Add invalid-row and missing-column tests**

Append:

```python
def test_aggregate_cell_carbon_excludes_invalid_rows() -> None:
    overlay = pd.DataFrame(
        {
            "cell_id": [1, 1, 2, 2],
            "predicted_tco2_ha_yr": [4.0, np.nan, np.nan, 9.0],
            "intersect_area_ha": [3.0, 7.0, 4.0, 0.0],
        }
    )

    result = aggregate_cell_carbon(overlay).set_index("cell_id")

    assert result.loc[1, "predicted_forest_area_ha"] == pytest.approx(3.0)
    assert result.loc[1, "predicted_tco2_yr"] == pytest.approx(12.0)
    assert result.loc[1, "predicted_tco2_ha_yr"] == pytest.approx(4.0)
    assert result.loc[2, "predicted_forest_area_ha"] == pytest.approx(0.0)
    assert result.loc[2, "predicted_tco2_yr"] == pytest.approx(0.0)
    assert np.isnan(result.loc[2, "predicted_tco2_ha_yr"])


def test_aggregate_cell_carbon_rejects_missing_columns() -> None:
    with pytest.raises(
        ValueError,
        match="overlay is missing required columns: intersect_area_ha",
    ):
        aggregate_cell_carbon(
            pd.DataFrame(
                {
                    "cell_id": [1],
                    "predicted_tco2_ha_yr": [4.0],
                }
            )
        )
```

- [ ] **Step 6: Run helper tests and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/carbon_dataset/test_grid_carbon.py -q
.\.venv\Scripts\python.exe -m ruff check src/carbon_dataset/grid_carbon.py tests/carbon_dataset/test_grid_carbon.py
```

Expected: `3 passed` and `All checks passed!`.

- [ ] **Step 7: Commit Task 1**

```powershell
git add src/carbon_dataset/grid_carbon.py tests/carbon_dataset/test_grid_carbon.py
git commit -m "feat: aggregate compartment carbon by grid cell"
```

### Task 2: Notebook 09 Compartment Prediction Pipeline

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/09_spatial_join_and_model.ipynb`

**Interfaces:**
- Consumes: `predict_tco2(model, compartments_with_details) -> np.ndarray` and `aggregate_cell_carbon(overlay) -> pd.DataFrame`.
- Produces: `grid_forest_features.parquet` and `features_with_forest.parquet` containing `predicted_tco2_ha_yr` and `predicted_tco2_yr`.

- [ ] **Step 1: Add a failing Notebook 09 source contract**

Add:

```python
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
```

- [ ] **Step 2: Run the contract and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py::test_spatial_join_predicts_compartments_before_aggregation -q
```

Expected: failure because Notebook 09 does not import or call the shared helper.

- [ ] **Step 3: Wire prediction into Notebook 09 before overlay**

In the import cell, add:

```python
from carbon_dataset.forest_carbon_model import load_model, predict_tco2
from carbon_dataset.grid_carbon import aggregate_cell_carbon
```

After `compartments_with_details` is created, add:

```python
model = load_model()
compartments_with_details["predicted_tco2_ha_yr"] = predict_tco2(
    model, compartments_with_details
)
print(
    "Compartment carbon predictions: "
    f"{compartments_with_details['predicted_tco2_ha_yr'].describe()}"
)
```

Add `"predicted_tco2_ha_yr"` to the compartment columns passed into
`gpd.overlay`.

- [ ] **Step 4: Aggregate predictions and remove the duplicate feature block**

Keep one existing `cell_features = overlay.groupby(...).apply(...).reset_index()`
block. Immediately after it, add:

```python
carbon_features = aggregate_cell_carbon(overlay)
cell_features = cell_features.merge(
    carbon_features,
    on="cell_id",
    how="left",
    validate="one_to_one",
)
```

Remove the second duplicate `cell_features = overlay.groupby(...)` block.

- [ ] **Step 5: Define non-forest output behavior**

After the forest features are merged onto all V1 cells, add:

```python
merged["predicted_forest_area_ha"] = merged[
    "predicted_forest_area_ha"
].fillna(0.0)
merged["predicted_tco2_yr"] = merged["predicted_tco2_yr"].fillna(0.0)
```

Do not fill `predicted_tco2_ha_yr`: `NaN` must continue to mean that a cell has
no valid compartment prediction.

- [ ] **Step 6: Run Notebook 09 contract, compile its code cells, and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py::test_spatial_join_predicts_compartments_before_aggregation -q
.\.venv\Scripts\python.exe -c "import json,pathlib; n='09_spatial_join_and_model.ipynb'; nb=json.loads((pathlib.Path('notebooks')/n).read_text(encoding='utf-8')); [compile(''.join(c.get('source',[])),f'{n}:cell{i}','exec') for i,c in enumerate(nb['cells']) if c['cell_type']=='code']; print('Notebook 09 code cells compile')"
.\.venv\Scripts\python.exe -m ruff check tests/test_notebook_contracts.py
```

Expected: contract passes, all code cells compile, and Ruff passes.

- [ ] **Step 7: Commit Task 2**

```powershell
git add notebooks/09_spatial_join_and_model.ipynb tests/test_notebook_contracts.py
git commit -m "feat: predict compartment carbon before grid aggregation"
```

### Task 3: Notebook 10 Prepared-Prediction Contract

**Files:**
- Modify: `tests/test_notebook_contracts.py`
- Modify: `notebooks/10_scenario_comparison.ipynb`

**Interfaces:**
- Consumes: `features_with_forest.parquet` with `predicted_tco2_ha_yr`.
- Produces: an early, explicit `FileNotFoundError` when Notebook 09 has not prepared the required column.

- [ ] **Step 1: Add a failing Notebook 10 provenance contract**

Add:

```python
def test_scenario_notebook_requires_prepared_carbon_predictions() -> None:
    source = _source("10_scenario_comparison.ipynb")
    assert 'if "predicted_tco2_ha_yr" not in features_df.columns:' in source
    assert "Run notebook 09_spatial_join_and_model.ipynb" in source
    assert "raise FileNotFoundError" in source
    assert "load_model()" not in source
    assert "predict_tco2(" not in source
    assert "GBR failed" not in source
```

- [ ] **Step 2: Run the contract and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py::test_scenario_notebook_requires_prepared_carbon_predictions -q
```

Expected: failure because Notebook 10 still loads the compartment model and
silently falls back.

- [ ] **Step 3: Replace Notebook 10's inference/fallback block**

Replace the block beginning with:

```python
if "predicted_tco2_ha_yr" not in features_df.columns:
```

with:

```python
if "predicted_tco2_ha_yr" not in features_df.columns:
    raise FileNotFoundError(
        "Missing prepared predicted_tco2_ha_yr. "
        "Run notebook 09_spatial_join_and_model.ipynb first."
    )

valid_carbon = features_df["predicted_tco2_ha_yr"].dropna()
print(
    "Prepared cell carbon predictions: "
    f"{len(valid_carbon):,}/{len(features_df):,} cells, "
    f"mean={valid_carbon.mean():.2f} tCO2/ha/yr"
)
```

- [ ] **Step 4: Run notebook contracts and compile Notebook 10**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py -q
.\.venv\Scripts\python.exe -c "import json,pathlib; n='10_scenario_comparison.ipynb'; nb=json.loads((pathlib.Path('notebooks')/n).read_text(encoding='utf-8')); [compile(''.join(c.get('source',[])),f'{n}:cell{i}','exec') for i,c in enumerate(nb['cells']) if c['cell_type']=='code']; print('Notebook 10 code cells compile')"
.\.venv\Scripts\python.exe -m ruff check tests/test_notebook_contracts.py
```

Expected: all notebook contracts pass, Notebook 10 code cells compile, and
Ruff passes.

- [ ] **Step 5: Stage a source-only Notebook 10 while preserving working outputs**

Create a temporary clean copy from the current working notebook, clear only
that copy's outputs, and stage its blob directly:

```powershell
$cleanNotebook = Join-Path $env:TEMP "et-landuse-notebook10-clean.ipynb"
Copy-Item -LiteralPath notebooks/10_scenario_comparison.ipynb -Destination $cleanNotebook -Force
uv run --extra notebook jupyter nbconvert --to notebook --ClearOutputPreprocessor.enabled=True --inplace $cleanNotebook
$blob = git hash-object -w $cleanNotebook
git update-index --add --cacheinfo "100644,$blob,notebooks/10_scenario_comparison.ipynb"
git add tests/test_notebook_contracts.py
git diff --cached --check
```

Verify the working notebook still has execution outputs:

```powershell
$nb = Get-Content -Raw notebooks/10_scenario_comparison.ipynb | ConvertFrom-Json
($nb.cells | Where-Object { $_.outputs.Count -gt 0 }).Count
```

Expected: a positive output-cell count. The user's results remain in the
working tree but are absent from the staged source-only notebook.

- [ ] **Step 6: Commit Task 3 and confirm results remain uncommitted**

```powershell
git commit -m "fix: require prepared cell carbon predictions"
git status --short
```

Expected: the commit succeeds and status still lists
`M notebooks/10_scenario_comparison.ipynb` because its execution outputs remain
uncommitted.

### Task 4: Full Verification and Local-Data Trial

**Files:**
- Read: `data/raw/forest_registry/laane_eraldised.gpkg`
- Read: `data/raw/forest_registry/laane_details.parquet`
- Read: `data/processed/v1/base_grid.gpkg`
- Generate: `data/processed/learned_carbon/grid_forest_features.parquet`
- Generate: `data/processed/learned_carbon/features_with_forest.parquet`
- Generate outside repository: executed Notebook 09 copy under the system temporary directory.

**Interfaces:**
- Consumes: implemented Notebook 09 and existing local data/model.
- Produces: prediction-distribution evidence for deciding whether Notebook 10 should be rerun.

- [ ] **Step 1: Run full source verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Expected: Ruff passes, the full pytest suite passes, and `git diff --check` is
silent.

- [ ] **Step 2: Execute Notebook 09 to a temporary output notebook**

Run from the repository worktree so the input notebook retains its normal
`notebooks` working directory:

```powershell
$trialDir = Join-Path $env:TEMP "et-landuse-carbon-trial"
New-Item -ItemType Directory -Path $trialDir -Force | Out-Null
uv run --extra notebook jupyter nbconvert --to notebook --execute notebooks/09_spatial_join_and_model.ipynb --output "09_spatial_join_and_model.executed.ipynb" --output-dir $trialDir --ExecutePreprocessor.timeout=1800
```

Expected: Notebook 09 completes using existing local files. The tracked input
notebook is not rewritten.

- [ ] **Step 3: Verify generated schemas and quantify predictions**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import pandas as pd, pathlib; root=pathlib.Path('data/processed/learned_carbon'); grid=pd.read_parquet(root/'grid_forest_features.parquet'); full=pd.read_parquet(root/'features_with_forest.parquet'); required={'predicted_tco2_ha_yr','predicted_tco2_yr','predicted_forest_area_ha'}; assert required <= set(grid.columns); assert required <= set(full.columns); valid=full['predicted_tco2_ha_yr'].dropna(); fallback=full.loc[full['mean_increment'].notna(),'mean_increment']*0.42*0.5*(44/12)*1.3; print({'cells':len(full),'valid_predictions':len(valid),'missing_predictions':int(full['predicted_tco2_ha_yr'].isna().sum()),'min':float(valid.min()),'median':float(valid.median()),'mean':float(valid.mean()),'max':float(valid.max()),'total_tco2_yr':float(full['predicted_tco2_yr'].sum()),'fallback_mean':float(fallback.mean()),'fallback_median':float(fallback.median())})"
```

Expected: required columns exist, at least one valid prediction is present, and
the command prints the model-versus-fallback distribution.

- [ ] **Step 4: Check hard safety conditions and repository status**

Run:

```powershell
git status --short
git status --short -- data/raw
```

Expected:

- Notebook 10 remains modified only by preserved execution outputs.
- No raw-data file is modified.
- Generated processed data may be untracked or ignored and must not be staged.

- [ ] **Step 5: Report trial results without rerunning Notebook 10**

Report:

- successful or failed Notebook 09 execution;
- count and coverage of valid cell predictions;
- prediction distribution;
- total annual predicted forest carbon;
- comparison with the former fallback;
- any model/schema warnings;
- whether the evidence supports rerunning Notebook 10.

Do not commit generated parquet files or the temporary executed notebook.
