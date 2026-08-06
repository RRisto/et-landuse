# Reliability Hardening Design

## Goal

Harden the 500 m land-use neuroevolution workflow so that infeasible policies
cannot be presented as valid solutions, spatial calculations work with arbitrary
cell identifiers, runs are reproducible, external data ingestion is safe, and
the core behavior is covered by automated tests and continuous integration.

## Branch and Local Data

Development takes place on `codex/reliability-hardening-500m`, based directly on
`origin/feature/500m-grid`.

The repository's ignored `data/` directory contains expensive local artifacts.
The implementation and verification workflow must reuse these artifacts and
must not execute the Rohemeeter collection workflow. Tests must use synthetic
fixtures unless a read-only integration check explicitly needs existing local
data.

## Constraint-Aware Optimization

The simulator continues to return a numeric `constraint_penalty` for every
policy. NSGA-II selection uses Deb-style feasible-first constraint handling:

1. A feasible policy always dominates an infeasible policy.
2. Two feasible policies are compared using the existing biodiversity, carbon,
   cost, and changed-area objectives.
3. Two infeasible policies are ordered by total constraint violation; ordinary
   objectives break exact ties.

Feasibility is defined as a finite aggregate constraint penalty less than or
equal to a small numerical tolerance. The tolerance is centralized and tested.
The final population exposes constraint violation alongside other metrics so
notebooks and reports can distinguish feasibility explicitly.

## Spatial Aggregation

Road length and building count calculations aggregate by `cell_id`, then map
the aggregate back to grid row order. They must support non-contiguous integer
IDs, string IDs, filtered grids, and arbitrary row order without treating an ID
as a NumPy array position.

## Validation and Reproducibility

Public simulator and optimizer entry points validate:

- target array shape and row count;
- required feature columns;
- finite numeric values;
- valid population and generation parameters;
- non-negative land-use targets with positive row totals.

Validation errors name the invalid field or column. Training accepts a seed or
NumPy `Generator`; all initialization, crossover, mutation, tournament
selection, and seed training draw from that generator. Identical inputs and
seeds produce identical populations.

## Safe External Data Handling

ZIP extraction rejects absolute member paths and any member whose resolved
destination escapes the extraction directory.

Downloads write to a temporary sibling file, validate the response, and
atomically replace the final destination only after success. Interrupted
downloads do not become cache hits.

Forest Registry WFS requests use explicit connect/read timeouts and bounded
retry behavior. Pagination raises an error on an unsuccessful or incomplete
download rather than returning a partial dataset as complete. Empty detail-ID
input returns an empty DataFrame without starting an event loop or dividing by
zero.

## Tests and Automation

Pytest tests cover:

- feasible-first dominance and selection;
- arbitrary `cell_id` aggregation;
- malformed and non-finite optimizer/simulator inputs;
- deterministic seeded training;
- ZIP traversal rejection;
- atomic download behavior;
- WFS retry/completeness behavior;
- empty Forest Registry detail input;
- no-change and representative carbon-transition invariants.

Tests use synthetic local data and mocked network boundaries. They never invoke
Rohemeeter or download production datasets.

Ruff checks formatting-quality rules and pytest runs in GitHub Actions on the
project's supported Python versions. CI installs only the dependencies needed
for linting and unit tests.

## Dependency and Notebook Boundaries

Dependencies are grouped into core runtime, notebook/visualization,
data-pipeline, ML, development, and an aggregate `all` extra. The default
installation remains sufficient for the importable core package.

Calculations needed by notebooks are moved into importable, tested Python
functions only where this hardening work touches duplicated logic. Notebooks
remain orchestration and visualization documents; the existing modified
`notebooks/10_scenario_comparison.ipynb` in the original checkout is not
modified or copied into the branch.

## Documentation

The README documents:

- reproducible seeded training;
- dependency installation choices;
- test and lint commands;
- how local processed data is reused;
- that Rohemeeter collection is expensive and should not be rerun when its
  processed outputs already exist;
- how constraint feasibility is represented in optimization results.

## Acceptance Criteria

- Constraint-violating policies cannot outrank feasible policies.
- Spatial density output is correct for arbitrary cell IDs.
- Invalid/non-finite inputs fail before evolution begins.
- Same-seed training is reproducible.
- Archive and download operations cannot expose partial or escaped outputs.
- Forest Registry ingestion fails loudly on incomplete WFS pagination and
  handles empty detail input.
- Automated tests and Ruff pass without network access or Rohemeeter execution.
- The implementation branch remains based on `origin/feature/500m-grid`, and
  the user's existing notebook modification and local data remain intact.
