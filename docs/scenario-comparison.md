# Notebook 10 Scenario Comparison

Notebook `10_scenario_comparison.ipynb` runs five policy scenarios with
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

Remote-data notebooks use `ALLOW_DOWNLOADS = False` by default. Leave this
flag unchanged to reuse local Forest Registry, Rohemeeter, and other prepared
data. Set it to `True` only when intentionally refreshing a source.

## Scenario semantics

The percentages below are hard feasibility limits. A policy exceeding either
limit receives positive `constraint_penalty`; feasible-first NSGA-II ranks
every feasible policy ahead of every infeasible policy.

| Scenario | Maximum changed land | Maximum agriculture loss | Maximum agriculture gain (net/gross) | Fourth objective |
|----------|---------------------:|-------------------------:|-------------------------:|------------------|
| Green Maximum | 40% | 50% | No scenario cap | Minimize changed land |
| Food Security | 15% | 3% | No scenario cap | Minimize changed land |
| Low Budget | 6% | 15% | No scenario cap | Minimize changed land |
| Wetland Priority | 25% | 15% | 5% / 15% | Maximize wetland gain |
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

The five-scenario full run can take hours. For a smoke test, work on a
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
9. Exactly one Pareto row per scenario is marked as representative.
10. Representative maps are not all identical.
11. Protected-cell deltas are zero and wetland deltas are non-negative.

The results are decision-support proxies, not calibrated ecological forecasts
or official planning recommendations.
