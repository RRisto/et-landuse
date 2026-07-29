# Notebook 10 Scenario Comparison

Notebook `10_scenario_comparison.ipynb` runs six policy scenarios with
feasible-first NSGA-II, selects one representative policy per scenario, and
saves comparable metrics and spatial maps.

## Prerequisites

Notebook 10 reads existing local files and does not download data. It requires:

- `data/processed/learned_carbon/features_with_forest.parquet`
- `data/processed/v1/base_grid.gpkg`
- a `predicted_tco2_ha_yr` column in the prepared feature parquet

Notebook 09 creates the prepared carbon column by:

1. loading the trained forest-carbon model;
2. predicting carbon for each Forest Registry compartment;
3. intersecting compartments with the 500 m grid;
4. area-weighting compartment predictions within each grid cell; and
5. saving the merged feature table.

Run Notebook 09 again only when the trained model, compartment details, grid,
or other upstream features have changed. If the prepared parquet already
contains the current predictions, Notebook 10 can run directly.

## Data provenance by simulation aspect

Notebook 10 uses the prepared per-cell feature table rather than contacting
external services. The following sources created those inputs upstream.

| Simulation aspect | Prepared fields or inputs | Upstream source | Role in the simulation |
|---|---|---|---|
| Grid and population | `cell_id`, `TOTAL_24` | Statistics Estonia 1 km population grid, subdivided to the project's 500 m grid | Defines analysis cells; population contributes to opportunity cost and wetland-restoration restrictions. |
| Current land use | `forest_pct`, `wetland_pct`, `agriculture_pct`, `grassland_pct`, `urban_pct`, `water_pct` | CORINE Land Cover 2018 | Starting land shares; urban and water shares are fixed. |
| Protected areas | `protected_overlap_pct` | EELIS WFS | Blocks change in heavily protected cells and adds a biodiversity bonus only to forest, wetland, and grassland gains in partly overlapping cells. |
| Roads and buildings | `road_density_km`, `building_count` | OpenStreetMap, distributed through Geofabrik | Helps derive wetland suitability and opportunity cost. |
| Peat and wetland context | `peat_overlap_pct` and wetland-restoration inputs | Maa-amet maardlad WFS and associated Estonian peat/wetland layers | Selects peat-sensitive non-forest carbon factors and supports restoration suitability. |
| Forest carbon | `predicted_tco2_ha_yr` | Estonian Forest Registry (metsaregister) compartment geometries and attributes, processed by Notebook 09's learned predictor | Cell-specific forest carbon rate. Missing values use the documented 3.8 tCO2/ha/yr fallback. |
| Non-forest carbon | Land-use transitions plus peat overlap | Estonia NIR 2024 and IPCC transition-factor tables | Estimates wetland, agriculture, and grassland transition effects; these are emission-factor assumptions, not a second observed dataset. |
| Prescriptor context | `naturalness_score`, `carbon_score`, `biodiversity_proxy`, `opportunity_cost_proxy`, `rohemeeter_norm` | Derived from the sources above; `rohemeeter_norm` comes from Rohemeeter biodiversity scores | Inputs used by the neural prescriptor to choose target land shares. |

Rohemeeter is decision context rather than a direct biodiversity-outcome
measurement. The biodiversity objective is calculated from land-use change,
wetland suitability, a protected-area overlap proxy, and configured land-group
values. The overlap proxy rewards forest, wetland, and grassland gains, not
agricultural expansion; it is not a graph-based habitat-corridor analysis.
Likewise, agriculture metrics describe agricultural land area only:
the model has no crop yield, soil fertility, farm-profit, food-demand, or
calorie-production data.

Remote-data notebooks use `ALLOW_DOWNLOADS = False` by default. Leave this
flag unchanged to reuse local Forest Registry, Rohemeeter, and other prepared
data. Set it to `True` only when intentionally refreshing a source.

## Scenario semantics

The percentages below are hard feasibility limits. A policy outside a
configured limit receives positive `constraint_penalty`; feasible-first
NSGA-II ranks every feasible policy ahead of every infeasible policy.

| Scenario | Maximum changed land | Maximum agriculture loss | Maximum agriculture gain (net/gross) | Fourth objective |
|----------|---------------------:|-------------------------:|-------------------------:|------------------|
| Green Maximum | 40% | 50% | No scenario cap | Minimize changed land |
| Food Security | 15% | 3% | No scenario cap | Minimize changed land |
| Low Budget | 6% | 15% | No scenario cap | Minimize changed land |
| Wetland Priority | 25% | 15% | 5% / 15% | Maximize wetland gain |
| Sustainable Agriculture Expansion | 15% | 2% gross | 5–10% net | Maximize agriculture gain |
| Balanced | 20% | 15% | No scenario cap | Minimize changed land |

All scenarios also maximize biodiversity gain and carbon gain and minimize
cost. Existing physical constraints remain active:

- protected cells cannot change;
- existing wetland cannot be reduced;
- wetland gain is capped by suitability and capacity;
- modeled land share is conserved; and
- target fractions remain non-negative.

`agriculture_loss_pct` and `agriculture_gain_pct` report non-negative
county-wide net change relative to current agriculture. Gross agriculture loss
and gain separately sum cell-level decreases and increases, revealing
relocation that the net metrics can hide. Wetland Priority prices gross
agriculture expansion and treats net expansion above 5% or gross expansion
above 15% as infeasible.
Sustainable Agriculture Expansion requires 5–10% net expansion, permits no
more than 2% gross agriculture loss, and permits no more than 1% biodiversity
or carbon loss. It therefore expands total agricultural area without
achieving the result by extensively removing and relocating existing
farmland.
`wetland_gain_pct` is total non-negative wetland increase divided by current
county-wide wetland. Values are stored as fractions: `0.03` means 3%.

## Representative selection

Notebook 10 selects representatives only from feasible policies. If a scenario
has no feasible policy, it uses the least-violating candidates and labels the
scenario `infeasible`.

| Scenario | Selection rule |
|----------|----------------|
| Green Maximum | Maximize the sum of independently normalized biodiversity and carbon gains |
| Food Security | Maximize biodiversity gain |
| Low Budget | Minimize distance to the normalized biodiversity/carbon/cost ideal |
| Wetland Priority | Minimize distance to the normalized biodiversity/carbon/cost/wetland ideal |
| Sustainable Agriculture Expansion | Minimize distance to the normalized agriculture/biodiversity/carbon/cost ideal |
| Balanced | Minimize distance to the normalized biodiversity/carbon/cost/changed-land ideal |

Ties are deterministic: lower cost, then lower changed land, then lower stable
policy ID. The selected policy is computed once and reused for the summary,
dominant-action plot, change-intensity plot, wetland-gain plot, and saved
GeoPackage.

## Running Notebook 10

Install the notebook profile and launch Jupyter:

```bash
uv sync --extra notebook
uv run --extra notebook jupyter lab
```

Open `notebooks/10_scenario_comparison.ipynb`, restart the kernel, and run all
cells. The committed full configuration is:

```python
POP_SIZE = 200
N_GENERATIONS = 200
```

The six-scenario full run can take hours. For a smoke test, work on a
temporary notebook copy and reduce both values; do not commit smoke settings or
overwrite reviewed full-run results accidentally.

By default, Notebook 10 writes into
`data/processed/learned_carbon/`. A new run replaces files with the same names,
so archive previous results first when a direct before/after comparison is
needed.

## Outputs

| Output | Contents |
|--------|----------|
| `scenario_summary.parquet` | One representative row per scenario, including status, rule, policy ID, gains, cost, net/gross agriculture metrics, violation, feasible count, front size, and runtime |
| `scenario_comparison.parquet` | Pareto-front metrics for all scenarios, with one `is_representative=True` row per scenario |
| `scenario_maps/<scenario>.gpkg` | Per-cell action, change intensity, and current/target/delta fractions for the selected representative |

## Result review checklist

Before treating a run as suitable for comparison, confirm:

1. Every scenario has at least one feasible solution.
2. Food Security agriculture loss is no more than `0.03`.
3. Low Budget changed land is no more than `0.06`.
4. Wetland Priority agriculture gain is no more than `0.05`.
5. Wetland Priority gross agriculture gain is no more than `0.15`.
6. Wetland Priority biodiversity and carbon gains are non-negative.
7. Wetland Priority produces greater wetland gain than Balanced.
8. Agriculture is the dominant action in less than 20% of Wetland Priority
   map cells.
9. Sustainable Agriculture Expansion has 5–10% net agriculture gain.
10. Sustainable Agriculture Expansion has no more than 2% gross agriculture
    loss and no more than 15% changed land.
11. Sustainable Agriculture Expansion biodiversity and carbon gains are each
    at least `-0.01`.
12. Exactly one Pareto row per scenario is marked as representative.
13. Representative maps are not all identical.
14. Protected-cell deltas are zero and wetland deltas are non-negative.

The results are decision-support proxies, not calibrated ecological forecasts
or official planning recommendations.
