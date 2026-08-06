# Reliability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 500 m neuroevolution workflow constraint-safe, reproducible, input-validated, download-safe, and continuously tested without rerunning Rohemeeter.

**Architecture:** Keep the simulator's numeric constraint calculation, but make optimizer ranking constraint-aware through a small NSGA-II constraint API. Add validation and injected NumPy generators at package boundaries, use ID-keyed spatial aggregation, and isolate external-I/O safety in download helpers. Tests use synthetic frames and controlled fake HTTP responses; local processed data is read-only and Rohemeeter is never invoked.

**Tech Stack:** Python 3.10+, NumPy, Pandas, GeoPandas, Requests, aiohttp, pytest, Ruff, GitHub Actions.

## Global Constraints

- Work only on `codex/reliability-hardening-500m`, based on `origin/feature/500m-grid`.
- Do not run `src/carbon_dataset/09_fetch_rohemeeter.py` or any Rohemeeter notebook/download cell.
- Reuse the linked ignored `data/` directory only for optional read-only checks.
- Write a failing regression test and observe the expected failure before every production behavior change.
- Do not modify the user's original-checkout `notebooks/10_scenario_comparison.ipynb`.
- Do not require network access in unit tests or CI.

---

### Task 1: Test and Development Foundation

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `pytest` and `ruff` development dependencies, pytest source-path configuration, reusable `minimal_context` fixture.

- [ ] **Step 1: Add a minimal import smoke test**

Create `tests/conftest.py` with a `minimal_context()` fixture containing one row and all simulator-required percentage, suitability, protection, and opportunity-cost columns. Create `tests/test_imports.py` that imports `score_policy`, `train`, and `fast_non_dominated_sort`.

- [ ] **Step 2: Run the smoke test and record the environment failure**

Run: `uv run --extra dev pytest tests/test_imports.py -q`

Expected before configuration: failure because the `dev` extra and/or pytest configuration does not exist.

- [ ] **Step 3: Split dependency groups and configure tools**

Keep core numerical/dataframe dependencies in `[project].dependencies`. Define extras named `notebook`, `pipeline`, `ml`, `dev`, and `all`. Add pytest configuration with `pythonpath = ["src"]`, and Ruff configuration targeting Python 3.10 with checks `E4`, `E7`, `E9`, `F`, `I`, and `B`.

- [ ] **Step 4: Add offline CI**

Create `.github/workflows/ci.yml` for pushes and pull requests. Use Python 3.10 and 3.12, install `.[dev]`, run `ruff check src tests`, and run `pytest -q`. Do not execute notebooks or data-download scripts.

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv lock
uv run --extra dev pytest tests/test_imports.py -q
uv run --extra dev ruff check tests/test_imports.py tests/conftest.py
```

Expected: all commands exit 0.

Commit: `build: add offline test and lint foundation`

### Task 2: Feasible-First NSGA-II

**Files:**
- Modify: `src/estonia_landuse/optimizer/nsga2.py`
- Modify: `src/estonia_landuse/optimizer/trainer.py`
- Modify: `src/estonia_landuse/optimizer/prescriptor.py`
- Create: `tests/optimizer/test_nsga2_constraints.py`
- Create: `tests/optimizer/test_trainer_constraints.py`

**Interfaces:**
- Produces: `CONSTRAINT_TOLERANCE`, `constraint_dominates(a, b, violation_a, violation_b, tolerance=...)`, and `fast_non_dominated_sort(metrics_list, constraint_violations=None)`.
- Produces: `Prescriptor.constraint_violation: float | None`.

- [ ] **Step 1: Write failing dominance tests**

Cover: feasible beats infeasible despite worse objectives; lower violation wins between infeasible policies; two feasible policies use ordinary Pareto dominance; exact infeasible ties fall back to objectives; non-finite violation is infeasible.

- [ ] **Step 2: Verify RED**

Run: `uv run --extra dev pytest tests/optimizer/test_nsga2_constraints.py -q`

Expected: failures because constraint-aware APIs do not exist.

- [ ] **Step 3: Implement constraint-aware sorting**

Add a centralized `CONSTRAINT_TOLERANCE = 1e-12`. Extend non-dominated sorting to accept one violation per individual, validate matching lengths, and use feasible-first comparison. Preserve existing behavior when violations are omitted.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --extra dev pytest tests/optimizer/test_nsga2_constraints.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing trainer integration test**

Construct two controlled prescriptors/summaries so an infeasible candidate has stronger ecological metrics. Assert `_select` ranks the feasible candidate first and that evaluation stores aggregate constraint violation.

- [ ] **Step 6: Verify RED**

Run: `uv run --extra dev pytest tests/optimizer/test_trainer_constraints.py -q`

Expected: failure because trainer neither stores nor passes constraint violations.

- [ ] **Step 7: Integrate trainer and expose diagnostics**

Set `p.constraint_violation = summary["constraint_penalty"]` during evaluation. Pass violations into non-dominated sorting. Include feasibility/violation in verbose reporting without changing the four ordinary optimization objectives.

- [ ] **Step 8: Verify and commit**

Run: `uv run --extra dev pytest tests/optimizer/test_nsga2_constraints.py tests/optimizer/test_trainer_constraints.py -q`

Expected: all tests pass.

Commit: `fix: enforce feasible-first NSGA-II selection`

### Task 3: Spatial Aggregation by Identifier

**Files:**
- Modify: `src/estonia_landuse/data/load.py`
- Create: `tests/data/test_spatial_density.py`

**Interfaces:**
- Produces unchanged public signatures:
  - `compute_road_density(grid, roads) -> np.ndarray`
  - `compute_building_density(grid, buildings) -> np.ndarray`

- [ ] **Step 1: Write failing non-contiguous-ID tests**

Create two simple grid polygons with reordered IDs such as `"cell-b"` and `"cell-a"`. Verify returned arrays follow grid row order and contain the correct clipped road lengths/building counts. Include a filtered integer-ID case such as IDs `10` and `42`.

- [ ] **Step 2: Verify RED**

Run: `uv run --extra dev pytest tests/data/test_spatial_density.py -q`

Expected: current code fails when indexing NumPy arrays by string or out-of-range IDs.

- [ ] **Step 3: Implement ID-keyed aggregation**

Build result Series indexed by `cell_id`, aggregate intersections/counts by ID, then `reindex(grid["cell_id"], fill_value=0).to_numpy()`. Validate that `cell_id` exists and is unique.

- [ ] **Step 4: Verify and commit**

Run: `uv run --extra dev pytest tests/data/test_spatial_density.py -q`

Expected: all tests pass.

Commit: `fix: aggregate spatial density by cell identifier`

### Task 4: Input Validation and Deterministic Evolution

**Files:**
- Create: `src/estonia_landuse/validation.py`
- Modify: `src/estonia_landuse/simulator/simulator.py`
- Modify: `src/estonia_landuse/optimizer/prescriptor.py`
- Modify: `src/estonia_landuse/optimizer/seeds.py`
- Modify: `src/estonia_landuse/optimizer/trainer.py`
- Create: `tests/test_validation.py`
- Create: `tests/optimizer/test_reproducibility.py`
- Create: `tests/simulator/test_invariants.py`

**Interfaces:**
- Produces: `validate_context_columns(context, required)`, `validate_target_fractions(context, targets)`, and `resolve_rng(seed=None, rng=None) -> np.random.Generator`.
- Extends `train(..., seed: int | None = None, rng: np.random.Generator | None = None)`.
- Extends `Prescriptor(..., rng: np.random.Generator | None = None)`.

- [ ] **Step 1: Write failing validation tests**

Assert clear `ValueError` messages for missing columns, mismatched target row count, target shape other than `(n, 4)`, NaN/infinite features, negative targets, zero-sum target rows, `pop_size < 2`, negative generation count, and simultaneous `seed` plus `rng`.

- [ ] **Step 2: Verify RED**

Run: `uv run --extra dev pytest tests/test_validation.py -q`

Expected: malformed inputs currently raise incidental errors or propagate NaNs.

- [ ] **Step 3: Implement shared boundary validation**

Centralize validation and call it before simulator scoring and optimizer normalization. Error text must identify the parameter or offending columns. Reject invalid hyperparameters before seed creation.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --extra dev pytest tests/test_validation.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing reproducibility tests**

Run a small synthetic population twice with the same seed and assert identical parameter arrays, ranks, crowding values, metrics, and constraint violations. Assert a different seed changes at least one parameter array.

- [ ] **Step 6: Verify RED**

Run: `uv run --extra dev pytest tests/optimizer/test_reproducibility.py -q`

Expected: same-seed API is absent or global RNG state changes results.

- [ ] **Step 7: Thread one generator through evolution**

Replace direct `np.random.*` calls in initialization, seed creation, crossover, mutation, and tournaments with the resolved `Generator`. Copies must not consume randomness merely to overwrite parameters.

- [ ] **Step 8: Add simulator invariants**

Write tests that no-change targets have approximately zero transition change/carbon for flat and NIR models, outputs are finite, and representative afforestation/rewetting transitions have expected carbon signs.

- [ ] **Step 9: Verify and commit**

Run:

```powershell
uv run --extra dev pytest tests/test_validation.py tests/optimizer/test_reproducibility.py tests/simulator/test_invariants.py -q
```

Expected: all tests pass.

Commit: `feat: validate inputs and support reproducible evolution`

### Task 5: Safe Cached Downloads and ZIP Extraction

**Files:**
- Modify: `src/estonia_landuse/data/download.py`
- Create: `tests/data/test_download.py`

**Interfaces:**
- Keeps: `download_file(url, filename, subdir="") -> Path`.
- Keeps: `unzip(path, dest_dir=None) -> Path`.
- Produces private path-validation helper used before extraction.

- [ ] **Step 1: Write failing archive-safety tests**

Create in-memory/local ZIP fixtures containing a safe file, `../escaped.txt`, and an absolute path. Assert safe extraction succeeds and unsafe archives raise `ValueError` without writing outside the destination.

- [ ] **Step 2: Write failing atomic-download tests**

Patch only the HTTP boundary with a controlled streaming response. Assert failure mid-stream leaves no final file, success atomically exposes the final file, and an existing non-empty cached file avoids HTTP.

- [ ] **Step 3: Verify RED**

Run: `uv run --extra dev pytest tests/data/test_download.py -q`

Expected: traversal and partial-final-file tests fail.

- [ ] **Step 4: Implement safe extraction and atomic replacement**

Validate every archive target using resolved paths. Stream downloads to a unique `.part` sibling, flush and close it, then use `Path.replace`. Remove the temporary file on any exception. Treat zero-byte cache files as incomplete.

- [ ] **Step 5: Verify and commit**

Run: `uv run --extra dev pytest tests/data/test_download.py -q`

Expected: all tests pass and no files escape pytest temporary directories.

Commit: `fix: harden cached downloads and archive extraction`

### Task 6: Reliable Forest Registry Ingestion

**Files:**
- Modify: `src/carbon_dataset/forest_registry_wfs.py`
- Modify: `src/carbon_dataset/forest_registry_details.py`
- Create: `tests/carbon_dataset/test_forest_registry_wfs.py`
- Create: `tests/carbon_dataset/test_forest_registry_details.py`

**Interfaces:**
- Produces module constants for request timeout and retry count.
- Extends internal WFS requests through a configured `requests.Session`.
- Keeps `fetch_details_parallel(...) -> pd.DataFrame`.

- [ ] **Step 1: Write failing WFS reliability tests**

Use a fake Session to verify explicit timeout use, retry after transient status, raising on permanent HTTP failure, and raising when pagination returns fewer features than `numberMatched`.

- [ ] **Step 2: Verify RED**

Run: `uv run --extra dev pytest tests/carbon_dataset/test_forest_registry_wfs.py -q`

Expected: timeout/session/completeness behaviors are absent.

- [ ] **Step 3: Implement bounded requests and completeness checks**

Use `HTTPAdapter` with bounded Retry rules for connection errors and statuses 429/500/502/503/504. Apply connect/read timeouts. Call `raise_for_status()`. Raise a descriptive `RuntimeError` unless downloaded feature count equals the advertised count.

- [ ] **Step 4: Write and verify the empty-input regression**

Add a test asserting `fetch_details_parallel([])` returns an empty DataFrame and does not call `asyncio.run`.

Run: `uv run --extra dev pytest tests/carbon_dataset/test_forest_registry_details.py -q`

Expected before implementation: division-by-zero failure.

- [ ] **Step 5: Implement empty-input return**

Return an empty DataFrame before logging percentages or entering the async runner.

- [ ] **Step 6: Verify and commit**

Run:

```powershell
uv run --extra dev pytest tests/carbon_dataset/test_forest_registry_wfs.py tests/carbon_dataset/test_forest_registry_details.py -q
```

Expected: all tests pass without network access.

Commit: `fix: make forest registry ingestion complete and bounded`

### Task 7: Extract Reusable Scenario Calculations

**Files:**
- Create: `src/estonia_landuse/scenarios.py`
- Modify only if cleanly applicable: `notebooks/10_scenario_comparison.ipynb`
- Create: `tests/test_scenarios.py`

**Interfaces:**
- Produces tested pure functions for scenario result tabulation and feasibility labeling used by notebook/reporting code.

- [ ] **Step 1: Identify duplicated pure calculations**

Inspect notebook 10 in the worktree and list calculations that duplicate aggregation or feasibility logic already implemented in package code. Do not execute notebook cells.

- [ ] **Step 2: Write failing pure-function tests**

Define the desired input/output with small dictionaries/DataFrames. Cover feasible labels, constraint violation display, and stable scenario table columns.

- [ ] **Step 3: Verify RED**

Run: `uv run --extra dev pytest tests/test_scenarios.py -q`

Expected: module/functions do not exist.

- [ ] **Step 4: Implement only reusable calculations**

Move pure logic into `scenarios.py`. Update notebook 10 only when the worktree copy can consume the function without regenerating outputs or conflicting with the user's original-checkout modification. Otherwise document the function and leave the notebook unchanged.

- [ ] **Step 5: Verify and commit**

Run: `uv run --extra dev pytest tests/test_scenarios.py -q`

Expected: all tests pass.

Commit: `refactor: expose tested scenario reporting helpers`

### Task 8: Documentation and Full Offline Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-27-reliability-hardening.md` only to check completed tasks.

**Interfaces:**
- Documents installation extras, seeded training, feasible-first results, local-data reuse, offline checks, and Rohemeeter avoidance.

- [ ] **Step 1: Update user documentation**

Add exact commands:

```powershell
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
```

Show `train(..., seed=42)`, explain `constraint_violation`, and state that existing Rohemeeter parquet/progress outputs should be reused because collection is expensive.

- [ ] **Step 2: Run formatting/static checks**

Run: `uv run --extra dev ruff check src tests`

Expected: exit 0.

- [ ] **Step 3: Run the complete test suite offline**

Run: `uv run --extra dev pytest -q`

Expected: exit 0 with zero failures and no external network access.

- [ ] **Step 4: Check package build and repository hygiene**

Run:

```powershell
uv build
git diff --check origin/feature/500m-grid...HEAD
git status --short
```

Expected: build exits 0, diff check emits no errors, and status contains only intentional files.

- [ ] **Step 5: Confirm protected local state**

Verify the original checkout still reports its pre-existing modification to `notebooks/10_scenario_comparison.ipynb`, the worktree `data/` path remains a junction to the original ignored data, and no Rohemeeter process is running or recorded in command history for this implementation.

- [ ] **Step 6: Commit documentation**

Commit: `docs: document reliable offline workflow`

- [ ] **Step 7: Final requirement audit**

Compare the branch diff against every acceptance criterion in
`docs/superpowers/specs/2026-07-27-reliability-hardening-design.md`. Report any
unmet criterion rather than claiming completion.
