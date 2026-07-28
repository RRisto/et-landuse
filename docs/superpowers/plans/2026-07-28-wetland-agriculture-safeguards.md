# Wetland Agriculture Safeguards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Wetland Priority from selecting agriculture-expansion extremes, report hidden gross agriculture changes, and visualize wetland gain directly.

**Architecture:** The simulator will calculate net and gross agriculture metrics once, price gross expansion, and enforce a configurable net-expansion limit. Scenario helpers will select Wetland Priority through a normalized biodiversity/carbon/cost/wetland knee and report the new metrics. Notebook 10 will configure the targeted safeguard, reuse the selected policy consistently, and add a shared-scale wetland-delta figure.

**Tech Stack:** Python 3.12, NumPy, pandas, GeoPandas, pytest, Ruff, Jupyter.

## Global Constraints

- Use existing local data only; do not download Forest Registry, Rohemeeter, or other remote data.
- Preserve the current output-bearing Notebook 10 working copy and commit source-only notebook changes.
- Do not run the full 200-population, 200-generation, five-scenario experiment.
- Wetland Priority alone uses `max_total_agri_gain_pct = 0.05` and `agriculture_gain_cost = 10.0`.
- Other scenarios retain `max_total_agri_gain_pct = 1.0` and `agriculture_gain_cost = 0.0`.
- Existing net agriculture loss semantics and physical invariants remain unchanged.
- Write and observe a failing test before every production behavior change.

---

## File Structure

- Modify `src/estonia_landuse/simulator/config.py`: backward-compatible expansion defaults.
- Modify `src/estonia_landuse/simulator/simulator.py`: net/gross agriculture metrics, expansion cost, and hard expansion excess.
- Modify `tests/simulator/test_policy_limits.py`: exact metric, cost, denominator, and constraint contracts.
- Modify `src/estonia_landuse/scenarios.py`: wetland ecological knee and expanded summary.
- Modify `tests/test_scenarios.py`: knee selection and summary schema.
- Modify `notebooks/10_scenario_comparison.ipynb`: Wetland safeguards and dedicated wetland-delta figure.
- Modify `tests/test_notebook_contracts.py`: Notebook 10 source and compilation contracts.
- Modify `README.md` and `docs/scenario-comparison.md`: revised scenario semantics and rerun guidance.

### Task 1: Agriculture Metrics, Cost, and Expansion Feasibility

**Files:**
- Modify: `src/estonia_landuse/simulator/config.py`
- Modify: `src/estonia_landuse/simulator/simulator.py:211-266`
- Modify: `tests/simulator/test_policy_limits.py`

**Interfaces:**
- Produces summary keys `agriculture_gain_pct`, `gross_agriculture_loss_pct`, and `gross_agriculture_gain_pct`.
- Consumes `config["max_total_agri_gain_pct"]` and `config["scoring"]["agriculture_gain_cost"]`.

- [ ] **Step 1: Write failing net/gross metric tests**

Append to `tests/simulator/test_policy_limits.py`:

```python
def test_summary_distinguishes_net_and_gross_agriculture_change(
    minimal_context: pd.DataFrame,
) -> None:
    context = pd.concat([minimal_context, minimal_context], ignore_index=True)
    proposal = np.array(
        [
            [0.5, 0.1, 0.2, 0.1],
            [0.2, 0.1, 0.5, 0.1],
        ]
    )

    result = summarize_policy(
        context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )

    assert result["agriculture_loss_pct"] == pytest.approx(0.0)
    assert result["agriculture_gain_pct"] == pytest.approx(1.0 / 6.0)
    assert result["gross_agriculture_loss_pct"] == pytest.approx(1.0 / 6.0)
    assert result["gross_agriculture_gain_pct"] == pytest.approx(1.0 / 3.0)


def test_zero_current_agriculture_has_zero_agriculture_percentages(
    minimal_context: pd.DataFrame,
) -> None:
    context = minimal_context.copy()
    context["forest_pct"] = 0.7
    context["agriculture_pct"] = 0.0
    proposal = np.array([[0.7, 0.1, 0.0, 0.1]])

    result = summarize_policy(
        context,
        proposal,
        {"carbon_model": "flat"},
    )

    assert result["agriculture_loss_pct"] == 0.0
    assert result["agriculture_gain_pct"] == 0.0
    assert result["gross_agriculture_loss_pct"] == 0.0
    assert result["gross_agriculture_gain_pct"] == 0.0
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/simulator/test_policy_limits.py -q
```

Expected: missing `agriculture_gain_pct`.

- [ ] **Step 3: Implement net and gross metrics**

In `summarize_policy`, calculate:

```python
agriculture_delta = targets[:, 2] - context["agriculture_pct"].to_numpy(float)
gross_agriculture_loss = np.clip(-agriculture_delta, 0.0, None).sum()
gross_agriculture_gain = np.clip(agriculture_delta, 0.0, None).sum()

if current_agri_total > 0:
    agriculture_loss_pct = max(0.0, -agriculture_delta.sum()) / current_agri_total
    agriculture_gain_pct = max(0.0, agriculture_delta.sum()) / current_agri_total
    gross_agriculture_loss_pct = gross_agriculture_loss / current_agri_total
    gross_agriculture_gain_pct = gross_agriculture_gain / current_agri_total
else:
    agriculture_loss_pct = 0.0
    agriculture_gain_pct = 0.0
    gross_agriculture_loss_pct = 0.0
    gross_agriculture_gain_pct = 0.0
```

Return all four percentages.

- [ ] **Step 4: Run metric tests and verify GREEN**

Run the simulator test file. Expected: metric tests pass.

- [ ] **Step 5: Write failing expansion-cost test**

```python
def test_gross_agriculture_gain_increases_cost(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    base = {
        "carbon_model": "flat",
        "max_changed_pct": 1.0,
        "max_total_agri_loss_pct": 1.0,
        "max_total_agri_gain_pct": 1.0,
    }
    free = summarize_policy(
        minimal_context,
        proposal,
        {**base, "scoring": {"agriculture_gain_cost": 0.0}},
    )
    priced = summarize_policy(
        minimal_context,
        proposal,
        {**base, "scoring": {"agriculture_gain_cost": 10.0}},
    )

    assert priced["cost"] - free["cost"] == pytest.approx(2.0)
```

The proposal adds `0.2` agriculture share in one cell; weight `10.0` adds
exactly `2.0`.

- [ ] **Step 6: Verify cost test RED, then implement**

In `score_policy`, after agriculture-loss cost:

```python
agriculture_gain = np.clip(delta[:, 2], 0, None)
agriculture_penalty += (
    sc.get("agriculture_gain_cost", 0.0) * agriculture_gain
)
```

Add `"agriculture_gain_cost": 0.0` to default scoring config.

- [ ] **Step 7: Write failing hard expansion-limit tests**

```python
def test_agriculture_expansion_excess_adds_to_constraint_penalty(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    unrestricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )
    restricted = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 0.05,
        },
    )

    assert restricted["constraint_penalty"] == pytest.approx(
        unrestricted["agriculture_gain_pct"] - 0.05
    )


def test_policy_exactly_on_agriculture_gain_limit_is_feasible(
    minimal_context: pd.DataFrame,
) -> None:
    proposal = np.array([[0.2, 0.1, 0.5, 0.1]])
    baseline = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": 1.0,
        },
    )
    exact = summarize_policy(
        minimal_context,
        proposal,
        {
            "carbon_model": "flat",
            "max_changed_pct": 1.0,
            "max_total_agri_loss_pct": 1.0,
            "max_total_agri_gain_pct": baseline["agriculture_gain_pct"],
        },
    )

    assert exact["constraint_penalty"] == pytest.approx(0.0, abs=1e-12)
```

- [ ] **Step 8: Verify RED, then enforce the cap**

Add default:

```python
"max_total_agri_gain_pct": 1.0,
```

Add to aggregate constraint penalty:

```python
max_total_agri_gain = config.get("max_total_agri_gain_pct", 1.0)
agriculture_gain_excess = max(
    0.0, agriculture_gain_pct - max_total_agri_gain
)
constraint_penalty += agriculture_gain_excess
```

- [ ] **Step 9: Verify and commit Task 1**

Run simulator tests, full Ruff on simulator files, and commit:

```powershell
git add src/estonia_landuse/simulator/config.py src/estonia_landuse/simulator/simulator.py tests/simulator/test_policy_limits.py
git commit -m "feat: constrain agriculture expansion"
```

### Task 2: Wetland Ecological Knee and Expanded Summary

**Files:**
- Modify: `src/estonia_landuse/scenarios.py`
- Modify: `tests/test_scenarios.py`

**Interfaces:**
- `select_representative(..., "wetland_priority")` uses normalized biodiversity, carbon, cost, and wetland losses.
- `build_scenario_summary` reports all net/gross agriculture metrics.

- [ ] **Step 1: Write failing Wetland knee test**

Add a frame with:

```python
def test_wetland_priority_selects_ecological_knee_not_absolute_extreme() -> None:
    frame = pd.DataFrame(
        [
            {"id": 1, "biodiversity_gain": -0.1, "carbon_gain": -0.1,
             "cost": 0.1, "changed_pct": 0.2,
             "agriculture_loss_pct": 0.0, "agriculture_gain_pct": 0.4,
             "gross_agriculture_loss_pct": 0.0,
             "gross_agriculture_gain_pct": 0.4,
             "wetland_gain_pct": 1.0, "constraint_penalty": 0.0},
            {"id": 2, "biodiversity_gain": 0.5, "carbon_gain": 0.5,
             "cost": 0.2, "changed_pct": 0.1,
             "agriculture_loss_pct": 0.1, "agriculture_gain_pct": 0.0,
             "gross_agriculture_loss_pct": 0.1,
             "gross_agriculture_gain_pct": 0.0,
             "wetland_gain_pct": 0.999, "constraint_penalty": 0.0},
            {"id": 3, "biodiversity_gain": 1.0, "carbon_gain": 1.0,
             "cost": 1.0, "changed_pct": 0.3,
             "agriculture_loss_pct": 0.1, "agriculture_gain_pct": 0.0,
             "gross_agriculture_loss_pct": 0.1,
             "gross_agriculture_gain_pct": 0.0,
             "wetland_gain_pct": 0.2, "constraint_penalty": 0.0},
        ]
    )

    assert select_representative(frame, "wetland_priority")["id"] == 2
```

Expected RED: current absolute wetland rule selects ID 1.

- [ ] **Step 2: Implement Wetland ecological knee**

Replace:

```python
elif rule == "wetland_priority":
    score = wetland
```

with:

```python
elif rule == "wetland_priority":
    score = np.sqrt(bio**2 + carbon**2 + cost**2 + wetland**2)
```

- [ ] **Step 3: Expand required metrics and summary schema**

Add required internal columns:

```python
"agriculture_gain_pct",
"gross_agriculture_loss_pct",
"gross_agriculture_gain_pct",
```

Add summary labels:

```python
"Agriculture gain",
"Gross agriculture loss",
"Gross agriculture gain",
```

Populate them from the representative row.

- [ ] **Step 4: Update existing fixtures and exact summary expectations**

Every scenario test row receives literal values for the three new fields.
The exact summary dictionary asserts the corresponding human-readable
columns.

- [ ] **Step 5: Run scenario tests and Ruff**

Expected: all scenario tests pass and Ruff is clean.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src/estonia_landuse/scenarios.py tests/test_scenarios.py
git commit -m "feat: select ecological wetland representative"
```

### Task 3: Notebook 10 Safeguards and Wetland Map

**Files:**
- Modify: `notebooks/10_scenario_comparison.ipynb`
- Modify: `tests/test_notebook_contracts.py`

**Interfaces:**
- Wetland config sets the approved expansion limit and cost.
- A new all-scenario figure maps selected-policy `delta_wetland`.

- [ ] **Step 1: Add failing Notebook 10 contract**

Extend the Notebook 10 test to require:

```python
assert 'config["max_total_agri_gain_pct"] = 0.05' in source
assert 'config["scoring"]["agriculture_gain_cost"] = 10.0' in source
assert 'map_df["wetland_gain"] = np.clip(delta[:, 1], 0, None)' in source
assert '"Wetland Gain per Scenario Representative"' in source
```

Expected RED: safeguard config and wetland figure are absent.

- [ ] **Step 2: Configure Wetland Priority**

In `make_scenario_config("wetland_priority")`, add:

```python
config["max_total_agri_gain_pct"] = 0.05
config["scoring"]["agriculture_gain_cost"] = 10.0
```

- [ ] **Step 3: Add dedicated wetland-gain figure**

After the change-intensity figure, add a code cell:

```python
selected_wetland_maps = {}
shared_wetland_max = 0.0
for name, data in results.items():
    best_policy = selected_policies[name]
    targets = best_policy.prescribe(feat_norm)
    current = np.column_stack(
        [features_df[f"{group}_pct"].values for group in groups]
    )
    targets_norm = realize_targets(
        features_df, targets, data["config"]
    )
    delta = targets_norm - current
    map_df = grid.copy()
    map_df["wetland_gain"] = np.clip(delta[:, 1], 0, None)
    selected_wetland_maps[name] = map_df
    shared_wetland_max = max(
        shared_wetland_max, float(map_df["wetland_gain"].max())
    )

fig, axes = plt.subplots(2, 3, figsize=(20, 12))
axes_flat = axes.flatten()
for idx, name in enumerate(results):
    ax = axes_flat[idx]
    selected_wetland_maps[name].plot(
        column="wetland_gain",
        ax=ax,
        cmap="Blues",
        vmin=0,
        vmax=shared_wetland_max,
        legend=(idx == 0),
    )
    ax.set_title(SCENARIOS[name], fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
axes_flat[5].set_visible(False)
plt.suptitle("Wetland Gain per Scenario Representative", fontsize=14)
plt.tight_layout()
plt.show()
```

- [ ] **Step 4: Compile and verify Notebook contracts**

Run all notebook tests and compile every Notebook 10 code cell.

- [ ] **Step 5: Commit source-only notebook changes**

Clear outputs only in a temporary copy, verify identical sources, stage its
blob with `git update-index`, stage the test, and commit:

```powershell
git commit -m "feat: safeguard wetland scenario"
```

Verify the working Notebook 10 remains modified and unstaged.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/scenario-comparison.md`

- [ ] **Step 1: Update documentation**

Document:

- Wetland Priority 5% maximum net agriculture expansion.
- Gross agriculture gain/loss reporting.
- Wetland ecological knee.
- Dedicated wetland-gain map.
- Need to rerun the full Notebook 10 experiment because evolution objectives
  now include the expansion cost.

- [ ] **Step 2: Run full verification**

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

- [ ] **Step 3: Run deterministic smoke experiment**

Create a temporary output-cleared Notebook 10 with `POP_SIZE = 30`,
`N_GENERATIONS = 20`, and `RESULTS_DIR` redirected to a temporary directory.
Execute from the repository `notebooks` working directory.

Validate:

```python
assert wetland_summary["Agriculture gain"] <= 0.05 + 1e-12
assert wetland_summary["Biodiversity gain"] >= 0
assert wetland_summary["Carbon gain"] >= 0
assert wetland_summary["Wetland gain"] > balanced_summary["Wetland gain"]
assert wetland_summary["Gross agriculture gain"] <= 0.15
assert wetland_agriculture_action_share < 0.20
```

Also verify protected deltas equal zero and wetland deltas are non-negative.

- [ ] **Step 4: Commit documentation**

```powershell
git add README.md docs/scenario-comparison.md
git commit -m "docs: explain wetland agriculture safeguards"
```

- [ ] **Step 5: Report handoff**

Report exact smoke metrics and instruct the user to restart the kernel and run
all Notebook 10 cells for the full 200×200×5 experiment. Do not merge, push,
or start the full run.
