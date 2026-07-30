# Pareto Reporting Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save the eight bar-chart reporting metrics for every scenario's Pareto policy so they can be shown as box plots later.

**Architecture:** Add a small reporting helper beside the simulator that realizes target land-use fractions and returns detailed aggregate metrics. Notebook 10 will call it while creating each rank-0 dataframe and persist the enriched dataframe. The optimisation objectives and `summarize_policy()` output contract remain unchanged.

**Tech Stack:** Python 3.10+, NumPy, pandas, pytest, Jupyter notebook.

## Global Constraints

- Preserve NSGA-II objective calculations and the `summarize_policy()` return contract.
- Apply the same target-realisation constraints as the scenario maps before calculating reporting deltas.
- Store snake-case metric columns and translate labels only during plotting.

---

## File Structure

- Create: `src/estonia_landuse/simulator/reporting.py` — constrained target realization and reporting metrics.
- Create: `tests/simulator/test_reporting.py` — reporting helper tests using a synthetic context.
- Modify: `notebooks/10_scenario_comparison.ipynb` — save detailed statistics for every Pareto policy.

### Task 1: Create testable reporting metrics

**Files:**
- Create: `tests/simulator/test_reporting.py`
- Create: `src/estonia_landuse/simulator/reporting.py`

**Interfaces:**
- Produces: `summarize_policy_reporting(context: pd.DataFrame, target_fractions: np.ndarray, config: dict | None = None) -> dict[str, float]`.
- Returns: `biodiversity_gain`, `carbon_gain`, `cost`, `changed_pct`, `agriculture_loss`, `agriculture_gain`, `gross_agriculture_gain`, and `wetland_gain`.

- [ ] **Step 1: Write the failing test**

```python
def test_reporting_summary_includes_all_bar_chart_metrics():
    context = synthetic_context()
    targets = np.array([[0.3, 0.2, 0.3, 0.2], [0.2, 0.1, 0.4, 0.3]])

    result = summarize_policy_reporting(context, targets, default_config())

    assert set(result) >= {
        "biodiversity_gain", "carbon_gain", "cost", "changed_pct",
        "agriculture_loss", "agriculture_gain",
        "gross_agriculture_gain", "wetland_gain",
    }
    assert result["agriculture_loss"] >= 0
    assert result["gross_agriculture_gain"] >= 0
    assert result["wetland_gain"] >= 0
```

- [ ] **Step 2: Verify the test fails**

Run: `uv run --extra dev pytest tests/simulator/test_reporting.py -q`

Expected: FAIL because the reporting module and helper do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def summarize_policy_reporting(context, target_fractions, config=None):
    targets = realize_targets(context, target_fractions, config)
    current = context[["forest_pct", "wetland_pct", "agriculture_pct", "grassland_pct"]].to_numpy()
    delta = targets - current
    base = summarize_policy(context, target_fractions, config)
    current_agriculture = current[:, 2].sum()
    return {
        **base,
        "agriculture_loss": np.clip(-delta[:, 2], 0, None).sum() / current_agriculture,
        "agriculture_gain": max(0.0, delta[:, 2].sum()) / current_agriculture,
        "gross_agriculture_gain": np.clip(delta[:, 2], 0, None).sum() / current_agriculture,
        "wetland_gain": np.clip(delta[:, 1], 0, None).mean(),
    }
```

Implement `realize_targets` with the notebook's normalization, protected-area blocking, and no-wetland-loss rules.

- [ ] **Step 4: Verify the test passes**

Run: `uv run --extra dev pytest tests/simulator/test_reporting.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/estonia_landuse/simulator/reporting.py tests/simulator/test_reporting.py
git commit -m "Add Pareto reporting metrics helper"
```

### Task 2: Save enriched Pareto statistics

**Files:**
- Modify: `notebooks/10_scenario_comparison.ipynb`

**Interfaces:**
- Consumes: `summarize_policy_reporting`.
- Produces: every row in `pareto_dfs[name]` and `scenario_comparison.parquet` includes the eight reporting metrics.

- [ ] **Step 1: Add a failing notebook assertion**

```python
reporting_columns = {
    "biodiversity_gain", "carbon_gain", "cost", "changed_pct",
    "agriculture_loss", "agriculture_gain",
    "gross_agriculture_gain", "wetland_gain",
}
for scenario_name, pareto_df in pareto_dfs.items():
    assert reporting_columns.issubset(pareto_df.columns), scenario_name
```

- [ ] **Step 2: Verify the assertion fails**

Run the existing Pareto-evaluation cell.

Expected: assertion failure because the detailed reporting columns are absent.

- [ ] **Step 3: Integrate the helper**

```python
from estonia_landuse.simulator.reporting import summarize_policy_reporting

# inside get_pareto_df
s = summarize_policy_reporting(context, targets, config)
s["id"] = i
rows.append(s)
```

- [ ] **Step 4: Re-run and verify persistence**

Run simulation/evaluation and save cells, then:

```python
saved = pd.read_parquet(OUTPUT_DIR / "scenario_comparison.parquet")
assert reporting_columns.issubset(saved.columns)
```

Expected: assertion passes and all scenario rows contain the metrics.

- [ ] **Step 5: Commit Task 2**

```bash
git add notebooks/10_scenario_comparison.ipynb
git commit -m "Save detailed Pareto scenario metrics"
```

### Task 3: Regression verification

**Files:**
- Modify: none.

- [ ] **Step 1: Run focused reporting tests**

Run: `uv run --extra dev pytest tests/simulator/test_reporting.py -q`

Expected: PASS.

- [ ] **Step 2: Run the project test suite**

Run: `uv run --extra dev pytest -q`

Expected: PASS.

- [ ] **Step 3: Confirm output schema**

```python
assert reporting_columns.issubset(saved.columns)
assert saved.groupby("scenario").size().min() > 0
```

Expected: all saved scenarios retain at least one Pareto policy and all eight columns.

## Plan Self-Review

- Task 1 creates consistent, testable detailed metrics without changing optimisation behavior.
- Task 2 saves those metrics for every Pareto policy.
- Task 3 verifies the helper, full suite, and persisted schema.
