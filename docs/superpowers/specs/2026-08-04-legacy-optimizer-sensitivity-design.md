# Legacy Optimizer Sensitivity Design

## Objective

Build a reproducible and practical sensitivity-analysis suite for the historical land-use optimizer that produced the accepted Notebook 10 scenario results. Preserve `notebooks/10_scenario_comparison.ipynb` byte-for-byte as the reference experiment.

## Reference model

The scientific reference is the code and data contract on branch `codex/legacy-optimizer-sensitivity` at preservation commit `d5a52db1e8308271787425aeeff9735e66d7773b`:

- Notebook 10 SHA-256: `89DD52DC8376F330728AB3A186423FFAF5B04AE15A14FD91CED1E45C21EF9D45`.
- Historical trainer API: `train(..., seed=<int>, rng=<Generator>)`.
- Four-objective model with scenario-specific `optimization.fourth_objective`.
- Constraint-dominance during NSGA-II selection.
- Scenario-specific feasible representative selection from `estonia_landuse.scenarios`.
- Target realization through `estonia_landuse.simulator.targets.realize_targets`.

Notebook 10 and its five committed plots must not be edited by this work. Its saved `scenario_summary.parquet` is the seed-42 reproduction reference.

## Selected approach

Keep the historical scientific model unchanged while improving execution around it:

1. Add a parallel Notebook 10 reproduction workflow as a new Notebook 10.1.
2. Profile the historical implementation and optimize only proven bottlenecks.
3. Require equivalence tests before accepting any performance change.
4. Build Notebooks 11.1-11.5 on the verified historical runner.
5. Use staged `test`, `screen`, and `full` profiles to avoid unnecessary full optimizer runs.

Reducing the population or generation count is allowed only in `test` and `screen` profiles. It is not evidence that the historical full model is reproduced.

## Architecture

### Historical experiment adapter

A focused sensitivity package under `src/estonia_landuse/sensitivity/` will adapt manifests to the historical interfaces. It will not introduce a second optimizer or reinterpret scenario objectives.

The adapter will:

- obtain scenario configurations from a historical adapter whose outputs are contract-tested
  against Notebook 10's unchanged inline configuration cell;
- call the historical trainer with an explicit integer `seed`;
- retain historical constraint-dominance;
- evaluate rank-zero policies using the historical reporting fields;
- select representatives through the scenario-specific selection rules;
- realize and save the selected target fractions;
- store scenario configuration, input, code, profile, seed, and selection metadata with each artifact.

The historical configuration adapter is intentionally a literal reproduction of the six Notebook 10
scenario branches. It always starts from a fresh `default_config()`, sets `carbon_model="learned"`,
and rejects unknown scenario IDs rather than silently returning the base configuration. In particular,
the wetland-priority and sustainable-agriculture scenarios retain their distinct
`optimization.fourth_objective` values (`wetland_gain_pct` and `agriculture_gain_pct`), while the
balanced scenario preserves `max_changed_pct=0.20`. Scenario labels and representative-selection
rules are copied from the same Notebook 10 cell and contract-tested with the notebook SHA guard.

### Parallel execution

Parallelism will occur across independent optimizer runs, not inside one evolutionary trajectory. A parent process will own manifests, progress reporting, and status writes. Worker processes will receive immutable context once at initialization and return one terminal result per run.

Notebook 10.1 will run independent scenarios concurrently with seed 42. Sensitivity notebooks will run independent scenario/seed/parameter combinations concurrently. The default worker count will be conservative on Windows and configurable through `SENSITIVITY_N_WORKERS`.

Parallel scheduling must not change a run's result. Artifact identity must include scenario, seed, experiment, sample, input fingerprint, profile, and model/code fingerprint.

### Performance optimization

Optimization begins with measurement. Benchmarks will separate:

- simulator and target-realization time;
- population evaluation time;
- NSGA-II sorting and crowding time;
- serialization and process-startup time.

Permitted improvements include caching immutable context arrays, precomputing invariant inputs, reducing repeated DataFrame conversion, and replacing Python-heavy operations with equivalent vectorized implementations. Any optimization that changes Pareto ranks, representative identity, realized targets, or reported metrics beyond numerical tolerance is rejected.

## Reproduction contract

Notebook 10.1 must compare its seed-42 scenario results with the committed Notebook 10 reference outputs. For each scenario it must verify:

- the scenario exists and uses the same effective configuration;
- a feasible representative is selected where Notebook 10 selected one;
- the representative uses the same scenario selection rule;
- biodiversity, carbon, cost, changed land, agriculture, and wetland metrics match within explicit floating-point tolerances;
- realized target arrays match within explicit floating-point tolerances when a historical target artifact is available.

The initial compatibility gate may use the saved scenario summary because Notebook 10 did not preserve every population object. A fresh sequential reference run and a parallel run with the same code and seed must then match directly.

The full sensitivity suite cannot be described as valid until this gate passes.

## Experiment profiles

Profiles define computational effort without changing scenario semantics:

| Profile | Purpose | Population | Generations | Seeds and samples |
|---|---|---:|---:|---|
| `test` | Import, artifact, and smoke verification | 8 | 2 | Minimal deterministic subset |
| `screen` | Economical parameter screening | 80 | 60 | Reduced seeds and parameter grid |
| `full` | Confirmation using Notebook 10 model scale | 200 | 200 | Prespecified final design |

Screening results identify parameters worth confirming but must remain labelled as reduced-effort results. Final claims use the `full` profile.

## Notebook suite

### Notebook 10.1: fast scenario reproduction

- Runs all six historical scenarios with seed 42.
- Executes scenarios in parallel when more than one worker is configured.
- Uses configurations proven equivalent to Notebook 10's inline definitions and the same
  representative rules.
- Compares the resulting summary with Notebook 10's saved reference summary.
- Writes to a new versioned sensitivity output root and never overwrites Notebook 10 outputs.

### Notebook 11.1: stochastic baseline

- Runs every canonical scenario across optimizer seeds.
- Includes seed 42 in every profile that is intended for reproduction or confirmation.
- Quantifies metric and spatial variation.
- Provides the seed-noise baseline consumed by later notebooks.

### Notebook 11.2: one-at-a-time screening

- Changes one prespecified scalar assumption from its scenario default.
- Uses the staged profile design to limit exploratory cost.
- Reports response curves, uncertainty across seeds, and effect size relative to 11.1 seed noise.

### Notebook 11.3: global sensitivity

- Samples influential assumptions jointly using a reproducible space-filling design.
- Ranks parameter importance after averaging repeated seeds per parameter sample.
- Reports model-fit diagnostics so weak importance estimates are not overinterpreted.

### Notebook 11.4: interactions

- Tests only prespecified or screening-supported parameter pairs.
- Estimates interaction residuals after accounting for main effects.
- Compares interaction magnitude with baseline seed variation.

### Notebook 11.5: robustness synthesis

- Reuses completed artifacts rather than retraining identical runs.
- Tests biodiversity-value alternatives and scenario-rank stability.
- Produces a concise report of stable conclusions, unstable conclusions, and missing evidence.

## Artifact isolation and recovery

All new artifacts will live below a dedicated root such as `data/processed/legacy_sensitivity/`. Notebook 10's `data/processed/learned_carbon/` outputs are read-only reference inputs for this work.

Runs must be resumable. Completed artifacts are reused only when all identity metadata match. Interrupted `running` records must be repairable. Only the parent process may update manifest CSV files, preventing concurrent Windows file replacement failures.

## Testing

Development follows test-driven development. Required automated coverage includes:

- manifest products and run counts for every profile;
- historical trainer argument mapping;
- scenario-specific fourth objectives;
- constraint-dominance preservation;
- scenario-specific representative selection;
- sequential/parallel equivalence for identical manifests;
- deterministic seed reproduction;
- artifact isolation, identity, resume, and stale-status repair;
- seed-42 Notebook 10 summary comparison;
- notebook structural contracts and preservation of the Notebook 10 hash.

The final verification runs the full project test suite and Ruff. A smoke execution of Notebook 10.1 and each Notebook 11 entry point must succeed with the `test` profile.

## Delivery sequence

1. Add the historical runner and seed-42 reproduction tests.
2. Add Notebook 10.1 and pass the reproduction gate.
3. Profile and implement only equivalence-proven performance improvements.
4. Add the resumable parallel manifest runner.
5. Add Notebooks 11.1-11.5 and their analysis helpers.
6. Run all test-profile notebooks and document expected screen/full run counts and runtimes.

## Non-goals

- Editing Notebook 10 or its committed plots.
- Replacing historical fourth-objective semantics with the newer generic objective-list model.
- Mixing artifacts from the redesigned optimizer with historical sensitivity artifacts.
- Claiming that reduced `test` or `screen` profiles reproduce full convergence.
- Requiring all expensive full-profile runs during implementation.
