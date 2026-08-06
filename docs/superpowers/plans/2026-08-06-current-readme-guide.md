# Current README Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one concise, comprehensive, code-verified README explaining the current model, workflows, scenarios, outputs, and limitations without obsolete branch history.

**Architecture:** Use current `main` as the document base and current source, tests, and notebooks as authoritative. Build a claim inventory, rewrite `README.md` as one coherent guide, then verify terminology, paths, links, lint, and tests.

**Tech Stack:** Markdown, Python project metadata, Jupyter notebooks, pytest, Ruff, Git.

## Global Constraints

- Do not change model, simulator, notebook, or visualizer behavior.
- Do not include branch comparisons or development history in the README.
- Describe forest, wetland, agriculture, and grassland as continuous target fractions.
- Describe map actions as dominant increases, not mutually exclusive model decisions.
- Describe protection as a constraint rather than an output action.
- Document all six current scenarios and Notebooks 10.1 through 11.5.
- Retain scientific claims only when supported by current code or committed documentation.

---

### Task 1: Audit Current Documentation Claims

**Files:**
- Read: `README.md`
- Read: `pyproject.toml`
- Read: `.github/workflows/ci.yml`
- Read: `src/estonia_landuse/optimizer/prescriptor.py`
- Read: `src/estonia_landuse/optimizer/nsga2.py`
- Read: `src/estonia_landuse/scenarios.py`
- Read: `src/estonia_landuse/simulator/actions.py`
- Read: `src/estonia_landuse/simulator/targets.py`
- Read: `src/estonia_landuse/simulator/reporting.py`
- Read: `src/estonia_landuse/sensitivity/config.py`
- Read: `tests/test_notebook_contracts.py`
- Read: `visualizer/app.js`
- Read: `visualizer/scenario_results/README.md`

**Interfaces:**
- Consumes: current repository state at `main`.
- Produces: a verified claim inventory used to rewrite `README.md`.

- [ ] **Step 1: Record exact model and display terminology**

Confirm the four prescriptor outputs, five display outcomes, twelve directional transitions, fixed urban/water treatment, and dominant-increase map rule from the listed source files.

- [ ] **Step 2: Record exact optimization terminology**

Confirm objectives, feasibility ordering, hard target realization, penalties, and representative-selection behavior from optimizer, simulator, and scenario modules.

- [ ] **Step 3: Record current operational routes**

Confirm dependency extras, CI commands, notebook filenames and roles, download defaults, six scenario identifiers, sensitivity profiles, output roots, and visualizer entry points.

- [ ] **Step 4: Identify stale README claims**

Run:

```powershell
rg -n "Protect|Afforest|five|5 scenarios|action|constraint|penalty|Notebook 10|visualizer|sensitivity" README.md
```

Expected: every match is supported by the claim inventory or marked for replacement in Task 2.

---

### Task 2: Rewrite README as the Current Project Guide

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 claim inventory.
- Produces: one current public project guide with valid repository links.

- [ ] **Step 1: Replace the opening model explanation**

Explain the flow from cell features through the neural prescriptor, feasible target realization, simulator scoring, feasible-first NSGA-II, scenario-specific representative selection, and saved spatial outputs.

- [ ] **Step 2: Replace the Actions section**

Use these exact display outcomes: `No substantial change`, `Forest increase`, `Wetland increase`, `Agricultural-land increase`, and `Grassland increase`. State that each label is only the largest positive change, four changeable groups allow `4 × 3 = 12` directional transitions, and protected areas are handled through constraints.

- [ ] **Step 3: Consolidate optimization and scenario documentation**

Separate objectives, hard constraints, penalties, and selection rules. Document the six current scenarios by intent without copying an exhaustive configuration dump that could drift.

- [ ] **Step 4: Consolidate setup and notebook routes**

Document installation extras and offline checks. Present the operational path to Notebook 10 separately from optional Notebooks 03–05, historical reproduction Notebook 10.1, sensitivity Notebooks 11.1–11.5, and exploratory `nsga2.ipynb`.

- [ ] **Step 5: Consolidate outputs, models, and limitations**

Describe saved representative-policy outputs, current visualizers, data sources, the 500 m grid, carbon-model choices, sensitivity scope, stochastic seed effects, proxy metrics, and the dominant-action map limitation. Link focused docs instead of duplicating them.

- [ ] **Step 6: Remove duplicated and obsolete material**

Ensure each concept has one authoritative section. Remove obsolete five-scenario tables, fixed-action descriptions, outdated launch commands, repeated carbon explanations, and unsupported claims.

- [ ] **Step 7: Review the README as a new user**

Verify that a reader can answer what the model outputs, how constraints are applied, which notebooks are required, what scenarios do, where results are saved, what map colors mean, and what sensitivity establishes.

- [ ] **Step 8: Commit the rewritten guide**

```powershell
git add README.md
git commit -m "docs: consolidate current project guide"
```

---

### Task 3: Verify Documentation and Repository Integrity

**Files:**
- Verify: `README.md`
- Verify: repository source and tests

**Interfaces:**
- Consumes: rewritten `README.md` from Task 2.
- Produces: evidence that the guide is internally clean and the repository remains green.

- [ ] **Step 1: Scan for stale wording and merge artifacts**

```powershell
rg -n "<<<<<<<|=======|>>>>>>>|5 scenarios|five scenarios|Protect.*Conservation candidate|Afforest.*Plant forest" README.md
```

Expected: no matches.

- [ ] **Step 2: Verify local Markdown links**

Extract repository-relative Markdown targets from `README.md` and confirm each target exists. Ignore `http://` and `https://` URLs during this filesystem check.

- [ ] **Step 3: Verify current identifiers**

Cross-check README scenario names, notebook paths, dependency extras, commands, land-use groups, and output locations against authoritative source files.

- [ ] **Step 4: Run lint and tests**

```powershell
uv run --extra dev ruff check src tests
uv run --extra dev pytest -q
```

Expected: Ruff exits 0 and all tests pass.

- [ ] **Step 5: Inspect final diff and commit corrections**

```powershell
git diff --check main...HEAD
git diff --stat main...HEAD
git status --short
```

Expected: no whitespace errors, only the specification, plan, and intended README change are committed, and the worktree is clean.
