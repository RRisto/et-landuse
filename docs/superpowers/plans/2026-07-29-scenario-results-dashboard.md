# Scenario Results Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Estonian static dashboard that lets visitors explore Notebook 10 scenario results and maps.

**Architecture:** A Python export script converts the existing summary Parquet and six scenario GeoPackages into one browser-friendly JSON payload with shared 500 m cell geometry. A dependency-free HTML, CSS, and JavaScript page renders the selected scenario's metrics, comparison table, chart, and canvas map, so the generated folder can be uploaded to any static host.

**Tech Stack:** Python 3.12, pandas, GeoPandas, standard-library JSON, HTML5, CSS, browser Canvas API, vanilla JavaScript.

## Global Constraints

- Use existing local Notebook 10 outputs only; do not download data or rerun optimisation.
- The public page is in Estonian.
- Cost remains a relative model index, not euros; biodiversity remains a model index, not a measured species change.
- Do not include local paths or raw Forest Registry attributes in the exported browser data.
- Preserve all existing visualizer files; create the dashboard in its own subfolder.
- Keep generated dashboard payloads out of Git if they are derived from ignored result data.

---

## File structure

- Create `visualizer/scenario_results/export_dashboard_data.py`: converts Notebook 10 outputs into a compact shared-geometry JSON data file.
- Create `visualizer/scenario_results/index.html`: accessible page structure and Estonian copy.
- Create `visualizer/scenario_results/styles.css`: responsive page layout and visual design.
- Create `visualizer/scenario_results/app.js`: scenario switching, comparison rendering, chart drawing, and canvas map rendering.
- Create `tests/visualizer/test_scenario_results_dashboard.py`: validates generated data and required page controls without running a browser.
- Create `visualizer/scenario_results/README.md`: generation and upload instructions.

### Task 1: Export verified scenario data

**Files:**
- Create: `visualizer/scenario_results/export_dashboard_data.py`
- Create: `tests/visualizer/test_scenario_results_dashboard.py`

**Interfaces:**
- Consumes: `data/processed/learned_carbon/scenario_summary.parquet` and `data/processed/learned_carbon/scenario_maps/<scenario>.gpkg`.
- Produces: `visualizer/scenario_results/data/scenario-results.json`.
- Exposes: `build_dashboard_payload(summary_path: Path, maps_dir: Path) -> dict` and `write_dashboard_payload(output_path: Path, payload: dict) -> None`.

- [ ] **Step 1: Write failing tests for required scenarios and map fields**

```python
def test_build_dashboard_payload_contains_summary_and_all_scenario_maps(tmp_path):
    payload = build_dashboard_payload(summary_path, maps_dir)

    assert set(payload["scenarios"]) == {
        "balanced", "food_security", "green_maximum", "low_budget",
        "sustainable_agriculture", "wetland_priority",
    }
    assert payload["grid"]["type"] == "FeatureCollection"
    assert payload["maps"]["balanced"]["112"] == {
        "action": "no_change",
        "change_intensity": 0.0,
        "delta_forest": 0.0,
        "delta_wetland": 0.0,
        "delta_agriculture": 0.0,
        "delta_grassland": 0.0,
    }
```

- [ ] **Step 2: Run the test and verify it fails because the exporter is absent**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: FAIL with an import error for `export_dashboard_data`.

- [ ] **Step 3: Implement the compact payload**

```python
def build_dashboard_payload(summary_path: Path, maps_dir: Path) -> dict:
    summary = pd.read_parquet(summary_path)
    scenarios = {
        row["Policy ID"]: {key: _json_value(value) for key, value in row.items()}
        for _, row in summary.iterrows()
    }
    first_map = gpd.read_file(maps_dir / "balanced.gpkg").to_crs("EPSG:4326")
    grid = json.loads(first_map[["cell_id", "geometry"]].to_json())
    maps = {
        scenario: _scenario_values(gpd.read_file(maps_dir / f"{scenario}.gpkg"))
        for scenario in scenarios
    }
    return {"scenarios": scenarios, "grid": grid, "maps": maps}
```

Keep only `action`, `change_intensity`, and four delta fields in `maps`; geometry appears only once in `grid`.

- [ ] **Step 4: Run exporter tests and create the browser data file from existing outputs**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: PASS.

Run: `python visualizer/scenario_results/export_dashboard_data.py`

Expected: writes `visualizer/scenario_results/data/scenario-results.json` without any network request.

- [ ] **Step 5: Commit source and tests, excluding generated JSON**

```bash
git add visualizer/scenario_results/export_dashboard_data.py tests/visualizer/test_scenario_results_dashboard.py
git commit -m "feat: export scenario dashboard data"
```

### Task 2: Build the static Estonian dashboard

**Files:**
- Create: `visualizer/scenario_results/index.html`
- Create: `visualizer/scenario_results/styles.css`
- Create: `visualizer/scenario_results/app.js`
- Modify: `tests/visualizer/test_scenario_results_dashboard.py`

**Interfaces:**
- Consumes: `data/scenario-results.json` generated by Task 1.
- Produces: interactive `index.html` with buttons for six scenarios and map-layer controls.
- Exposes browser functions `loadDashboard()`, `selectScenario(id)`, `renderMetrics()`, `renderComparison()`, `drawMap()`.

- [ ] **Step 1: Write failing static-page contract tests**

```python
def test_dashboard_page_exposes_scenario_and_map_controls():
    html = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    script = (DASHBOARD_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="scenario-selector"' in html
    assert 'id="map-layer"' in html
    assert 'Stsenaariumide võrdlus' in html
    assert "function selectScenario" in script
    assert "function drawMap" in script
```

- [ ] **Step 2: Run the contract test and verify it fails because page files are absent**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: FAIL with missing `index.html`.

- [ ] **Step 3: Implement the semantic page shell and styles**

```html
<main class="dashboard">
  <header class="hero"><p class="eyebrow">ESTONIA LAND-USE</p><h1>Maakasutuse stsenaariumid</h1></header>
  <section class="scenario-control"><label for="scenario-selector">Vali stsenaarium</label><select id="scenario-selector"></select></section>
  <section id="metric-cards" class="metric-grid" aria-label="Valitud stsenaariumi tulemused"></section>
  <section class="map-panel"><select id="map-layer"></select><canvas id="scenario-map" aria-label="Stsenaariumi kaart"></canvas></section>
  <section><h2>Stsenaariumide võrdlus</h2><div id="comparison-table"></div></section>
  <aside class="method-note">Tulemused on mudeli otsustustugi, mitte ametlik planeering ega euro-eelarve.</aside>
</main>
```

Use CSS grid for metric cards and a responsive single-column layout below 900 px.

- [ ] **Step 4: Implement browser data loading and rendering**

```javascript
async function loadDashboard() {
  const response = await fetch("data/scenario-results.json");
  state.data = await response.json();
  state.scenario = "balanced";
  populateScenarioSelector();
  render();
}

function selectScenario(id) {
  state.scenario = id;
  render();
}
```

Render percentages for gains and changed land, render cost as `Suhteline kulude indeks`, and label all model quantities appropriately. Draw the shared GeoJSON geometry on Canvas after fitting its bounds; fill each cell according to selected map layer.

- [ ] **Step 5: Run static-page tests**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: PASS.

- [ ] **Step 6: Commit dashboard source and tests**

```bash
git add visualizer/scenario_results/index.html visualizer/scenario_results/styles.css visualizer/scenario_results/app.js tests/visualizer/test_scenario_results_dashboard.py
git commit -m "feat: add scenario results dashboard"
```

### Task 3: Package and document the uploadable folder

**Files:**
- Create: `visualizer/scenario_results/README.md`
- Modify: `tests/visualizer/test_scenario_results_dashboard.py`

**Interfaces:**
- Consumes: dashboard source and generated JSON.
- Produces: a documented folder that can be uploaded intact to static hosting.

- [ ] **Step 1: Write a failing test for upload instructions and local-data disclosure**

```python
def test_dashboard_readme_explains_generation_and_upload():
    readme = (DASHBOARD_DIR / "README.md").read_text(encoding="utf-8")

    assert "scenario-results.json" in readme
    assert "staatiline veebimajutus" in readme
    assert "andmeid alla" in readme
```

- [ ] **Step 2: Run the test and verify it fails because the README is absent**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: FAIL with missing `README.md`.

- [ ] **Step 3: Write concise Estonian generator and upload instructions**

Include the exact local command to regenerate the derived JSON, state that no data download occurs, and instruct users to upload the whole `visualizer/scenario_results` folder after generation.

- [ ] **Step 4: Run full dashboard and project validation**

Run: `python -m pytest tests/visualizer/test_scenario_results_dashboard.py -q`

Expected: PASS.

Run: `python -m ruff check visualizer/scenario_results/export_dashboard_data.py tests/visualizer/test_scenario_results_dashboard.py`

Expected: PASS.

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit the documentation**

```bash
git add visualizer/scenario_results/README.md tests/visualizer/test_scenario_results_dashboard.py
git commit -m "docs: explain scenario dashboard upload"
```

## Self-review

- Spec coverage: Task 1 uses the exact existing Notebook 10 summary and map outputs; Task 2 covers scenario selection, maps, metrics, comparison, Estonian copy, responsive layout, and model-index disclosure; Task 3 covers uploadability and validation.
- Placeholder scan: no implementation step defers work or relies on undefined interfaces.
- Type consistency: Task 1 produces `scenarios`, `grid`, and `maps`; Task 2 consumes exactly those fields and no raw source paths.
