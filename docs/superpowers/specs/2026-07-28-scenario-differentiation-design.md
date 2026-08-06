# Scenario Differentiation Design

## Goal

Make the five policy scenarios produce honest, materially different feasible
policies. Explicit policy limits become hard feasibility constraints, while
scenario aspirations remain optimization or representative-selection
preferences.

This work uses the prepared compartment-first carbon predictions and existing
local data. It does not download data or immediately rerun the full
200-population, 200-generation, five-scenario experiment.

## Policy Semantics

The scenarios use these hard county-level limits:

| Scenario | Maximum changed land | Maximum agriculture loss |
|---|---:|---:|
| Green Maximum | 40% | 50% |
| Food Security | 15% | 3% |
| Low Budget | 6% | 15% |
| Wetland Priority | 25% | 15% |
| Balanced | 20% | 15% |

`max_changed_pct` and `max_total_agri_loss_pct` are no longer merely prices
that a high-benefit policy can pay. Any excess contributes to aggregate
`constraint_penalty`, so feasible-first NSGA-II prefers every compliant policy
over every noncompliant policy.

Existing physical rules remain hard:

- protected cells do not change;
- existing wetland is not reduced;
- wetland gain obeys suitability and capacity;
- targets conserve modeled land share and remain non-negative.

Cost remains an optimization objective within the feasible region. Existing
soft excess penalties may remain in the cost calculation for backward
compatibility, but they do not replace or weaken feasibility.

## Aggregate Metrics

`summarize_policy` will expose:

- `changed_pct`: mean per-cell changed share, as currently calculated;
- `agriculture_loss_pct`: non-negative county-wide agriculture loss divided by
  current county-wide agriculture;
- `wetland_gain_pct`: non-negative county-wide wetland increase divided by
  current county-wide wetland;
- `constraint_penalty`: physical violation plus excess over the configured
  changed-land and agriculture-loss limits.

When a current county-wide denominator is zero, its corresponding percentage
is zero. Gains do not offset losses: agriculture expansion produces zero
agriculture loss, and any impossible wetland loss remains handled by the
physical constraint.

The new percentages are dimensionless and are reported as fractions internally
and percentages in human-facing tables.

## Optimization Objectives

The standard objective tuple remains:

1. maximize biodiversity gain;
2. maximize carbon gain;
3. minimize cost;
4. minimize changed land.

Wetland Priority replaces objective four with maximizing
`wetland_gain_pct`. Its 25% hard change limit still caps the total
intervention. This avoids adding a fifth objective, which would worsen the
observed all-policies-on-Front-0 behavior.

The trainer will select objective four from explicit configuration, with
`"changed_pct"` as the default and `"wetland_gain_pct"` as the only additional
supported value. Unsupported values fail before evolution starts.

## Representative Policy Selection

A pure scenario helper will select one representative row and return its stable
row identifier. Only feasible policies are eligible. If none are feasible, the
least-violating policy is selected and the scenario is marked `infeasible`.

Selection rules:

- **Green Maximum:** maximize the sum of independently min-max-normalized
  biodiversity and carbon gains.
- **Food Security:** maximize biodiversity gain.
- **Low Budget:** minimize Euclidean distance to the normalized ideal of
  maximum biodiversity, maximum carbon, and minimum cost.
- **Wetland Priority:** maximize wetland gain.
- **Balanced:** minimize Euclidean distance to the normalized ideal of maximum
  biodiversity, maximum carbon, minimum cost, and minimum changed land.

For a metric with zero range, its normalized loss is zero so it cannot distort
selection. Ties are deterministic: lower cost, then lower changed land, then
the stable row identifier.

Notebook 10 will compute representatives once and reuse the same selected
policy for:

- the scenario summary;
- dominant-action maps;
- change-intensity maps;
- saved scenario GeoPackages.

This prevents the table and maps from silently representing different
policies.

## Reporting

The scenario summary will include:

- scenario label;
- status (`feasible` or `infeasible`);
- selection rule;
- biodiversity gain;
- carbon gain;
- cost;
- changed land;
- agriculture loss;
- wetland gain;
- constraint violation;
- feasible-solution count;
- front size;
- runtime.

Metric comparison plots continue to display complete Pareto fronts. Because
Wetland Priority uses a different fourth optimization objective and a modified
biodiversity scale, ecological scores are interpreted within scenario; the
shared hard limits and common reported metrics support cross-scenario checks.

## Components

### Simulator

`src/estonia_landuse/simulator/simulator.py` computes aggregate land-change
metrics once and adds hard-limit excess to `constraint_penalty`.

### Optimizer

`src/estonia_landuse/optimizer/trainer.py` validates and applies the configured
fourth objective. The custom biodiversity trainer in Notebook 03.2 remains
outside this scenario-specific change.

### Scenario Helpers

`src/estonia_landuse/scenarios.py` owns feasibility annotation,
representative selection, and stable summary construction. Notebook 10 does
not duplicate selection formulas.

### Notebook 10

Notebook 10 defines explicit scenario limits and the Wetland Priority fourth
objective, calls shared helpers, and retains one mapping from scenario to
selected population member. Current executed results remain uncommitted while
source-only changes are staged.

## Testing

Tests will be written before implementation and cover:

- changed-land excess makes an otherwise physical policy infeasible;
- county agriculture-loss excess makes a policy infeasible;
- policies exactly on each limit remain feasible within numerical tolerance;
- aggregate agriculture-loss and wetland-gain metrics;
- default and Wetland Priority objective tuples;
- rejection of an unsupported fourth objective;
- every representative-selection rule;
- deterministic tie-breaking;
- least-violation fallback when no policy is feasible;
- summary schema and selected-row consistency;
- Notebook 10's use of shared scenario helpers and explicit configurations.

The full Ruff and pytest suites must pass. Notebook code cells will be compiled
without execution.

## Experiment Gate

Before another full run, execute a deterministic smoke experiment with a small
population and generation count for all five scenarios. The smoke review must
confirm:

- at least one feasible policy per scenario;
- Food Security representative agriculture loss at or below 3%;
- Low Budget representative changed land at or below 6%;
- Wetland Priority representative wetland gain greater than Balanced;
- representative maps are not all identical;
- protected-cell and wetland-preservation invariants remain exact.

Only after this gate passes will the user decide whether to rerun the complete
Notebook 10 experiment.
