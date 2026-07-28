# Sustainable Agriculture Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sixth policy scenario that produces 5–10% net agriculture expansion while bounding farmland relocation, changed land, biodiversity loss, and carbon loss.

**Architecture:** Extend `summarize_policy` with reusable hard-policy shortfalls, extend the configurable NSGA-II fourth objective with agriculture gain, and add a normalized sustainable-agriculture representative rule. Notebook 10 supplies scenario-specific limits and automatically carries the sixth representative through tables, plots, and GeoPackages.

**Tech Stack:** Python 3.11, NumPy, pandas, pytest, Ruff, Jupyter notebook JSON.

## Global Constraints

- Net agriculture gain is 5–10%, inclusive.
- Gross agriculture loss is no more than 2%.
- Changed land is no more than 15%.
- Biodiversity and carbon gain are each at least -1%.
- Existing wetland cannot decrease and protected cells cannot change.
- Existing local data is reused; no downloads or experiment runs.
- Notebook 10 output cells remain in the working copy but are not committed.

---

### Task 1: Policy constraints

**Files:**
- Modify: `src/estonia_landuse/simulator/config.py`
- Modify: `src/estonia_landuse/simulator/simulator.py`
- Test: `tests/simulator/test_policy_limits.py`

**Interfaces:**
- Consumes: existing aggregate policy metrics from `summarize_policy`.
- Produces: `constraint_penalty` shortfalls for `min_total_agri_gain_pct`, `max_gross_agri_loss_pct`, `min_biodiversity_gain`, and `min_carbon_gain`.

- [ ] **Step 1: Write failing tests**

Add tests that compute an unrestricted baseline and assert:

```python
minimum_gain = summarize_policy(
    minimal_context,
    proposal,
    {**base, "min_total_agri_gain_pct": baseline["agriculture_gain_pct"] + 0.05},
)
assert minimum_gain["constraint_penalty"] == pytest.approx(0.05)
```

Add equivalent exact-boundary coverage, gross-loss excess coverage, and
biodiversity/carbon floor coverage.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py -q
```

Expected: new shortfall assertions fail because the keys are ignored.

- [ ] **Step 3: Implement minimal constraints**

Add nonbinding defaults:

```python
"min_total_agri_gain_pct": 0.0,
"max_gross_agri_loss_pct": 1.0,
"min_biodiversity_gain": -1.0,
"min_carbon_gain": -1.0,
```

Compute:

```python
agriculture_gain_shortfall = max(
    0.0, config.get("min_total_agri_gain_pct", 0.0) - agriculture_gain_pct
)
gross_agriculture_loss_excess = max(
    0.0,
    gross_agriculture_loss_pct - config.get("max_gross_agri_loss_pct", 1.0),
)
biodiversity_shortfall = max(
    0.0,
    config.get("min_biodiversity_gain", -1.0) - biodiversity_gain,
)
carbon_shortfall = max(
    0.0, config.get("min_carbon_gain", -1.0) - carbon_gain
)
```

Add all four values once to `constraint_penalty`.

- [ ] **Step 4: Verify GREEN**

Run the simulator policy-limit tests and Ruff for the changed files.

- [ ] **Step 5: Commit**

```powershell
git add src/estonia_landuse/simulator/config.py src/estonia_landuse/simulator/simulator.py tests/simulator/test_policy_limits.py
git commit -m "feat: constrain sustainable agriculture expansion"
```

### Task 2: Agriculture objective and truthful progress output

**Files:**
- Modify: `src/estonia_landuse/optimizer/trainer.py`
- Modify: `tests/optimizer/test_objectives.py`

**Interfaces:**
- Produces: supported fourth objective `"agriculture_gain_pct"`.
- Produces: `_fourth_progress(metrics, config) -> tuple[str, float]`.

- [ ] **Step 1: Write failing tests**

Add:

```python
def test_agriculture_fourth_objective_maximizes_gain() -> None:
    config = {"optimization": {"fourth_objective": "agriculture_gain_pct"}}
    assert _objective_metrics(SUMMARY, config) == (-0.4, -0.3, 0.2, -0.6)


@pytest.mark.parametrize(
    ("objective", "metric", "expected"),
    [
        ("changed_pct", 0.1, ("change", 0.1)),
        ("wetland_gain_pct", -0.5, ("wetland_gain", 0.5)),
        ("agriculture_gain_pct", -0.6, ("agriculture_gain", 0.6)),
    ],
)
def test_fourth_progress_uses_public_label_and_sign(
    objective: str, metric: float, expected: tuple[str, float]
) -> None:
    assert _fourth_progress(
        np.array([0.0, 0.0, 0.0, metric]),
        {"optimization": {"fourth_objective": objective}},
    ) == expected
```

- [ ] **Step 2: Verify RED**

Run `tests/optimizer/test_objectives.py`; expect unsupported-objective/import
failures.

- [ ] **Step 3: Implement minimal objective and formatter**

Add agriculture gain to `FOURTH_OBJECTIVES`, negate both gain objectives for
NSGA-II, and use `_fourth_progress` in the generation log instead of the
hard-coded `change` label.

- [ ] **Step 4: Verify GREEN**

Run optimizer objective tests and Ruff.

- [ ] **Step 5: Commit**

```powershell
git add src/estonia_landuse/optimizer/trainer.py tests/optimizer/test_objectives.py
git commit -m "feat: optimize agriculture expansion"
```

### Task 3: Sustainable representative

**Files:**
- Modify: `src/estonia_landuse/scenarios.py`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- Produces: selection rule `"sustainable_agriculture"`.
- Consumes: biodiversity, carbon, cost, and net agriculture gain metrics.

- [ ] **Step 1: Write a failing representative test**

Construct feasible policies representing an agriculture-only extreme, an
ecological-only extreme, and a balanced policy. Assert the balanced policy is
selected by `"sustainable_agriculture"`.

- [ ] **Step 2: Verify RED**

Run the new test; expect `unsupported selection rule`.

- [ ] **Step 3: Implement the normalized knee**

Normalize `agriculture_gain_pct` as a maximized metric and score:

```python
np.sqrt(bio**2 + carbon**2 + cost**2 + agriculture_gain**2)
```

Retain existing feasible-only selection and deterministic tie-breaking.

- [ ] **Step 4: Verify GREEN**

Run `tests/test_scenarios.py` and Ruff.

- [ ] **Step 5: Commit**

```powershell
git add src/estonia_landuse/scenarios.py tests/test_scenarios.py
git commit -m "feat: select sustainable agriculture representative"
```

### Task 4: Notebook 10 policy

**Files:**
- Modify: `notebooks/10_scenario_comparison.ipynb`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Produces scenario key `sustainable_agriculture`, label
  `Sustainable Agriculture Expansion`, and selection rule
  `sustainable_agriculture`.

- [ ] **Step 1: Write failing notebook-contract assertions**

Assert the notebook source contains the new scenario branch and exact values:

```python
assert 'config["min_total_agri_gain_pct"] = 0.05' in source
assert 'config["max_total_agri_gain_pct"] = 0.10' in source
assert 'config["max_gross_agri_loss_pct"] = 0.02' in source
assert 'config["min_biodiversity_gain"] = -0.01' in source
assert 'config["min_carbon_gain"] = -0.01' in source
assert '"agriculture_gain_pct"' in source
assert '"sustainable_agriculture"' in source
```

- [ ] **Step 2: Verify RED**

Run the notebook contract test; expect the new source assertions to fail.

- [ ] **Step 3: Update notebook source**

Add the sixth scenario configuration and selection rule. Change the wetland
map's unused-axis handling to:

```python
if len(results) < len(axes_flat):
    axes_flat[-1].set_visible(False)
```

Compile every code cell. Do not execute the notebook.

- [ ] **Step 4: Verify source while preserving outputs**

Confirm the working notebook still has its existing output cells. Build an
output-cleared temporary JSON copy and stage only that blob, so committed
sources change while the user's working outputs remain.

- [ ] **Step 5: Verify GREEN and commit**

Run notebook contracts and commit:

```powershell
git commit -m "feat: add sustainable agriculture scenario"
```

### Task 5: Documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `docs/scenario-comparison.md`

- [ ] **Step 1: Document the sixth scenario**

Add its expansion band, gross-loss cap, ecological floors, fourth objective,
representative rule, output map, and acceptance checks. Change references
from five scenarios to six.

- [ ] **Step 2: Run full automated verification**

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Do not run Notebook 10 or download data.

- [ ] **Step 3: Commit documentation**

```powershell
git add README.md docs/scenario-comparison.md
git commit -m "docs: explain sustainable agriculture scenario"
```

- [ ] **Step 4: Verify handoff state**

Confirm Notebook 10 source matches `HEAD`, its execution outputs remain in the
working copy, no data files changed, and the branch remains unmerged.
