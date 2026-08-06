# Estonia Land-Use Neuroevolution

A research prototype for exploring county-scale land-use trade-offs in Estonia. The current demo
scope is Lääne County on a 500 m grid. The project uses feasible-first NSGA-II to evolve small
neural prescriptors, score their continuous land-share targets, and compare representative
policies under six scenarios.

This is a decision-support experiment, not an ecological forecast or an official planning
recommendation. Biodiversity, carbon, and cost outputs are model-derived indicators whose
meaning depends on the prepared inputs and configured assumptions.

At a high level, prepared cell features enter the neural prescriptor; its proposed target shares
are normalized and constrained; the simulator scores realized changes; feasible-first NSGA-II
evolves a Pareto population; scenario rules select representatives; and notebooks save comparable
metrics and spatial outputs.

## How the model represents land-use change

Each grid cell starts with fractions for forest, wetland, agriculture, grassland, urban, and
water. A neural prescriptor emits four continuous target fractions:

- forest;
- wetland;
- agriculture; and
- grassland.

The four outputs are normalized to the cell's currently modelled changeable-land total. Urban
and water remain fixed. The main simulator then realizes physically feasible targets: protected
cells retain their current fractions, existing wetland cannot be lost, and wetland gain is
limited by suitability and capacity. Protection is therefore a constraint, not a land-use
action or a fifth prescriptor output. See the target implementation in
[`src/estonia_landuse/simulator/targets.py`](src/estonia_landuse/simulator/targets.py).

### Continuous targets and map labels are different

Saved scenario maps reduce each cell's continuous realized changes to one of five display
labels:

| Saved value | Reader-facing meaning |
|---|---|
| `no_change` | No substantial change |
| `forest` | Forest increase |
| `wetland` | Wetland increase |
| `agriculture` | Agricultural-land increase |
| `grassland` | Grassland increase |

For cells above the change threshold, the label is the group with the largest positive realized
delta. It is not the policy's only change and is not a mutually exclusive prescriptor decision.
Change intensity is half the sum of the four absolute deltas; cells below `0.05` are labelled
`no_change`. A dominant forest label, for example, can hide a smaller simultaneous wetland gain.

Four changeable groups also imply `4 x 3 = 12` possible directed increase/decrease pairs as an
abstract pre-constraint taxonomy. These pairs are not twelve discrete actions, and the map does
not assign one exclusive source-to-destination transition. Realized targets prohibit wetland
loss and remain subject to protection, suitability, capacity, and land-share constraints, so the
taxonomy is not a claim that all twelve pairs occur in saved results.

## Optimization, feasibility, and scenario selection

The optimizer internally minimizes every objective. The trainer represents the current goals as:

1. maximize biodiversity gain by minimizing its negative;
2. maximize carbon gain by minimizing its negative;
3. minimize cost; and
4. use one scenario-configurable metric: minimize changed land (the default), maximize wetland
   gain, or maximize agriculture gain.

Several related mechanisms have distinct roles:

- **Objectives** define Pareto trade-offs among candidate policies.
- **Target-realization constraints** project proposed targets into allowed land shares, including
  protected-area handling and no wetland loss.
- **Constraint violations** quantify infeasibility. Feasible-first dominance ranks every feasible
  policy ahead of every infeasible one; among infeasible policies, the smaller normalized
  violation wins. Feasibility uses a `1e-12` tolerance, and non-finite violations are treated as
  infinite.
- **Cost penalties** add configured budget and agriculture terms to the cost objective. They are
  not synonymous with physical constraints or feasibility violations.
- **Scenario selection** chooses one representative after optimization. Selection uses feasible
  candidates when available, otherwise the least-violating candidates, then applies the
  scenario's normalized rule with deterministic cost, changed-land, and policy-ID tie-breaks.

The implementations are in
[`optimizer/trainer.py`](src/estonia_landuse/optimizer/trainer.py),
[`optimizer/nsga2.py`](src/estonia_landuse/optimizer/nsga2.py),
[`simulator/simulator.py`](src/estonia_landuse/simulator/simulator.py), and
[`scenarios.py`](src/estonia_landuse/scenarios.py).

## Grid and carbon scoring

The configured grid is 500 m by 500 m (25 hectares per cell); the shared constant in
[`src/estonia_landuse/data/constants.py`](src/estonia_landuse/data/constants.py) keeps cell-area
calculations consistent. Prepared current land-use fractions come from CORINE 2018, while other
features add protected-area, wetland, peat, infrastructure, biodiversity-context, and forest data.
The detailed source-to-feature mapping is maintained in
[`docs/scenario-comparison.md`](docs/scenario-comparison.md#data-provenance-by-simulation-aspect).

The simulator supports four carbon-scoring modes through `carbon_model`:

- `auto` uses the configured V1.5 spatial scores when available and otherwise falls back to flat
  land-group densities;
- `flat` forces the flat density lookup;
- `nir` scores source-to-destination transitions with Estonia NIR factor assumptions; and
- `learned` uses prepared gradient-boosted forest predictions and NIR factors for non-forest
  transitions.

Notebook 10 explicitly uses `learned` for all six scenarios. Carbon modes are alternative model
assumptions, not independent observed measurements.

## The six current scenarios

All six scenarios optimize biodiversity gain, carbon gain, and cost. Their fourth objective,
feasibility limits, and representative-selection rule give each scenario a different policy
interpretation.

| Identifier | Purpose and representative |
|---|---|
| `green_maximum` | Relaxes economic limits to explore stronger environmental gains; selects the feasible policy with the greatest combined normalized biodiversity and carbon gain. |
| `food_security` | Preserves agricultural land; selects the feasible policy with the greatest biodiversity gain. |
| `low_budget` | Favors minimal intervention; selects a biodiversity/carbon/cost compromise closest to the normalized ideal. |
| `wetland_priority` | Prioritizes rewetting, using wetland gain as the fourth objective; selects a biodiversity/carbon/cost/wetland compromise. |
| `sustainable_agriculture` | Expands agricultural area within biodiversity, carbon, relocation, and changed-land safeguards, using agriculture gain as the fourth objective; selects an agriculture/biodiversity/carbon/cost compromise. |
| `balanced` | Provides the default broad trade-off and minimizes changed land as the fourth objective; selects a biodiversity/carbon/cost/changed-land compromise. |

The exact limits, metric definitions, and review checklist live in
[`docs/scenario-comparison.md`](docs/scenario-comparison.md). Notebook 10 saves the selected
policy ID and uses that same representative for its summary, plots, and map output.

## Installation

Python 3.10 or newer and [uv](https://docs.astral.sh/uv/) are recommended.

For notebooks, geospatial processing, and the optional ML interfaces:

```bash
uv sync --extra all
uv run --extra all jupyter lab
```

For the same focused checks used by CI:

```bash
uv sync --extra dev
uv run --extra dev ruff check src tests
uv run --extra dev pytest -q
```

The base install contains NumPy, pandas, and SciPy. Dependency groups are documented in
[`pyproject.toml`](pyproject.toml); Jupyter is in the `notebook` and `all` groups, not the base
environment.

## Notebook routes

The notebook numbers record the project's stages, but they are not one mandatory run-everything
sequence. Choose the route that matches the question.

### 1. Current six-scenario workflow

[`notebooks/10_scenario_comparison.ipynb`](notebooks/10_scenario_comparison.ipynb) is the current
scenario comparison and reporting entry point. It reads local prepared data and does not download
anything. It requires:

- `data/processed/learned_carbon/features_with_forest.parquet`;
- `data/processed/v1/base_grid.gpkg`; and
- a `predicted_tco2_ha_yr` column in the prepared feature parquet.

If those artifacts are current, run Notebook 10 directly. If they need rebuilding, the learned
forest-carbon path is:

1. [`06_download_forest_registry.ipynb`](notebooks/06_download_forest_registry.ipynb) — prepare
   Forest Registry geometries;
2. [`07_fetch_forest_details.ipynb`](notebooks/07_fetch_forest_details.ipynb) — prepare compartment
   attributes;
3. [`08_train_carbon_predictor.ipynb`](notebooks/08_train_carbon_predictor.ipynb) — train the forest
   carbon predictor; and
4. [`09_spatial_join_and_model.ipynb`](notebooks/09_spatial_join_and_model.ipynb) — create the
   area-weighted grid predictions consumed by Notebook 10.

Earlier collection and feature-preparation notebooks under [`notebooks/`](notebooks/) are needed
only when their corresponding local inputs must be created or refreshed. Five network-facing
notebooks default to `ALLOW_DOWNLOADS = False`: `01_collect_datasets`, `01.2_fetch_rohemeeter`,
`04_learned_carbon_predictor`, `06_download_forest_registry`, and
`07_fetch_forest_details`. Change the guard only for an intentional source refresh.

### 2. Optional development and comparison experiments

Notebooks `03`, `03.1`, and `03.2` explore neuroevolution variants; Notebooks `04` and `05`
develop and compare carbon-model routes. They are comparative/development experiments, not
prerequisites to a Notebook 10 run when the prepared Notebook 09 output already exists.

### 3. Historical-model reproduction and sensitivity

This separate route evaluates the preserved historical Notebook 10 model and optimizer within
declared parameter ranges. Run it in order because the seed baseline informs later comparisons:

| Notebook | Role |
|---|---|
| [`10.1_fast_scenario_reproduction.ipynb`](notebooks/10.1_fast_scenario_reproduction.ipynb) | Reproduce all six historical scenarios with the published seed 42. |
| [`11.1_stochastic_baseline.ipynb`](notebooks/11.1_stochastic_baseline.ipynb) | Measure optimizer-seed variation with scenario defaults fixed. |
| [`11.2_one_at_a_time.ipynb`](notebooks/11.2_one_at_a_time.ipynb) | Screen individual parameter effects against seed noise. |
| [`11.3_global_sensitivity.ipynb`](notebooks/11.3_global_sensitivity.ipynb) | Vary sampled parameters simultaneously. |
| [`11.4_parameter_interactions.ipynb`](notebooks/11.4_parameter_interactions.ipynb) | Test selected two-parameter interactions. |
| [`11.5_biodiversity_robustness.ipynb`](notebooks/11.5_biodiversity_robustness.ipynb) | Compare declared dimensionless biodiversity-value assumptions. |

Select a compute profile and worker count before launching Jupyter:

```powershell
$env:SENSITIVITY_PROFILE = "screen"
$env:SENSITIVITY_N_WORKERS = "2"
uv run --extra all jupyter lab
```

`test` uses population 8, 2 generations, hidden size 4, and no seed prescriptors. `screen` uses
80, 60, 16, and seed prescriptors; `full` uses 200, 200, 16, and seed prescriptors. Default random
seeds are `0` for `test` and `42, 73, 101` for `screen` and `full`. Outputs default to
`data/processed/legacy_sensitivity/` and valid completed artifacts are reused. These experiments
measure model and optimizer sensitivity; they do not estimate empirical ecological uncertainty.

### 4. NSGA-II learning notebook

[`notebooks/nsga2.ipynb`](notebooks/nsga2.ipynb) is a self-contained educational exploration of
NSGA-II mechanics. Use it to study the algorithm rather than as part of the numbered land-use
data and scenario pipeline.

## Notebook 10 outputs

Notebook 10 uses the learned carbon model for every scenario and writes to
`data/processed/learned_carbon/`:

| Path | Contents |
|---|---|
| `scenario_summary.parquet` | One selected representative and its metrics per scenario. |
| `scenario_comparison.parquet` | Pareto-front metrics across all scenarios, including the representative marker. |
| `scenario_maps/<scenario>.gpkg` | Per-cell target fractions, deltas, dominant label, and change intensity for each representative. |

Existing files with those names are replaced by a new run, so archive results first when a
before/after comparison is required.

## Visualizing saved results

The repository contains two distinct static viewers. Neither reruns optimization in the browser.

### Leaflet viewer

[`visualizer/index.html`](visualizer/index.html) reads the checked-in
[`visualizer/scenario_summary.json`](visualizer/scenario_summary.json) and
`visualizer/scenario_maps/*.geojson` exports. Its JavaScript styles the saved `action` property;
it does not infer a new action from the other fields. Serve the repository root locally and open
`http://localhost:8000/visualizer/`:

```bash
uv run python -m http.server 8000
```

### Estonian scenario dashboard

[`visualizer/scenario_results/`](visualizer/scenario_results/) is a separate Estonian dashboard
for Notebook 10 results. After Notebook 10 completes, export its existing parquet and GeoPackage
files:

```bash
uv run --extra all python visualizer/scenario_results/export_dashboard_data.py
```

The command creates `visualizer/scenario_results/data/scenario-results.json`; it does not download
data or rerun optimization. With the same local server, open
`http://localhost:8000/visualizer/scenario_results/`.

## Repository map

```text
src/estonia_landuse/
  data/          loading and grid helpers
  optimizer/     neural prescriptors, NSGA-II, seeds, and training
  simulator/     target realization, scoring, constraints, and reporting
  sensitivity/   preserved-model experiment configuration and runners
src/carbon_dataset/  carbon and Forest Registry preparation utilities
notebooks/           operational, experimental, sensitivity, and learning routes
docs/                scenario interpretation plus design and implementation records
tests/               model invariants, constraints, notebook contracts, and viewers
visualizer/          two static saved-result viewers
```

## Interpretation boundaries

- Scenario results compare this model's policies under configured assumptions; they are not
  predictions of observed ecological or economic outcomes.
- The biodiversity objective is a dimensionless proxy derived from land-use change and prepared
  context. It is not species abundance, a field survey, or habitat-connectivity validation.
- Carbon results depend on transition-factor assumptions and prepared Forest Registry predictions;
  they are not an inventory-grade carbon account.
- Cost is a model objective assembled from configured change, budget, and agriculture terms; it
  is not a project quotation or approved budget.
- Agriculture metrics represent land area, not crop yield, soil fertility, farm profit, food
  demand, or calorie production.
- Prepared inputs include CORINE 2018 land cover and other source-specific snapshots that can
  become outdated. Network refreshes are opt-in so results remain reproducible by default.
- The dominant map label compresses four continuous deltas and should always be interpreted with
  change intensity and the underlying per-group deltas.

For detailed data provenance, scenario semantics, and result checks, see
[`docs/scenario-comparison.md`](docs/scenario-comparison.md).
