# Notebook Modernization Design

## Goal

Make the operational notebooks consistent with the 500 m grid, the
feasible-first optimizer, deterministic experiments, and the user's existing
local datasets. Network downloads must remain possible for deliberate future
refreshes but must never occur by default.

## Scope

### Operational notebooks to update

- `01_collect_datasets.ipynb`
- `01.2_fetch_rohemeeter.ipynb`
- `02_simulator_and_baselines.ipynb`
- `03_neuroevolution.ipynb`
- `03.1_neuroevolution_carbon.ipynb`
- `03.2_neuroevolution_biodiversity.ipynb`
- `04_learned_carbon_predictor.ipynb`
- `05_compare_carbon_models.ipynb`
- `06_download_forest_registry.ipynb`
- `07_fetch_forest_details.ipynb`

Notebook `10_scenario_comparison.ipynb` already satisfies the new contract.
Notebooks `01.4`, `08`, and `09` already use the current operational pipeline
and require only verification. Historical V1/V1.5 notebooks `01.1` and `01.3`
will remain reproducibility references and receive a clear legacy notice
rather than a behavioral rewrite.

### Supporting source

`src/carbon_dataset/09_fetch_rohemeeter.py` must be updated because notebook
01.2 delegates its optional refresh to that script. The script must use the
500 m grid and derive query locations from cell geometry instead of assuming a
1 km cell.

## Download Safety Contract

Every notebook capable of network access will define:

```python
ALLOW_DOWNLOADS = False
```

The default path is:

1. Check for the expected local file or completed cache.
2. Load or validate it without network access.
3. If it is missing, stop with a message naming the missing path and explaining
   that `ALLOW_DOWNLOADS = True` is required for a deliberate refresh.

When the user changes the flag to `True`, the existing download workflow is
available. Existing resumable and atomic behavior in the underlying download
modules remains in force.

Notebook execution during this migration must not set this flag to `True`,
invoke Rohemeeter, contact the Forest Registry, or download UNFCCC/Zenodo data.

## 500 m Rohemeeter Refresh

The fetcher will:

- read `data/processed/v1/base_grid.gpkg` by default;
- use the current 500 m cell geometry rather than a hard-coded 1,000 m width;
- generate 200 m-spaced interior sample points from each cell's bounds;
- continue to skip water-dominated cells using `cell_id`;
- store new refresh progress and outputs in a 500 m-specific output location;
- keep atomic progress writes and resume semantics;
- accept explicit path overrides so historical data is not overwritten.

Existing Rohemeeter values already present in
`features_with_forest.parquet` remain the input to downstream notebooks.

## Simulator and Optimizer Consistency

Notebook 02 will use `realize_targets()` for map deltas so visualization and
scoring use the same residual-land, protected-area, wetland-loss, and
wetland-suitability rules.

Notebooks 03 and 03.1 will retain the shared trainer and add `seed=42`.

Notebook 03.2 will preserve its Rohemeeter-informed biodiversity objective but
will align its custom training loop with the current optimizer:

- call `realize_targets()` before calculating its spatial biodiversity delta;
- set `constraint_violation` from each policy summary;
- accept a seed or generator and pass the same generator to seed creation,
  random prescriptors, and offspring creation;
- pass the required `rng` argument to `_create_offspring()`;
- use the simulator's protected threshold rather than a notebook-local
  conflicting default.

Notebook 05 will use the same fixed seed for flat and NIR experiments so their
initial populations are comparable.

## Carbon Area Consistency

Notebook 04 will import `CELL_AREA_HA` from the shared constants module. At the
current 500 m resolution this value is 25 ha. Its local carbon estimator will
use the shared target normalizer so unmodelled residual land is not silently
allocated to the four modeled categories.

## Notebook Output Policy

Changed notebooks will have stale saved outputs cleared. They will not be
fully re-executed as part of this migration because several are expensive or
network-capable. Each notebook's source must be run-ready with downloads
disabled, and inexpensive structural validation will replace full execution.

Current locally generated scenario outputs from notebook 10 are preserved.

## Automated Verification

A notebook-contract test will parse notebook JSON and verify:

- all network-capable operational notebooks default to
  `ALLOW_DOWNLOADS = False`;
- all optimizer notebooks pass an explicit seed;
- operational cells do not manually expand targets to all available land;
- notebook 03.2 supplies RNG and constraint-violation data;
- notebook 04 does not hard-code a 100 ha cell;
- notebook JSON is valid and code cells compile after excluding supported
  notebook-only syntax.

Rohemeeter source tests will verify dynamic query-point generation on synthetic
500 m cells and confirm progress/output paths can be overridden without
touching existing data.

The final verification is:

1. notebook-contract tests pass;
2. Rohemeeter unit tests pass without network access;
3. the complete project test suite passes;
4. Ruff passes for source and tests;
5. `git diff --check` reports no whitespace errors;
6. no processed or raw data file appears in the Git diff.

## Non-Goals

- Re-downloading any dataset.
- Re-running every notebook.
- Rewriting historical analyses solely for stylistic consistency.
- Merging the duplicate 03 and 03.1 notebooks in this change.
- Changing notebook 10's validated scenario results.
