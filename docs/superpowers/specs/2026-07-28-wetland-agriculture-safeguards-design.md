# Wetland Agriculture Safeguards Design

## Goal

Correct the Wetland Priority result that achieved the highest wetland gain by
expanding agriculture, reducing biodiversity, and reducing carbon. Preserve
the successful hard scenario limits and feasible-first NSGA-II behavior while
making Wetland Priority representative selection ecologically credible and
its maps easier to interpret.

This change uses existing local data and the completed 200-policy populations.
It does not download data. If the live Notebook 10 kernel remains available,
the existing policies will be re-scored and reporting cells rerun without
repeating evolution.

## Observed Failure

The completed Wetland Priority representative had:

- 1.7818% wetland gain;
- 33.64% county-wide net agriculture expansion;
- 35.14% gross agriculture gain;
- negative biodiversity gain;
- negative carbon gain;
- 4,235 cells labelled as agriculture; and
- only 54 cells labelled as wetland, although 183 cells gained wetland.

The dominant-action map contributed to the confusing presentation. A cell can
gain both wetland and agriculture but is labelled agriculture when agriculture
is the larger positive delta. About 67% of the representative's total wetland
gain occurred in cells whose dominant label was agriculture.

The behavior was permitted because agriculture loss was constrained while
agriculture expansion was not, agriculture expansion had no specific cost,
and Wetland Priority selected the absolute maximum wetland-gain policy without
considering its biodiversity or carbon effects.

## Scope

The correction changes four connected areas:

1. simulator agriculture metrics and Wetland Priority safeguards;
2. Wetland Priority representative selection;
3. scenario summary reporting; and
4. Notebook 10 wetland visualization and post-run validation.

The other four scenarios retain their current agriculture-expansion
feasibility semantics. Existing physical constraints remain unchanged.

## Agriculture Metrics

`summarize_policy` will retain the existing county-wide net
`agriculture_loss_pct` and add:

- `agriculture_gain_pct`: non-negative county-wide net agriculture expansion
  divided by current county-wide agriculture;
- `gross_agriculture_loss_pct`: sum of cell-level agriculture decreases
  divided by current county-wide agriculture; and
- `gross_agriculture_gain_pct`: sum of cell-level agriculture increases
  divided by current county-wide agriculture.

When current county-wide agriculture is zero, all four agriculture percentages
are zero.

Net metrics describe the county-wide balance. Gross metrics reveal relocation
and opposing cell-level changes that net aggregation can hide. All values
remain fractions internally; `0.05` means 5%.

## Wetland Priority Agriculture Safeguards

Wetland Priority will explicitly set:

```python
config["max_total_agri_gain_pct"] = 0.05
config["max_gross_agri_gain_pct"] = 0.15
config["scoring"]["agriculture_gain_cost"] = 10.0
```

`max_total_agri_gain_pct` is a hard county-wide net expansion limit. Excess
above 5% contributes directly to `constraint_penalty`, so feasible-first
NSGA-II ranks every compliant policy ahead of every policy exceeding the cap.

`max_gross_agri_gain_pct` is a hard 15% limit on summed cell-level
agriculture increases. It was added after the first safeguard smoke run showed
that the cost reduced agriculture-labelled cells but did not guarantee the
approved gross-gain acceptance gate.

`agriculture_gain_cost` applies to gross cell-level agriculture gain. It
discourages forest or grassland conversion to agriculture and prevents
opposing cell-level gains and losses from becoming free merely because their
county-wide net change is small. The hard cap remains authoritative; the cost
term differentiates compliant policies.

The default configuration uses:

```python
config["max_total_agri_gain_pct"] = 1.0
config["max_gross_agri_gain_pct"] = 1.0
config["scoring"]["agriculture_gain_cost"] = 0.0
```

These defaults preserve existing behavior for other scenarios. Notebook 10
sets the 5% limit and expansion-cost weight only inside the Wetland Priority
configuration.

## Wetland Representative Selection

The Wetland Priority representative changes from absolute maximum wetland gain
to a normalized ecological knee. Among feasible policies, minimize Euclidean
distance to the four-dimensional ideal:

1. maximum biodiversity gain;
2. maximum carbon gain;
3. minimum cost; and
4. maximum wetland gain.

Each metric is independently min-max normalized. A zero-range metric has zero
normalized loss and cannot distort selection. Deterministic ties use lower
cost, then lower changed land, then lower stable policy ID.

The existing feasible-only rule remains. If no policy is feasible, selection
uses the least-violating candidates and the summary marks the scenario
infeasible.

Wetland Priority selection must yield non-negative biodiversity and carbon in
the post-run acceptance check. This is an experiment gate rather than a new
hard optimizer constraint. If the knee fails the gate, the result is rejected
and the selection design is revisited.

The selected policy is computed once and reused for:

- the scenario summary;
- the dominant-action map;
- the change-intensity map;
- the dedicated wetland-delta map; and
- the saved scenario GeoPackage.

## Summary Reporting

The scenario summary will continue to report `Agriculture loss` for the
existing net loss metric and add:

- `Agriculture gain`;
- `Gross agriculture loss`; and
- `Gross agriculture gain`.

The Pareto comparison parquet will include the corresponding internal metric
columns and exactly one `is_representative=True` row per scenario.

## Wetland Visualization

Notebook 10 keeps the dominant-action map because it summarizes the largest
positive land-use change per cell. It adds a dedicated continuous
`delta_wetland` figure for all five representatives.

The wetland figure will:

- use the same selected policies as the summary;
- show wetland fraction gain directly rather than dominant action;
- use a common color scale across scenarios; and
- make zero or negligible wetland change visually distinct.

The saved GeoPackages already contain `delta_wetland`; no duplicate spatial
output format is required.

## Existing-Population Re-Scoring

The completed Notebook 10 kernel appears to remain active. After implementation:

1. reload the changed simulator and scenario-helper modules;
2. rebind Notebook 10 imports to the reloaded functions;
3. re-evaluate the existing 200 policies per scenario with the revised
   configuration and metrics;
4. rebuild Pareto DataFrames and feasibility annotations;
5. recompute representatives;
6. regenerate summaries, figures, and GeoPackages; and
7. validate the regenerated artifacts.

The populations were evolved under the previous expansion cost. Re-scoring
them is an efficient first correction because the completed population already
contains ecologically positive, high-wetland alternatives. The result must be
reported as re-selection from the existing population, not as evolution under
the revised cost.

If the live kernel cannot be reused, stop before launching another full
200-population, 200-generation, five-scenario experiment and ask for approval.

## Testing

Tests will be written before implementation and cover:

- net and gross agriculture gain/loss from a hand-derived multi-cell fixture;
- zero-current-agriculture denominators;
- exact and excess agriculture-expansion limits;
- gross agriculture expansion increasing policy cost;
- Wetland Priority choosing the normalized ecological knee rather than the
  absolute wetland extreme;
- deterministic ties and least-violation fallback;
- expanded summary metrics;
- consistent representative reuse; and
- Notebook 10's dedicated wetland-delta visualization contract.

The full Ruff and pytest suites must pass. Notebook 10 code cells must compile
without execution before live-kernel re-scoring.

## Result Acceptance

Re-scored Wetland Priority results must satisfy:

- net agriculture expansion at or below 5%;
- non-negative biodiversity gain;
- non-negative carbon gain;
- wetland gain greater than Balanced;
- gross agriculture gain at or below 15%;
- agriculture-labelled cells below 20% of mapped cells;
- protected-cell target deltas equal zero;
- wetland target deltas non-negative; and
- one and only one representative row in saved Pareto output.

The before/after report will state exact representative metrics, action counts,
gross and net agriculture changes, and whether re-scoring reused the previous
population.
