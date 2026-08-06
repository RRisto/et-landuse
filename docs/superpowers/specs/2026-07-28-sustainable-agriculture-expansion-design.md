# Sustainable Agriculture Expansion Scenario Design

## Goal

Add a sixth Notebook 10 scenario that increases county-wide agricultural
land by a meaningful but bounded amount while preserving existing farmland
and limiting ecological harm.

The scenario is named `sustainable_agriculture` and displayed as
**Sustainable Agriculture Expansion**.

## Policy Contract

The selected representative must satisfy all of these hard constraints:

| Metric | Requirement |
|---|---:|
| Net agriculture gain | 5% to 10%, inclusive |
| Gross agriculture loss | No more than 2% |
| Changed land | No more than 15% |
| Biodiversity gain | At least -1% |
| Carbon gain | At least -1% |
| Wetland change | No cell may lose wetland |
| Protected-cell change | Zero |

Percentages are fractions in code: 5% is `0.05`. Agriculture percentages
use current county-wide agriculture as their denominator. Biodiversity,
carbon, and changed-land metrics retain their existing definitions.

Wetland and protected-cell requirements continue to use the simulator's
existing target-projection invariants. The new scenario does not weaken
them.

## Configuration

The default configuration gains nonbinding values so existing scenarios
retain their behavior:

```python
config["min_total_agri_gain_pct"] = 0.0
config["max_gross_agri_loss_pct"] = 1.0
config["min_biodiversity_gain"] = -1.0
config["min_carbon_gain"] = -1.0
```

Notebook 10 configures Sustainable Agriculture Expansion with:

```python
config["max_changed_pct"] = 0.15
config["max_total_agri_loss_pct"] = 1.0
config["min_total_agri_gain_pct"] = 0.05
config["max_total_agri_gain_pct"] = 0.10
config["max_gross_agri_loss_pct"] = 0.02
config["min_biodiversity_gain"] = -0.01
config["min_carbon_gain"] = -0.01
config["scoring"]["agriculture_loss_cost"] = 30.0
config["scoring"]["agriculture_gain_cost"] = 0.0
config["optimization"]["fourth_objective"] = "agriculture_gain_pct"
```

The minimum-gain constraint makes policies below 5% infeasible. The
existing maximum-gain constraint makes policies above 10% infeasible.
Gross agriculture loss is capped separately so expansion cannot be
achieved by removing and relocating large amounts of existing farmland.

The biodiversity and carbon floors permit no more than a 1% loss in either
metric. Constraint excesses are added to `constraint_penalty`; feasible-first
NSGA-II therefore ranks every compliant policy ahead of every noncompliant
policy.

## Optimization

`agriculture_gain_pct` becomes a supported fourth objective. NSGA-II
minimizes internally, so its objective value is the negative of the reported
agriculture gain.

Progress output must use the configured metric's public name and direction:

- Default scenarios: `change=...`
- Wetland Priority: `wetland_gain=...`
- Sustainable Agriculture Expansion: `agriculture_gain=...`

The two gain labels display positive reported gains rather than their
sign-inverted internal objective values.

## Representative Selection

The new `sustainable_agriculture` rule chooses the feasible policy closest
to the normalized ideal across:

- maximum net agriculture gain;
- maximum biodiversity gain;
- maximum carbon gain; and
- minimum cost.

The normalized Euclidean knee avoids selecting an ecological extreme or the
absolute maximum agricultural expansion. Existing deterministic tie-breaking
remains: lower cost, lower changed land, then lower stable policy ID.

If no feasible policy exists, the existing least-violation fallback remains
active and the summary marks the representative `infeasible`.

## Notebook and Outputs

Notebook 10 adds the scenario to `SCENARIOS` and `SELECTION_RULES`. Existing
training, summary, Pareto, dominant-action, change-intensity, wetland-gain,
and GeoPackage loops must include it automatically.

The saved files retain their current schemas:

- `scenario_summary.parquet`
- `scenario_comparison.parquet`
- `scenario_maps/sustainable_agriculture.gpkg`

No data is downloaded. Existing prepared data and learned-carbon predictions
are reused. The user's current Notebook 10 execution outputs are preserved
while source changes are committed without outputs.

## Documentation

README and `docs/scenario-comparison.md` document:

- the sixth scenario;
- its 5–10% net expansion band;
- its 2% gross-loss cap;
- its ecological floors;
- the difference between net expansion and gross relocation; and
- the new acceptance checks.

## Testing

Automated tests cover:

1. Minimum net agriculture gain contributes the exact shortfall to
   `constraint_penalty`.
2. A policy exactly at the minimum remains feasible.
3. Gross agriculture loss above 2% contributes the exact excess.
4. Biodiversity and carbon values below their floors contribute exact
   shortfalls.
5. `agriculture_gain_pct` is maximized as the fourth objective.
6. Progress labels and signs match the configured fourth objective.
7. The new representative rule selects the intended normalized knee from
   feasible policies only.
8. Notebook 10 contains the scenario configuration, label, rule, and
   objective.
9. Existing scenarios retain nonbinding defaults and unchanged behavior.

## Acceptance

Before the new full result is accepted:

1. Sustainable Agriculture Expansion has at least one feasible policy.
2. Its representative has net agriculture gain from 5% through 10%.
3. Gross agriculture loss is no more than 2%.
4. Changed land is no more than 15%.
5. Biodiversity and carbon gains are each at least -1%.
6. Protected-cell deltas are zero.
7. Wetland deltas are non-negative.
8. Land fractions remain balanced and target fractions are non-negative.
9. Exactly one representative is saved for the scenario.
10. Its map is distinct from the other scenario maps.

The experiment remains decision support rather than a calibrated crop-yield
forecast. Agricultural area is optimized; food production, soil quality,
crop suitability, and farm economics are not modeled as direct outcomes.
