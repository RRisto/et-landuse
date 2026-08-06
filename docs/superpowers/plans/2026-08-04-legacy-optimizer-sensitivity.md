# Legacy Optimizer Sensitivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a faster, reproducible sensitivity-analysis suite for the exact historical optimizer behind Notebook 10 while keeping Notebook 10 byte-identical.

**Architecture:** A historical-model adapter reproduces Notebook 10's inline scenario configurations and scenario-specific representative selection. A resumable parent-owned manifest runner executes independent optimizer runs sequentially or in Windows-safe process workers. Notebook 10.1 verifies seed-42 reproduction, and Notebooks 11.1-11.5 reuse the same runner for staged sensitivity experiments.

**Tech Stack:** Python 3.12, NumPy, pandas, SciPy, scikit-learn, GeoPandas, PyArrow, Matplotlib, Jupyter, pytest, Ruff, `concurrent.futures.ProcessPoolExecutor`.

## Global Constraints

- Never modify `notebooks/10_scenario_comparison.ipynb` or its five committed plot files.
- Preserve Notebook 10 SHA-256 `89DD52DC8376F330728AB3A186423FFAF5B04AE15A14FD91CED1E45C21EF9D45` in a regression test.
- Use the historical trainer API `train(..., seed=<int>)` and its built-in constraint-dominance semantics.
- Preserve historical `optimization.fourth_objective` values and scenario-specific representative rules.
- Write all new artifacts below `data/processed/legacy_sensitivity/`; treat `data/processed/learned_carbon/` as read-only.
- `test` and `screen` results are reduced-effort diagnostics; only `full` uses population 200 and 200 generations.
- Parallelism occurs only across independent runs; a parent process exclusively owns manifest updates and progress callbacks.

---

### Task 1: Freeze the Notebook 10 scientific contract

**Files:**
- Create: `src/estonia_landuse/sensitivity/__init__.py`
- Create: `src/estonia_landuse/sensitivity/historical_model.py`
- Create: `tests/sensitivity/test_historical_model.py`
- Modify: `docs/superpowers/specs/2026-08-04-legacy-optimizer-sensitivity-design.md`

**Interfaces:**
- Produces: `SCENARIO_LABELS: dict[str, str]`
- Produces: `SELECTION_RULES: dict[str, str]`
- Produces: `make_historical_scenario_config(scenario: str) -> dict`
- Consumes: `default_config()` and existing `select_representative()` from `estonia_landuse.scenarios`

- [ ] **Step 1: Add a failing Notebook 10 preservation test**

```python
def test_notebook_10_reference_hash_is_unchanged():
    digest = hashlib.sha256(NOTEBOOK_10.read_bytes()).hexdigest().upper()
    assert digest == "89DD52DC8376F330728AB3A186423FFAF5B04AE15A14FD91CED1E45C21EF9D45"
```

- [ ] **Step 2: Add failing configuration-equivalence tests**

Load Notebook 10 as JSON, execute only its scenario-definition cell in a namespace containing `default_config`, and compare every scenario configuration with `make_historical_scenario_config()`. Assert equality for all six scenarios and explicitly assert:

```python
assert configs["wetland_priority"]["optimization"]["fourth_objective"] == "wetland_gain_pct"
assert configs["sustainable_agriculture"]["optimization"]["fourth_objective"] == "agriculture_gain_pct"
assert configs["balanced"]["max_changed_pct"] == 0.20
```

- [ ] **Step 3: Run the new tests and verify the expected failure**

Run: `uv run --extra dev pytest tests/sensitivity/test_historical_model.py -q`

Expected: FAIL because `estonia_landuse.sensitivity.historical_model` does not exist.

- [ ] **Step 4: Implement the exact historical configuration adapter**

Copy the six scenario branches and labels from Notebook 10 into `historical_model.py`. Return a fresh `default_config()` for every call, set `carbon_model="learned"`, reject unknown scenario IDs, and expose the Notebook 10 selection-rule mapping.

- [ ] **Step 5: Run focused tests and Ruff**

Run: `uv run --extra dev pytest tests/sensitivity/test_historical_model.py -q`

Run: `uv run --extra dev ruff check src/estonia_landuse/sensitivity tests/sensitivity/test_historical_model.py`

Expected: all pass and Notebook 10 remains unchanged.

- [ ] **Step 6: Commit the contract adapter**

```bash
git add src/estonia_landuse/sensitivity tests/sensitivity/test_historical_model.py docs/superpowers/specs/2026-08-04-legacy-optimizer-sensitivity-design.md
git commit -m "Add historical scenario sensitivity contract"
```

### Task 2: Add profiles, designs, and exact run accounting

**Files:**
- Create: `src/estonia_landuse/sensitivity/config.py`
- Create: `src/estonia_landuse/sensitivity/sampling.py`
- Create: `tests/sensitivity/test_sampling.py`

**Interfaces:**
- Produces: `ExperimentProfile(pop_size, n_generations, hidden_size, use_seeds)`
- Produces: `resolve_profile(name: str) -> ExperimentProfile`
- Produces: `build_baseline_manifest()`, `build_oat_manifest()`, `build_global_manifest()`, `build_interaction_manifest()`, `build_biodiversity_manifest()` returning `pd.DataFrame`
- Consumes: historical dotted configuration paths and explicit seeds

- [ ] **Step 1: Write failing profile and manifest tests**

Assert exact profiles:

```python
assert resolve_profile("test") == ExperimentProfile(8, 2, 4, False)
assert resolve_profile("screen") == ExperimentProfile(80, 60, 16, True)
assert resolve_profile("full") == ExperimentProfile(200, 200, 16, True)
```

Assert seed 42 is present in reproduction-capable designs, manifests have unique `(experiment, sample_id, scenario, seed)` keys, OAT rows change one dotted path, global samples are reproducible for a sampler seed, and interaction rows contain exactly two overrides.

- [ ] **Step 2: Run tests and confirm missing-interface failures**

Run: `uv run --extra dev pytest tests/sensitivity/test_sampling.py -q`

Expected: FAIL because profile and sampling interfaces are absent.

- [ ] **Step 3: Implement immutable profiles and prespecified parameter designs**

Use the sensitivity parameter families already developed on `codex/update-readme-documentation`, but map values onto the historical scenario configuration schema. Define screen designs as strict subsets of full designs. Use `scipy.stats.qmc.LatinHypercube` for deterministic global samples.

- [ ] **Step 4: Add run-count helpers**

Implement `manifest_run_count(frame) -> int` and notebook-facing summaries that print optimizer-run totals before execution. Reject duplicate execution keys and unknown profiles.

- [ ] **Step 5: Verify tests and lint**

Run: `uv run --extra dev pytest tests/sensitivity/test_sampling.py -q`

Run: `uv run --extra dev ruff check src/estonia_landuse/sensitivity/config.py src/estonia_landuse/sensitivity/sampling.py tests/sensitivity/test_sampling.py`

- [ ] **Step 6: Commit profiles and sampling**

```bash
git add src/estonia_landuse/sensitivity/config.py src/estonia_landuse/sensitivity/sampling.py tests/sensitivity/test_sampling.py
git commit -m "Add staged historical sensitivity designs"
```

### Task 3: Build the sequential historical artifact runner

**Files:**
- Create: `src/estonia_landuse/sensitivity/runner.py`
- Create: `tests/sensitivity/test_runner.py`
- Modify: `src/estonia_landuse/sensitivity/__init__.py`

**Interfaces:**
- Produces: `run_experiment_row(context, feature_columns, row, output_dir, profile, overwrite=False) -> RunArtifacts`
- Produces: `run_manifest(..., n_workers=1, progress=None) -> pd.DataFrame`
- Produces: one Parquet metric row and one NPZ target artifact per execution key
- Consumes: `make_historical_scenario_config()`, historical `train(seed=...)`, `select_representative()`, and `realize_targets()`

- [ ] **Step 1: Write a failing single-run integration test**

Use a small real context fixture and a `test` profile. Assert the runner calls the historical trainer with `seed`, produces scenario-specific metrics including `constraint_penalty`, and selects the same policy as `select_representative(front, rule)`.

- [ ] **Step 2: Write failing artifact identity and resume tests**

Assert paths contain experiment/sample/scenario/seed, stored metadata includes configuration and input fingerprints, a matching run is skipped, a changed configuration is recomputed, and incomplete artifact pairs are never reused.

- [ ] **Step 3: Run tests and verify missing-runner failures**

Run: `uv run --extra dev pytest tests/sensitivity/test_runner.py -q`

- [ ] **Step 4: Implement normalized feature preparation and front reporting**

Evaluate rank-zero policies with historical `summarize_policy()`. Keep historical metric names in raw front data and map them to stable artifact columns (`agriculture_loss`, `agriculture_gain`, `gross_agriculture_loss`, `gross_agriculture_gain`, `wetland_gain`) only at the serialization boundary.

- [ ] **Step 5: Implement atomic artifacts and parent-owned manifests**

Write temporary files beside final paths and replace them atomically. Persist a cohort-specific manifest plus a convenient experiment alias. Mark rows `pending`, `running`, `completed`, `skipped`, or `failed`, with timestamps and error details.

- [ ] **Step 6: Verify focused and existing scientific tests**

Run: `uv run --extra dev pytest tests/sensitivity/test_runner.py tests/test_scenarios.py tests/optimizer -q`

Run: `uv run --extra dev ruff check src/estonia_landuse/sensitivity/runner.py tests/sensitivity/test_runner.py`

- [ ] **Step 7: Commit the sequential runner**

```bash
git add src/estonia_landuse/sensitivity tests/sensitivity/test_runner.py
git commit -m "Add historical sensitivity artifact runner"
```

### Task 4: Add safe parallel execution and measurable speedup

**Files:**
- Modify: `src/estonia_landuse/sensitivity/runner.py`
- Create: `src/estonia_landuse/sensitivity/benchmark.py`
- Create: `tests/sensitivity/test_parallel_runner.py`
- Create: `tests/sensitivity/test_benchmark.py`

**Interfaces:**
- Extends: `run_manifest(..., n_workers: int)`
- Produces: `benchmark_manifest(context, feature_columns, manifest, profile) -> pd.DataFrame`
- Guarantees: identical terminal artifacts for `n_workers=1` and `n_workers>1`

- [ ] **Step 1: Write failing sequential/parallel equivalence tests**

Run a deterministic tiny manifest both ways and compare metric columns, selected targets, input order, statuses, and progress callback counts. Assert only the parent PID writes manifests and duplicate artifact identities fail before any writes.

- [ ] **Step 2: Write failing recovery tests**

Cover worker exceptions, process-pool startup failure, stale `running` rows, Windows path aliases, symlink/junction escapes, and a locked manifest alias. A worker failure must become a row-level failure without corrupting completed rows.

- [ ] **Step 3: Run tests and verify failure with unsupported `n_workers`**

Run: `uv run --extra dev pytest tests/sensitivity/test_parallel_runner.py -q`

- [ ] **Step 4: Implement a Windows-safe process pool**

Transfer immutable context once through a worker initializer. Submit one manifest row per future. Reconcile results and update manifests only in the parent. Keep `n_workers=1` as a deterministic compatibility path.

- [ ] **Step 5: Add timing instrumentation without changing model semantics**

Record training, front evaluation, artifact writing, and total duration. `benchmark_manifest()` must report sequential and parallel wall time, optimizer CPU time, and speedup for the same manifest.

- [ ] **Step 6: Verify parallel tests and full scientific suite**

Run: `uv run --extra dev pytest tests/sensitivity/test_parallel_runner.py tests/sensitivity/test_benchmark.py tests/optimizer tests/simulator -q`

Run: `uv run --extra dev ruff check src/estonia_landuse/sensitivity tests/sensitivity`

- [ ] **Step 7: Commit parallel execution**

```bash
git add src/estonia_landuse/sensitivity tests/sensitivity
git commit -m "Parallelize historical sensitivity runs"
```

### Task 5: Add Notebook 10.1 and the seed-42 reproduction gate

**Files:**
- Create: `notebooks/10.1_fast_scenario_reproduction.ipynb`
- Create: `src/estonia_landuse/sensitivity/reproduction.py`
- Create: `tests/sensitivity/test_reproduction.py`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Produces: `compare_reference_summary(reference: pd.DataFrame, candidate: pd.DataFrame, *, rtol=1e-6, atol=1e-8) -> pd.DataFrame`
- Consumes: Notebook 10's saved `data/processed/learned_carbon/scenario_summary.parquet`
- Produces: seed-42 artifacts below `data/processed/legacy_sensitivity/`

- [ ] **Step 1: Write failing summary comparison tests**

Test exact matches, tolerated rounding, missing scenarios, changed selection rules, changed feasibility, and materially different metrics. The result must identify every mismatched field rather than stop at the first mismatch.

- [ ] **Step 2: Write failing Notebook 10.1 structural tests**

Assert the new notebook uses seed 42, imports the historical runner, exposes `SENSITIVITY_N_WORKERS`, writes only to the legacy sensitivity root, displays planned run count, and calls the reproduction comparison.

- [ ] **Step 3: Run focused tests and confirm failures**

Run: `uv run --extra dev pytest tests/sensitivity/test_reproduction.py tests/test_notebook_contracts.py -q`

- [ ] **Step 4: Implement comparison logic and Notebook 10.1**

Notebook sections: purpose and model identity; settings; input validation; six-row manifest preview; parallel execution with progress; reproduction table; benchmark table; artifact locations. It must not import or execute Notebook 10.

- [ ] **Step 5: Execute Notebook 10.1 with the `test` profile**

Run it through `jupyter nbconvert --execute` with `SENSITIVITY_PROFILE=test` and an isolated temporary output root. Expected: successful execution and visible progress. The full seed-42 reproduction gate remains explicitly pending until full-profile runs finish.

- [ ] **Step 6: Verify Notebook 10 remains byte-identical**

Run the preservation test and calculate its SHA-256 directly. Expected: `89DD52D...EF9D45`.

- [ ] **Step 7: Commit Notebook 10.1**

```bash
git add notebooks/10.1_fast_scenario_reproduction.ipynb src/estonia_landuse/sensitivity/reproduction.py tests
git commit -m "Add fast historical scenario reproduction notebook"
```

### Task 6: Add analysis helpers and Notebooks 11.1-11.4

**Files:**
- Create: `src/estonia_landuse/sensitivity/analysis.py`
- Create: `src/estonia_landuse/sensitivity/plots.py`
- Create: `notebooks/11.1_stochastic_baseline.ipynb`
- Create: `notebooks/11.2_one_at_a_time.ipynb`
- Create: `notebooks/11.3_global_sensitivity.ipynb`
- Create: `notebooks/11.4_parameter_interactions.ipynb`
- Create: `tests/sensitivity/test_analysis.py`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Produces: baseline uncertainty summaries, OAT effect-to-noise ratios, seed-averaged global importance, held-out model diagnostics, and interaction residuals
- Consumes: stable metric artifacts produced by Tasks 3-4

- [ ] **Step 1: Write failing statistical-analysis tests**

Use synthetic tables with known effects. Assert seed averaging happens before global importance, OAT ranges are calculated across parameter-value means, interaction residuals remove main effects, and insufficient samples raise explicit errors.

- [ ] **Step 2: Write failing notebook contract tests**

Each notebook must expose `PROFILE`, `N_WORKERS`, `OVERWRITE`, preview its exact run count, call the shared runner, and read/write only the legacy sensitivity root. Full-profile seed sets must include 42.

- [ ] **Step 3: Run tests and verify missing-analysis failures**

Run: `uv run --extra dev pytest tests/sensitivity/test_analysis.py tests/test_notebook_contracts.py -q`

- [ ] **Step 4: Implement analysis and plotting helpers**

Use empirical means, standard deviations, and 95% intervals for 11.1; response curves and effect/noise ratios for 11.2; seed-averaged Spearman and random-forest importance with held-out R-squared for 11.3; and main-effect-adjusted two-factor grids for 11.4.

- [ ] **Step 5: Create the four notebooks**

Adapt the established structure from `codex/update-readme-documentation`, replacing new-optimizer calls and generic representative selection with the historical runner. Every notebook must explain its question, planned run count, expected runtime class, resume behavior, and interpretation limits.

- [ ] **Step 6: Execute all four notebooks with isolated `test` outputs**

Use `jupyter nbconvert --execute` and `SENSITIVITY_PROFILE=test`. Expected: no exceptions, no writes to Notebook 10 output directories, and all planned test runs reach terminal status.

- [ ] **Step 7: Verify tests and commit**

Run: `uv run --extra dev pytest tests/sensitivity/test_analysis.py tests/test_notebook_contracts.py -q`

Run: `uv run --extra dev ruff check src/estonia_landuse/sensitivity tests/sensitivity`

```bash
git add src/estonia_landuse/sensitivity notebooks/11.1_stochastic_baseline.ipynb notebooks/11.2_one_at_a_time.ipynb notebooks/11.3_global_sensitivity.ipynb notebooks/11.4_parameter_interactions.ipynb tests
git commit -m "Add historical sensitivity experiment notebooks"
```

### Task 7: Add robustness synthesis and cross-notebook reuse

**Files:**
- Create: `src/estonia_landuse/sensitivity/robustness.py`
- Create: `notebooks/11.5_biodiversity_robustness.ipynb`
- Create: `tests/sensitivity/test_robustness.py`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Produces: `build_robustness_report(output_root, report_dir, profile) -> dict[str, Path]`
- Reuses: baseline, OAT, global, interaction, and biodiversity-assumption artifacts
- Produces: scenario rank stability, parameter importance, interactions, spatial robustness, and run-completeness reports

- [ ] **Step 1: Write failing artifact-reuse and completeness tests**

Assert 11.5 never schedules an execution key already available with matching identity, excludes incomplete scenario comparison groups, reports missing experiments explicitly, and cannot mix profiles or model fingerprints.

- [ ] **Step 2: Write failing rank and spatial robustness tests**

Use known synthetic rankings and target arrays. Assert first-place frequency, median rank, comparison count, modal action, action agreement, target mean, and target standard deviation.

- [ ] **Step 3: Run tests and confirm missing-module failures**

Run: `uv run --extra dev pytest tests/sensitivity/test_robustness.py -q`

- [ ] **Step 4: Implement robustness synthesis and Notebook 11.5**

The notebook must inventory artifacts first, schedule only missing biodiversity-assumption runs, display planned new-run count, execute through the shared runner, and write a report with stable, unstable, and unavailable conclusions.

- [ ] **Step 5: Execute Notebook 11.5 with isolated test artifacts**

Run once with a complete test artifact set and once with one experiment absent. Expected: successful report generation in both cases, with the second report flagging missing evidence.

- [ ] **Step 6: Verify and commit**

Run: `uv run --extra dev pytest tests/sensitivity/test_robustness.py tests/test_notebook_contracts.py -q`

```bash
git add src/estonia_landuse/sensitivity/robustness.py notebooks/11.5_biodiversity_robustness.ipynb tests
git commit -m "Add historical sensitivity robustness synthesis"
```

### Task 8: Verify the suite and document execution economics

**Files:**
- Create: `docs/legacy-sensitivity-guide.md`
- Modify: `README.md`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Documents: exact test/screen/full run counts, environment variables, output paths, resume steps, and interpretation boundaries
- Verifies: no changes to Notebook 10 or its plots

- [ ] **Step 1: Add failing documentation contract assertions**

Assert the guide names all six notebooks, all three profiles, `SENSITIVITY_N_WORKERS`, `SENSITIVITY_OVERWRITE`, the legacy output root, seed 42, and the rule that full-profile reproduction must pass before scientific interpretation.

- [ ] **Step 2: Run documentation tests and confirm failure**

Run: `uv run --extra dev pytest tests/test_notebook_contracts.py -q`

- [ ] **Step 3: Write the execution guide**

Include the recommended order `10.1 -> 11.1 -> 11.2 -> 11.3 -> 11.4 -> 11.5`, exact profile-specific optimizer-run counts calculated from manifests, conservative Windows worker guidance, resume instructions, and estimated runtime derived from benchmark artifacts rather than hard-coded guesses.

- [ ] **Step 4: Execute the full test-profile notebook chain**

Run all six new notebooks with isolated test outputs in dependency order. Expected: every notebook exits successfully and 11.5 recognizes earlier artifacts without retraining them.

- [ ] **Step 5: Run complete verification**

Run: `uv run --extra dev ruff check src tests`

Run: `uv run --extra dev pytest -q`

Run the Notebook 10 SHA test and verify the five plot hashes remain unchanged from commit `d5a52db`.

- [ ] **Step 6: Commit documentation and final verification contracts**

```bash
git add docs/legacy-sensitivity-guide.md README.md tests/test_notebook_contracts.py
git commit -m "Document historical sensitivity workflow"
```

- [ ] **Step 7: Push the completed branch**

```bash
git push origin codex/legacy-optimizer-sensitivity
```
