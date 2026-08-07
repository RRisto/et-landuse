# README Notebooks 01–05 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accurate README table explaining every Notebook 01–05 entry and its place in the current workflow.

**Architecture:** Inspect notebook markdown, imports, paths, and outputs as the source of truth. Add one focused table to the existing Notebook routes section, then verify descriptions, links, wording, lint, and tests.

**Tech Stack:** Markdown, Jupyter notebook JSON, pytest, Ruff, Git.

## Global Constraints

- Modify only `README.md` during implementation.
- Do not change notebook or runtime behavior.
- Do not present Notebooks 03–05 as prerequisites for Notebook 10.
- Explicitly distinguish preparation, validation, legacy exploration, and optional experiments.
- Verify descriptions from notebook contents rather than filenames alone.

---

### Task 1: Audit Notebooks 01–05

**Files:**
- Read: `notebooks/01_collect_datasets.ipynb`
- Read: `notebooks/01.1_carbon_dataset.ipynb`
- Read: `notebooks/01.2_fetch_rohemeeter.ipynb`
- Read: `notebooks/01.3_validate_features_map.ipynb`
- Read: `notebooks/01.4_process_soil_map.ipynb`
- Read: `notebooks/02_simulator_and_baselines.ipynb`
- Read: `notebooks/03_neuroevolution.ipynb`
- Read: `notebooks/03.1_neuroevolution_carbon.ipynb`
- Read: `notebooks/03.2_neuroevolution_biodiversity.ipynb`
- Read: `notebooks/04_learned_carbon_predictor.ipynb`
- Read: `notebooks/05_compare_carbon_models.ipynb`

**Interfaces:**
- Produces: an evidence-backed purpose, principal output/role, and classification for each notebook.

- [ ] **Step 1: Inspect notebook introductions and section headings**

Record each notebook's stated purpose and whether it labels itself legacy or operational.

- [ ] **Step 2: Inspect imports, input paths, output paths, and download guards**

Record what each notebook consumes or produces and whether it performs guarded network access.

- [ ] **Step 3: Classify each notebook**

Assign one of: operational preparation, validation, legacy exploration, or optional experiment. Note any notebook that spans two roles.

---

### Task 2: Add the Early-Notebook Guide

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 audit.
- Produces: one linked table in the Notebook routes section.

- [ ] **Step 1: Add the table before the current six-scenario route**

Use columns `Notebook`, `Purpose and principal role`, and `Workflow status`. Include all eleven notebook files listed in Task 1 with repository-relative links.

- [ ] **Step 2: Add concise routing guidance**

State which notebooks are used when rebuilding inputs, which validate prepared data, which preserve legacy routes, and which are optional comparisons. Preserve the existing Notebook 10 prerequisite explanation.

- [ ] **Step 3: Remove the now-redundant generic 03–05 paragraph**

Avoid explaining the same notebooks twice while retaining the separate numbered routes for Notebook 10, sensitivity analysis, and NSGA-II learning.

- [ ] **Step 4: Commit**

```powershell
git add README.md
git commit -m "docs: explain notebooks 01 through 05"
```

---

### Task 3: Verify the README Update

**Files:**
- Verify: `README.md`

**Interfaces:**
- Consumes: Task 2 README.
- Produces: verified documentation and repository integrity evidence.

- [ ] **Step 1: Confirm all eleven notebook links exist**

Extract the table's repository-relative paths and verify them against the worktree.

- [ ] **Step 2: Check routing language**

Search for claims that make Notebooks 03–05 mandatory or omit legacy/validation classifications. Expected: none.

- [ ] **Step 3: Run repository checks**

```powershell
uv run --extra dev ruff check src tests
uv run --extra dev pytest -q
git diff --check main...HEAD
git status --short
```

Expected: Ruff passes, all tests pass, no whitespace errors, and only the design, plan, and README commits differ from `main`.
