# Scenario Differentiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce scenario change and agriculture limits through feasible-first NSGA-II, optimize explicit wetland gain for Wetland Priority, and select one consistent scenario-specific representative for all reporting and maps.

**Architecture:** The simulator will calculate aggregate policy metrics and add hard-limit excess to constraint violation. The trainer will choose a validated fourth objective from configuration. Pure scenario helpers will own feasible representative selection and summary construction, while Notebook 10 will define scenario parameters and reuse selected population members across tables, plots, and saved maps.

**Tech Stack:** Python 3.12, NumPy, pandas, GeoPandas, pytest, Ruff, Jupyter nbconvert, existing NSGA-II implementation.

## Global Constraints

- Use the prepared compartment-first carbon predictions and existing local data only.
- Do not download Forest Registry, Rohemeeter, or other remote data.
- Preserve Notebook 10's current executed outputs in the working tree and stage source-only notebook changes.
- Do not run the full 200-population, 200-generation experiment until the deterministic smoke gate passes and the user approves.
- Keep protected-cell, wetland-preservation, suitability, land-mass, and non-negativity rules unchanged.
- Use hard maximum-change and county agriculture-loss constraints with the approved scenario thresholds.
- Wetland Priority replaces changed-land minimization with wetland-gain maximization; do not add a fifth objective.
- Write a failing test before each production behavior change.

---

## File Structure

- Modify `src/estonia_landuse/simulator/simulator.py`: aggregate agriculture/wetland metrics and hard policy-limit violation.
- Create `tests/simulator/test_policy_limits.py`: exact-limit and excess-limit contracts.
- Modify `src/estonia_landuse/optimizer/trainer.py`: validated configurable fourth objective.
- Create `tests/optimizer/test_objectives.py`: objective tuple and validation contracts.
- Modify `src/estonia_landuse/scenarios.py`: deterministic feasible representative selection and expanded summaries.
- Modify `tests/test_scenarios.py`: selection rules, fallback, ties, and summary consistency.
- Modify `notebooks/10_scenario_comparison.ipynb`: explicit scenario semantics and shared representative reuse.
- Modify `tests/test_notebook_contracts.py`: Notebook 10 source contracts and syntax gate.

### Task 1: Aggregate Metrics and Hard Policy Limits

**Files:**
- Modify: `src/estonia_landuse/simulator/simulator.py:211-243`
- Create: `tests/simulator/test_policy_limits.py`

**Interfaces:**
- Consumes: realized targets from `realize_targets(context, target_fractions, config)`.
- Produces: `summarize_policy(...)` keys `agriculture_loss_pct`, `wetland_gain_pct`, and aggregate excess included in `constraint_penalty`.

- [ ] **Step 1: Write failing aggregate metric tests**

Create `tests/simulator/test_policy_limits.py`:

```python
import numpy as np
import pytest

from estonia_landuse.simulator.simulator import summarize_policy


def test_summary_reports_county_agriculture_loss_and_wetland_gain(
    minimal_context,
) -> None:
    agriculture_conversion = np.array([[0.5, 0.1, 0.2, 0.1]])
    wetland_restoration = np.array([[0.3, 0.2, 0.3, 0.1]])

    agriculture = summarize_policy(
        minimal_context,
        agriculture_conversion,
        {"carbon_model": "flat", "max_changed_pct": 1.0,
         "max_total_agri_loss_pct": 1.0},
    )
    wetland = summarize_policy(
        minimal_context,
        wetland_restoration,
        {"carbon_model": "flat", "max_changed_pct": 1.0,
         "max_total_agri_loss_pct": 1.0},
    )

    assert agriculture["agriculture_loss_pct"] == pytest.approx(1.0 / 3.0)
    assert agriculture["wetland_gain_pct"] == pytest.approx(0.0)
    assert wetland["agriculture_loss_pct"] == pytest.approx(0.0)
    assert wetland["wetland_gain_pct"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run the aggregate metric test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py::test_summary_reports_county_agriculture_loss_and_wetland_gain -q
```

Expected: failure with missing `agriculture_loss_pct`.

- [ ] **Step 3: Compute aggregate metrics once in `summarize_policy`**

After `changed_pct` is calculated, realize the targets and compute:

```python
targets = realize_targets(context, target_fractions, config)

current_agri_total = context["agriculture_pct"].to_numpy(float).sum()
target_agri_total = targets[:, 2].sum()
agriculture_loss_pct = (
    max(0.0, current_agri_total - target_agri_total) / current_agri_total
    if current_agri_total > 0
    else 0.0
)

current_wetland_total = context["wetland_pct"].to_numpy(float).sum()
target_wetland_total = targets[:, 1].sum()
wetland_gain_pct = (
    max(0.0, target_wetland_total - current_wetland_total)
    / current_wetland_total
    if current_wetland_total > 0
    else 0.0
)
```

Reuse `agriculture_loss_pct` in the existing cost penalty instead of
recalculating agriculture totals.

Return both metrics in the summary dictionary.

- [ ] **Step 4: Run the aggregate metric test and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py::test_summary_reports_county_agriculture_loss_and_wetland_gain -q
```

Expected: `1 passed`.

- [ ] **Step 5: Write failing hard-limit tests**

Append:

```python
def test_policy_limit_excess_adds_to_constraint_penalty(
    minimal_context,
) -> None:
    proposal = np.array([[0.5, 0.1, 0.2, 0.1]])
    unrestricted = summarize_policy(
        minimal_context,
        proposal,
        {"carbon_model": "flat", "max_changed_pct": 1.0,
         "max_total_agri_loss_pct": 1.0},
    )
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {"carbon_model": "flat", "max_changed_pct": 0.05,
         "max_total_agri_loss_pct": 0.10},
    )

    expected = (
        unrestricted["changed_pct"] - 0.05
        + unrestricted["agriculture_loss_pct"] - 0.10
    )
    assert unrestricted["constraint_penalty"] == pytest.approx(0.0)
    assert restricted["constraint_penalty"] == pytest.approx(expected)


def test_policy_exactly_on_limits_remains_feasible(minimal_context) -> None:
    proposal = np.array([[0.5, 0.1, 0.2, 0.1]])
    baseline = summarize_policy(
        minimal_context,
        proposal,
        {"carbon_model": "flat", "max_changed_pct": 1.0,
         "max_total_agri_loss_pct": 1.0},
    )
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": baseline["changed_pct"],
            "max_total_agri_loss_pct": baseline["agriculture_loss_pct"],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)
```

- [ ] **Step 6: Run the hard-limit tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py -q
```

Expected: the metric test passes and the excess-limit test fails because
aggregate excess is not yet part of `constraint_penalty`.

- [ ] **Step 7: Add aggregate excess to constraint violation**

Replace the returned constraint value with:

```python
max_changed = config.get("max_changed_pct", 0.20)
max_total_agri_loss = config.get("max_total_agri_loss_pct", 0.20)
changed_excess = max(0.0, changed_pct - max_changed)
agriculture_excess = max(
    0.0, agriculture_loss_pct - max_total_agri_loss
)
constraint_penalty = (
    outcomes["constraint_penalty"].mean()
    + changed_excess
    + agriculture_excess
)
```

Return `constraint_penalty`, `agriculture_loss_pct`, and `wetland_gain_pct`.
Keep existing cost penalties for backward compatibility.

- [ ] **Step 8: Run simulator tests and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py tests/simulator/test_invariants.py -q
.\.venv\Scripts\python.exe -m ruff check src/estonia_landuse/simulator/simulator.py tests/simulator
```

Expected: all tests and Ruff pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add src/estonia_landuse/simulator/simulator.py tests/simulator/test_policy_limits.py
git commit -m "feat: enforce aggregate policy limits"
```

### Task 2: Configurable Fourth Optimizer Objective

**Files:**
- Modify: `src/estonia_landuse/optimizer/trainer.py:10-124`
- Create: `tests/optimizer/test_objectives.py`

**Interfaces:**
- Consumes: `config["optimization"]["fourth_objective"]`, defaulting to `"changed_pct"`.
- Produces: `_objective_metrics(summary: dict, config: dict | None) -> tuple[float, float, float, float]`.

- [ ] **Step 1: Write failing objective tuple tests**

Create `tests/optimizer/test_objectives.py`:

```python
import pytest

from estonia_landuse.optimizer.trainer import _objective_metrics


SUMMARY = {
    "biodiversity_gain": 0.4,
    "carbon_gain": 0.3,
    "cost": 0.2,
    "changed_pct": 0.1,
    "wetland_gain_pct": 0.5,
}


def test_default_fourth_objective_minimizes_changed_land() -> None:
    assert _objective_metrics(SUMMARY, None) == (-0.4, -0.3, 0.2, 0.1)


def test_wetland_fourth_objective_maximizes_wetland_gain() -> None:
    config = {"optimization": {"fourth_objective": "wetland_gain_pct"}}
    assert _objective_metrics(SUMMARY, config) == (-0.4, -0.3, 0.2, -0.5)
```

- [ ] **Step 2: Run objective tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/optimizer/test_objectives.py -q
```

Expected: import failure because `_objective_metrics` does not exist.

- [ ] **Step 3: Implement objective selection**

Add:

```python
FOURTH_OBJECTIVES = {"changed_pct", "wetland_gain_pct"}


def _fourth_objective(config: dict | None) -> str:
    config = {} if config is None else config
    objective = config.get("optimization", {}).get(
        "fourth_objective", "changed_pct"
    )
    if objective not in FOURTH_OBJECTIVES:
        choices = ", ".join(sorted(FOURTH_OBJECTIVES))
        raise ValueError(
            f"unsupported fourth objective {objective!r}; choose from {choices}"
        )
    return objective


def _objective_metrics(
    summary: dict, config: dict | None
) -> tuple[float, float, float, float]:
    objective = _fourth_objective(config)
    fourth = summary[objective]
    if objective == "wetland_gain_pct":
        fourth = -fourth
    return (
        -summary["biodiversity_gain"],
        -summary["carbon_gain"],
        summary["cost"],
        fourth,
    )
```

Use `_objective_metrics(summary, config)` in `_evaluate_population`.
Call `_fourth_objective(config)` during `train` validation so unsupported
configuration fails before population initialization.

- [ ] **Step 4: Add unsupported-objective test**

Append:

```python
def test_unsupported_fourth_objective_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported fourth objective"):
        _objective_metrics(
            SUMMARY,
            {"optimization": {"fourth_objective": "forest_gain"}},
        )
```

- [ ] **Step 5: Run optimizer tests and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/optimizer -q
.\.venv\Scripts\python.exe -m ruff check src/estonia_landuse/optimizer tests/optimizer
```

Expected: all tests and Ruff pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/estonia_landuse/optimizer/trainer.py tests/optimizer/test_objectives.py
git commit -m "feat: configure fourth optimization objective"
```

### Task 3: Deterministic Scenario Representatives and Summary

**Files:**
- Modify: `src/estonia_landuse/scenarios.py`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: Pareto DataFrames with stable `id`, feasibility, aggregate metrics, and scenario names.
- Produces:
  - `select_representative(metrics: pd.DataFrame, rule: str, tolerance: float = CONSTRAINT_TOLERANCE) -> pd.Series`
  - `select_scenario_representatives(pareto_frames: Mapping[str, pd.DataFrame], selection_rules: Mapping[str, str], tolerance: float = CONSTRAINT_TOLERANCE) -> dict[str, pd.Series]`
  - expanded `build_scenario_summary(..., representatives=..., selection_rules=...) -> pd.DataFrame`.

- [ ] **Step 1: Replace old best-biodiversity test with failing rule tests**

Add fixtures and tests to `tests/test_scenarios.py`:

```python
import pytest

from estonia_landuse.scenarios import (
    annotate_feasibility,
    build_scenario_summary,
    select_representative,
    select_scenario_representatives,
)


def _metrics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": 10, "biodiversity_gain": 0.9, "carbon_gain": 0.2,
             "cost": 0.8, "changed_pct": 0.3, "agriculture_loss_pct": 0.1,
             "wetland_gain_pct": 0.1, "constraint_penalty": 0.0},
            {"id": 20, "biodiversity_gain": 0.5, "carbon_gain": 0.9,
             "cost": 0.4, "changed_pct": 0.2, "agriculture_loss_pct": 0.02,
             "wetland_gain_pct": 0.8, "constraint_penalty": 0.0},
            {"id": 30, "biodiversity_gain": 1.0, "carbon_gain": 1.0,
             "cost": 0.1, "changed_pct": 0.1, "agriculture_loss_pct": 0.5,
             "wetland_gain_pct": 1.0, "constraint_penalty": 0.2},
        ]
    )


@pytest.mark.parametrize(
    ("rule", "expected_id"),
    [
        ("green_maximum", 20),
        ("food_security", 10),
        ("wetland_priority", 20),
    ],
)
def test_representative_rules_use_only_feasible_rows(
    rule: str, expected_id: int
) -> None:
    assert select_representative(_metrics(), rule)["id"] == expected_id
```

The Green Maximum fixture deliberately creates equal normalized biodiversity
plus carbon scores for IDs 10 and 20; the lower tie-breaking cost selects ID
20. This prevents interpreting the raw gain sum instead of the specified
normalized sum.

- [ ] **Step 2: Run representative tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scenarios.py -q
```

Expected: import failure because representative helpers do not exist.

- [ ] **Step 3: Implement normalized loss and representative selection**

Add:

```python
SELECTION_RULES = {
    "green_maximum",
    "food_security",
    "low_budget",
    "wetland_priority",
    "balanced",
}


def _normalized_loss(values: pd.Series, *, maximize: bool) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    span = numeric.max() - numeric.min()
    if not np.isfinite(span) or span <= 0:
        return pd.Series(0.0, index=values.index)
    if maximize:
        return (numeric.max() - numeric) / span
    return (numeric - numeric.min()) / span


def select_representative(
    metrics: pd.DataFrame,
    rule: str,
    tolerance: float = CONSTRAINT_TOLERANCE,
) -> pd.Series:
    if rule not in SELECTION_RULES:
        raise ValueError(f"unsupported selection rule: {rule}")
    annotated = annotate_feasibility(metrics, tolerance=tolerance)
    candidates = annotated.loc[annotated["is_feasible"]].copy()
    if candidates.empty:
        minimum = annotated["constraint_penalty"].min()
        candidates = annotated.loc[
            annotated["constraint_penalty"] == minimum
        ].copy()

    bio = _normalized_loss(candidates["biodiversity_gain"], maximize=True)
    carbon = _normalized_loss(candidates["carbon_gain"], maximize=True)
    cost = _normalized_loss(candidates["cost"], maximize=False)
    changed = _normalized_loss(candidates["changed_pct"], maximize=False)
    wetland = _normalized_loss(candidates["wetland_gain_pct"], maximize=True)

    if rule == "green_maximum":
        score = bio + carbon
    elif rule == "food_security":
        score = bio
    elif rule == "low_budget":
        score = np.sqrt(bio**2 + carbon**2 + cost**2)
    elif rule == "wetland_priority":
        score = wetland
    else:
        score = np.sqrt(bio**2 + carbon**2 + cost**2 + changed**2)

    candidates["_selection_score"] = score
    ordered = candidates.sort_values(
        ["_selection_score", "cost", "changed_pct", "id"],
        ascending=True,
        kind="stable",
    )
    return ordered.iloc[0].drop(labels="_selection_score")
```

Implement `select_scenario_representatives` as a dictionary comprehension that
validates every scenario has a rule.

- [ ] **Step 4: Add knee, fallback, and deterministic tie tests**

Add tests with concrete frames:

```python
def test_low_budget_and_balanced_select_normalized_knees() -> None:
    frame = _metrics()
    assert select_representative(frame, "low_budget")["id"] == 20
    assert select_representative(frame, "balanced")["id"] == 20


def test_no_feasible_policy_uses_least_violation_then_rule() -> None:
    frame = _metrics()
    frame["constraint_penalty"] = [0.3, 0.1, 0.2]
    selected = select_representative(frame, "food_security")
    assert selected["id"] == 20
    assert selected["is_feasible"] == False


def test_ties_use_cost_then_change_then_id() -> None:
    frame = pd.DataFrame(
        [
            {"id": 2, "biodiversity_gain": 1.0, "carbon_gain": 1.0,
             "cost": 0.5, "changed_pct": 0.2, "agriculture_loss_pct": 0.0,
             "wetland_gain_pct": 0.0, "constraint_penalty": 0.0},
            {"id": 1, "biodiversity_gain": 1.0, "carbon_gain": 1.0,
             "cost": 0.5, "changed_pct": 0.2, "agriculture_loss_pct": 0.0,
             "wetland_gain_pct": 0.0, "constraint_penalty": 0.0},
        ]
    )
    assert select_representative(frame, "green_maximum")["id"] == 1
```

- [ ] **Step 5: Expand summary schema and consume preselected rows**

Change `SUMMARY_COLUMNS` to:

```python
SUMMARY_COLUMNS = [
    "Scenario",
    "Status",
    "Selection rule",
    "Policy ID",
    "Biodiversity gain",
    "Carbon gain",
    "Cost",
    "Changed land",
    "Agriculture loss",
    "Wetland gain",
    "Constraint violation",
    "Feasible solutions",
    "Front size",
    "Time (s)",
]
```

Extend `build_scenario_summary` with required keyword arguments:

```python
representatives: Mapping[str, pd.Series]
selection_rules: Mapping[str, str]
```

Use the supplied representative rather than selecting again. Derive status
from its `is_feasible` field and report all approved metrics. Update the
existing summary tests with exact expected dictionaries using the new column
names.

- [ ] **Step 6: Run scenario tests and lint**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scenarios.py -q
.\.venv\Scripts\python.exe -m ruff check src/estonia_landuse/scenarios.py tests/test_scenarios.py
```

Expected: all tests and Ruff pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/estonia_landuse/scenarios.py tests/test_scenarios.py
git commit -m "feat: select scenario-specific representatives"
```

### Task 4: Notebook 10 Shared Scenario Semantics

**Files:**
- Modify: `notebooks/10_scenario_comparison.ipynb`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Consumes: optimizer fourth-objective config and shared scenario representative/summary helpers.
- Produces: one `representatives` mapping and one `selected_policies` mapping reused for summaries, maps, and GeoPackages.

- [ ] **Step 1: Add failing Notebook 10 source contract**

Add:

```python
def test_scenario_notebook_uses_hard_limits_and_shared_representatives() -> None:
    source = _source("10_scenario_comparison.ipynb")
    assert (
        "from estonia_landuse.scenarios import "
        "build_scenario_summary, select_scenario_representatives"
    ) in source
    assert (
        'config["optimization"]["fourth_objective"] = '
        '"wetland_gain_pct"'
    ) in source
    assert 'config["max_total_agri_loss_pct"] = 0.15' in source
    assert "representatives = select_scenario_representatives(" in source
    assert "selected_policies[name]" in source
    assert 'pdf["biodiversity_gain"].idxmax()' not in source
```

- [ ] **Step 2: Run contract and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py::test_scenario_notebook_uses_hard_limits_and_shared_representatives -q
```

Expected: failure because Notebook 10 still duplicates maximum-biodiversity
selection.

- [ ] **Step 3: Update imports, scenario configs, and rules**

Import:

```python
from estonia_landuse.scenarios import (
    build_scenario_summary,
    select_scenario_representatives,
)
```

For every scenario, set both approved hard limits explicitly. For Wetland
Priority also set:

```python
config.setdefault("optimization", {})["fourth_objective"] = (
    "wetland_gain_pct"
)
```

Define:

```python
SELECTION_RULES = {
    "green_maximum": "green_maximum",
    "food_security": "food_security",
    "low_budget": "low_budget",
    "wetland_priority": "wetland_priority",
    "balanced": "balanced",
}
```

- [ ] **Step 4: Select policies once and build the shared summary**

After `pareto_dfs` is built:

```python
representatives = select_scenario_representatives(
    pareto_dfs,
    SELECTION_RULES,
)
selected_policies = {
    name: results[name]["pop"][int(row["id"])]
    for name, row in representatives.items()
}
summary = build_scenario_summary(
    pareto_dfs,
    representatives=representatives,
    selection_rules=SELECTION_RULES,
    scenario_labels=SCENARIOS,
    elapsed_seconds={
        name: data["time"] for name, data in results.items()
    },
)
print(summary.set_index("Scenario").to_string(float_format="{:.4f}".format))
```

Remove the manual `summary_rows` loop.

- [ ] **Step 5: Reuse `selected_policies` in every map/save block**

Replace every block that recomputes `best_idx`, `front0`, and `best_policy`
with:

```python
best_policy = selected_policies[name]
```

Rename comments and plot titles from "best biodiversity" to
"scenario representative".

Before concatenating Pareto frames for saving, add:

```python
pdf_copy["is_representative"] = (
    pdf_copy["id"] == int(representatives[name]["id"])
)
```

Save `summary` to `RESULTS_DIR / "scenario_summary.parquet"`.

- [ ] **Step 6: Separate data input and result output directories**

Replace the single directory constant with:

```python
DATA_DIR = Path("../data/processed/learned_carbon")
RESULTS_DIR = DATA_DIR
```

Read `features_with_forest.parquet` from `DATA_DIR`. Write comparison parquet,
summary parquet, and scenario maps under `RESULTS_DIR`. This permits the smoke
experiment to redirect outputs without copying or modifying input data.

- [ ] **Step 7: Run all notebook contracts and compile Notebook 10**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_contracts.py -q
.\.venv\Scripts\python.exe -c "import json,pathlib; n='10_scenario_comparison.ipynb'; nb=json.loads((pathlib.Path('notebooks')/n).read_text(encoding='utf-8')); [compile(''.join(c.get('source',[])),f'{n}:cell{i}','exec') for i,c in enumerate(nb['cells']) if c['cell_type']=='code']; print('Notebook 10 code cells compile')"
.\.venv\Scripts\python.exe -m ruff check tests/test_notebook_contracts.py
```

Expected: all contracts, compilation, and Ruff pass.

- [ ] **Step 8: Stage a source-only Notebook 10 and commit**

Use the established output-preserving flow:

```powershell
$cleanNotebook = Join-Path $env:TEMP "et-landuse-notebook10-scenarios-clean.ipynb"
Copy-Item -LiteralPath notebooks/10_scenario_comparison.ipynb -Destination $cleanNotebook -Force
uv run --extra notebook jupyter nbconvert --to notebook --ClearOutputPreprocessor.enabled=True --inplace $cleanNotebook
$blob = git hash-object -w $cleanNotebook
git update-index --add --cacheinfo "100644,$blob,notebooks/10_scenario_comparison.ipynb"
git add tests/test_notebook_contracts.py
git diff --cached --check
git commit -m "feat: differentiate policy scenarios"
```

Verify `git status --short` still lists the working Notebook 10 outputs.

### Task 5: Full Verification and Deterministic Smoke Gate

**Files:**
- Read: `notebooks/10_scenario_comparison.ipynb`
- Read: `data/processed/learned_carbon/features_with_forest.parquet`
- Generate outside repository: smoke notebook and result directory under the system temporary directory.

**Interfaces:**
- Consumes: complete scenario implementation and prepared local carbon data.
- Produces: smoke evidence for all acceptance checks without changing full-run results.

- [ ] **Step 1: Run full source verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Expected: Ruff and all tests pass; diff check is silent.

- [ ] **Step 2: Create a temporary smoke notebook mechanically**

Copy Notebook 10 to a temporary `.ipynb`, clear outputs, and replace only these
source assignments in the temporary JSON:

```python
POP_SIZE = 30
N_GENERATIONS = 20
RESULTS_DIR = Path(r"<temporary smoke result directory>")
```

Use `nbformat` through the project environment so the tracked notebook is not
rewritten. Assert exactly one replacement for each assignment before saving the
temporary notebook.

- [ ] **Step 3: Execute the temporary smoke notebook**

Execute the temporary notebook with `nbclient` and set its resource path to the
repository `notebooks` directory so relative input paths resolve:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import nbformat; from nbclient import NotebookClient; source=Path(r'<temporary-smoke-notebook>'); output=Path(r'<temporary-smoke-directory>')/'10_scenario_smoke.executed.ipynb'; nb=nbformat.read(source,as_version=4); NotebookClient(nb,timeout=1800,resources={'metadata':{'path':r'<repository-notebooks-directory>'}}).execute(); nbformat.write(nb,output)"
```

No network-enabled notebook is involved.

- [ ] **Step 4: Validate smoke summary and maps**

Read the temporary `scenario_summary.parquet`,
`scenario_comparison.parquet`, and five GeoPackages. Assert:

```python
assert len(summary) == 5
assert (summary["Status"] == "feasible").all()
assert summary.loc[food_security, "Agriculture loss"] <= 0.03 + 1e-12
assert summary.loc[low_budget, "Changed land"] <= 0.06 + 1e-12
assert (
    summary.loc[wetland_priority, "Wetland gain"]
    > summary.loc[balanced, "Wetland gain"]
)
assert comparison.groupby("scenario")["is_representative"].sum().eq(1).all()
assert at least_two_action_maps_differ
```

For each map, also assert protected cells have zero target delta and wetland
delta is non-negative, using the existing feature table and configured
protected threshold.

- [ ] **Step 5: Check status and report**

Run:

```powershell
git status --short
git status --short -- data/raw data/processed
```

Expected: Notebook 10 remains modified only by preserved old outputs; no raw or
processed data from the smoke run appears because all smoke outputs are under
the temporary directory.

Report feasibility counts, representative metrics, front sizes, action-map
differences, runtime, and whether all smoke acceptance checks passed. Do not
start the full experiment without the user's approval.
