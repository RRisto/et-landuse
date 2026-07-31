# Scenario Results Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static Estonian visualizer for saved Notebook 10 scenario maps and results.

**Architecture:** Export GeoPackage maps and result summaries to GeoJSON and JSON. Load summary data initially and only the selected scenario GeoJSON on demand in the Leaflet application.

**Tech Stack:** Python, GeoPandas, pandas, static HTML/CSS/JavaScript, Leaflet.

## Global Constraints

- Use saved Notebook 10 results, never random action assignment.
- Keep all files static and load one selected scenario map at a time.
- Use Estonian labels and explain map colours are not probabilities.

---

### Task 1: Export static scenario data

**Files:** Modify `visualizer/export_geojson.py`; create `visualizer/scenario_maps/*.geojson` and `visualizer/scenario_summary.json`; test `tests/visualizer/test_export_geojson.py`.

- [ ] Write a failing test asserting `export_scenario_results(...)` writes `balanced.geojson` and `scenario_summary.json`.
- [ ] Run `uv run --with pytest pytest tests/visualizer/test_export_geojson.py -q`; expect failure because exporter does not exist.
- [ ] Implement exporter: read every `scenario_maps/*.gpkg`, reproject to WGS84, write same-stem GeoJSON; read saved summary parquet and write JSON records.
- [ ] Re-run focused test and commit exporter, test, and generated static data.

### Task 2: Show selected saved map

**Files:** Modify `visualizer/index.html`, `visualizer/app.js`; test `tests/visualizer/test_visualizer_static.py`.

- [ ] Write a failing test asserting `app.js` fetches `scenario_maps/${scenario}.geojson` and has no `Math.random` action assignment.
- [ ] Run focused test; expect failure because the app currently uses synthetic slider actions.
- [ ] Replace sliders with Estonian scenario tabs and implement `loadScenarioMap(scenario)` to fetch and render one saved GeoJSON. Use saved `action` values and add the non-probability map explanation.
- [ ] Re-run focused test and commit the static application changes.

### Task 3: Retain scenario comparison

**Files:** Modify `visualizer/index.html`, `visualizer/app.js`; extend `tests/visualizer/test_visualizer_static.py`.

- [ ] Write a failing test asserting the app loads `scenario_summary.json` and calls `renderScenarioComparison`.
- [ ] Run focused test; expect failure because no summary comparison exists.
- [ ] Fetch summary JSON and render an Estonian comparison table of biodiversity, carbon, cost, changed land, agricultural loss/gain, gross agricultural gain, and wetland gain. Highlight the selected scenario.
- [ ] Re-run focused tests, validate static files, and commit.

## Plan Self-Review

- Task 1 creates GitHub Pages-compatible inputs.
- Task 2 replaces synthetic maps with saved scenario output.
- Task 3 preserves comparison across all scenarios.
