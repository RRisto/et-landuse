# Estonia Neuroevolution Land-Use Demo Plan

## 1. Purpose

Build a practical open-source demo that adapts the Project Resilience land-use neuroevolution approach to an Estonian county-level land-use planning sandbox.

The demo should not claim to produce official land-use policy. Instead, it should explore spatial policy trade-offs under transparent proxy assumptions.

**Working description:**

> A county-level decision-support sandbox where a neuroevolutionary optimizer evolves land-use action policies and visualizes trade-offs between biodiversity, carbon, restoration cost, and habitat connectivity.

---

## 2. Relationship to Project Resilience MVP

This project should be implemented as a localized Estonia-inspired use case based on the structure of the Project Resilience MVP ELUC use case.

The existing MVP code is useful because it already demonstrates:

- context → action → outcome framing
- predictor / prescriptor separation
- neuroevolutionary prescriptors
- NSGA-II multi-objective optimization
- Pareto-front policy search
- seed policies
- experiment notebooks
- demo-oriented architecture

The Estonia version should reuse the optimizer and prescriptor ideas, but replace the global ELUC data pipeline and carbon-only outcome model.

### Reuse from Project Resilience MVP

| Component | Reuse level | Notes |
|---|---:|---|
| Context/action/outcome framing | High | Keep the conceptual model |
| Prescriptor idea | High | A policy model recommends actions |
| PyTorch candidate network | High | Fixed small neural network is enough |
| NSGA-II training loop | High | Adapt evaluation function |
| Pareto-front output | High | Central to the dashboard |
| Seed policies | High | Useful for realistic Pareto edges |
| ELUC/LUH2/BLUE data pipeline | Low | Too coarse for Estonia county-level demo |
| Current land-use fraction action model | Medium | Replace or simplify for discrete actions |
| Existing web app | Medium | Reuse design ideas, rebuild map layers |

---

## 3. First Demo Scope

### Geography

Start with one Estonian county, not all Estonia.

Recommended candidates:

1. **Lääne County / Matsalu area**
   - strong biodiversity and wetland story
   - visually understandable conservation/restoration use case

2. **Pärnu County**
   - wetlands, forests, coast, agriculture, protected areas

3. **Tartu County**
   - balanced urban, agricultural, forest, and natural land-use patterns

For the first demo, choose **Lääne County or Pärnu County**.

### Grid resolution

Use **1 km grid cells** for v1.

Avoid 250 m in the first version because it increases preprocessing, memory, and spatial-join complexity before the simulator is validated.

### Time horizon

Use **static optimization** first.

Do not model multi-year land-use transitions in v1. The first version should answer:

> Given the current landscape and our proxy assumptions, which land-use actions produce good trade-offs?

---

## 4. V1 Actions

Use a small discrete action set:

| ID | Action | Meaning |
|---:|---|---|
| 0 | No change | Keep current land use |
| 1 | Protect | Prioritize conservation / legal protection candidate |
| 2 | Restore wetland | Restore likely wetland / peatland / hydrologically suitable areas |
| 3 | Afforest | Add forest where ecologically and economically plausible |

Delay these actions until v2:

- agriculture expansion
- urban development
- forestry intensification
- renewable energy siting
- peatland drainage reversal with detailed hydrology

Reason: the v1 demo should show neuroevolution and trade-offs, not solve full land-use planning.

---

## 5. V1 Objectives

Use four main objectives:

1. **Maximize biodiversity proxy**
2. **Maximize carbon proxy**
3. **Maximize habitat connectivity / minimize fragmentation**
4. **Minimize intervention cost and constraint violations**

Optional separate objective:

5. **Minimize economic opportunity cost proxy**

For v1, avoid claiming true economic optimization. Use transparent proxy scores.

---

## 6. Data Model

Each grid cell should become one row in a feature table.

### Required features

| Feature | Type | Possible source / derivation |
|---|---|---|
| cell_id | string/int | generated grid |
| geometry | polygon | generated grid |
| centroid_x | float | grid centroid |
| centroid_y | float | grid centroid |
| land_cover_class | categorical | CORINE Land Cover / ESA WorldCover |
| protected_overlap | float | Estonian protected areas / Natura 2000 |
| road_distance | float | OpenStreetMap |
| water_distance | float | OpenStreetMap / national water layers |
| wetness_proxy | float | elevation, water proximity, land-cover class, peat/wetland classes |
| carbon_proxy | float | lookup table by land-cover class |
| naturalness_proxy | float | lookup table by land-cover class |
| biodiversity_proxy | float | naturalness + protected proximity + habitat diversity; optionally public observations |
| population_proxy | float | Statistics Estonia / settlement data |
| opportunity_cost_proxy | float | land-cover-based score |
| neighbor_natural_share | float | share of natural/semi-natural cells nearby |

### File formats

Recommended processed outputs:

```text
processed/
  county_grid.gpkg
  county_features.parquet
  county_features.geojson
  lookup_landcover_scores.csv
```

Use `GeoPackage` for GIS compatibility and `Parquet` for fast model training.

---

## 7. Simulator Design

The simulator is the most important part of the project.

The first simulator should be simple, transparent, and modular. It should not pretend to be an ecological truth model.

### Simulator input

```text
context_df: one row per grid cell
policy_actions: one action per grid cell
```

### Simulator output

```text
biodiversity_gain
carbon_gain
connectivity_gain
restoration_cost
opportunity_cost
constraint_penalty
changed_area
```

### Example scoring logic

#### Protect

Good when:

- biodiversity proxy is high
- naturalness score is high
- near existing protected area
- improves habitat connectivity

Bad when:

- urban/populated cell
- very high opportunity cost
- already protected, unless protection is allowed as reinforcement

#### Restore wetland

Good when:

- wetness proxy is high
- current land cover suggests former/current wetland, peatland, grassland, or low-value agriculture
- near water or wetland
- low road density

Bad when:

- urban area
- high-value agriculture
- steep terrain or unsuitable hydrology
- far from plausible wetland features

#### Afforest

Good when:

- low-value open land
- near existing forest
- improves carbon score

Bad when:

- valuable open habitat
- wetland/peatland candidate
- existing protected grassland
- urban area

#### No change

Good when:

- action would violate constraints
- current land use already has high value
- intervention cost is too high

---

## 8. Constraints

Hard or soft constraints should prevent unrealistic policies.

### Suggested v1 constraints

- Do not change urban cells.
- Do not restore wetland where wetness suitability is below threshold.
- Do not afforest likely wetland cells.
- Do not afforest high-value open habitats.
- Do not modify more than a configurable percentage of the county.
- Penalize isolated single-cell interventions.
- Penalize interventions far away from similar habitat patches.
- Prefer actions adjacent to existing natural/protected areas.

Represent constraints as penalty terms first. Later some can become hard feasibility masks.

---

## 9. Neuroevolution Design

### Prescriptor type

Use a fixed-topology neural network, similar to the Project Resilience MVP ELUC prescriptor:

```text
input: grid-cell features
hidden layer: 16 tanh units
output: action scores
```

For v1:

```text
in_size = number of encoded features
hidden_size = 16
out_size = 4 actions
```

The prescriptor outputs action scores. The selected action is the highest-scoring feasible action.

### Evolution algorithm

Use NSGA-II.

Suggested defaults:

```json
{
  "pop_size": 100,
  "n_generations": 100,
  "p_mutation": 0.2,
  "mutation_factor": 0.1,
  "hidden_size": 16
}
```

For fast local debugging:

```json
{
  "pop_size": 20,
  "n_generations": 10,
  "p_mutation": 0.2,
  "mutation_factor": 0.1,
  "hidden_size": 16
}
```

### Fitness metrics

NSGA-II should minimize all metrics. Convert maximization objectives by negating them.

```python
candidate.metrics = (
    -biodiversity_gain_mean,
    -carbon_gain_mean,
    -connectivity_gain_mean,
    restoration_cost_mean,
    constraint_penalty_mean,
)
```

For v1, keep objectives few. Too many objectives can make the Pareto front hard to interpret.

Recommended v1 metrics:

```python
candidate.metrics = (
    -biodiversity_gain_mean,
    -carbon_gain_mean,
    restoration_cost_mean,
    fragmentation_penalty_mean,
    constraint_penalty_mean,
)
```

---

## 10. Seed Policies

Seed policies are important because purely random neural policies may struggle to find realistic low-change solutions.

Create simple rule-based seed policies:

### Seed 1: Do nothing

All cells keep current land use.

### Seed 2: Biodiversity-first

Protect cells with high biodiversity proxy and high naturalness.

### Seed 3: Wetland restoration

Restore cells with high wetness proxy, low opportunity cost, and low constraint risk.

### Seed 4: Carbon-first

Afforest suitable low-value open cells and protect high-carbon natural cells.

### Seed 5: Connectivity-first

Protect or restore cells that connect existing protected/natural areas.

These seeds can either be:

- converted into neural-network weight initializations, or
- added as baseline policies outside the neural population, then compared in the dashboard.

For v1, it is acceptable to use them as baselines first and add neural seeding later.

---

## 11. Baselines

The demo must compare neuroevolution against simple alternatives.

Recommended baselines:

| Baseline | Purpose |
|---|---|
| No change | Minimum intervention reference |
| Random feasible actions | Weak lower bound |
| Protect top biodiversity cells | Simple conservation strategy |
| Restore top wetland-suitability cells | Simple restoration strategy |
| Afforest top carbon-suitability cells | Simple carbon strategy |
| Weighted rule-based policy | Human-designed heuristic |

A successful demo does not need to prove ecological correctness. It should show that evolved policies discover better trade-offs than simple rules under the stated simulator assumptions.

---

## 12. Dashboard

Build the dashboard with Streamlit first.

### Page 1: Data overview

Show:

- selected county
- grid cells
- current land cover
- protected areas
- biodiversity proxy layer
- carbon proxy layer
- wetness proxy layer

### Page 2: Optimization settings

Controls:

- objective weights for display/filtering
- maximum changed area
- enabled actions
- restoration budget proxy
- constraint strictness
- number of generations / population size for demo mode

### Page 3: Pareto policies

Show:

- Pareto frontier scatterplot
- selected policy point
- KPI cards
- comparison against baselines

Example KPIs:

```text
biodiversity gain
carbon gain
connectivity gain
changed area %
restoration cost proxy
constraint violations
```

### Page 4: Policy map

Map layers:

- current land cover
- recommended actions
- protected areas
- biodiversity proxy
- carbon proxy
- wetness proxy

Action colors:

```text
No change: gray
Protect: green
Restore wetland: blue
Afforest: dark green
Constraint violation: red outline
```

### Page 5: Cell explanation

When the user clicks a cell, show:

```text
Cell ID
Current land cover
Recommended action
Biodiversity proxy
Carbon proxy
Wetness proxy
Opportunity cost proxy
Constraint penalty
Reason for recommendation
```

Example explanation:

```text
Recommended action: Restore wetland
Reason:
- high wetness proxy
- near existing wetland/protected area
- low opportunity cost
- improves connectivity
- moderate carbon benefit
```

---

## 13. Suggested Repository Structure

```text
estonia-neuro-landuse/
  README.md
  pyproject.toml
  configs/
    demo_laane.yaml
    demo_parnu.yaml
  data/
    raw/
    interim/
    processed/
    lookup_tables/
  notebooks/
    01_data_exploration.ipynb
    02_simulator_check.ipynb
    03_evolution_debug.ipynb
  src/
    estonia_landuse/
      data/
        make_grid.py
        load_landcover.py
        load_protected_areas.py
        load_osm.py
        build_features.py
        encoder.py
        constants.py
      simulator/
        actions.py
        feasibility.py
        scoring.py
        connectivity.py
        constraints.py
        simulator.py
      optimizer/
        candidate.py
        nsga2_utils.py
        trainer.py
        action_prescriptor.py
        seeds.py
        baselines.py
      dashboard/
        app.py
        maps.py
        charts.py
        explanations.py
      io/
        save_policy.py
        load_policy.py
  outputs/
    policies/
    metrics/
    maps/
  tests/
    test_simulator.py
    test_constraints.py
    test_prescriptor.py
```

---

## 14. Implementation Plan

### Milestone 1: Minimal county dataset

Goal: build one usable geospatial feature table.

Tasks:

- choose county
- create 1 km grid
- add land-cover class
- add protected-area overlap
- add road distance
- add water distance
- add simple wetness/naturalness/carbon lookup scores
- export `county_features.parquet` and `county_grid.gpkg`

Definition of done:

- one row per grid cell
- all required v1 features present
- map can show current land cover and proxy layers

---

### Milestone 2: Rule-based simulator

Goal: produce believable metrics before adding neuroevolution.

Tasks:

- implement action feasibility masks
- implement action scoring
- implement constraints
- implement connectivity/fragmentation proxy
- run simulator on rule-based policies

Definition of done:

- no-change baseline works
- random feasible policy works
- biodiversity-first policy works
- wetland-restoration policy works
- metrics are explainable

---

### Milestone 3: Baseline dashboard

Goal: show maps and metrics without neuroevolution.

Tasks:

- build Streamlit app
- load processed county data
- show current land-use map
- show rule-based policy maps
- show KPI comparison table

Definition of done:

- user can select a baseline policy
- dashboard updates map and KPIs
- cell-level explanation works

---

### Milestone 4: Neuroevolution v1

Goal: evolve action policies with NSGA-II.

Tasks:

- adapt candidate neural network
- implement action prescriptor
- adapt NSGA-II trainer
- evaluate policies with local simulator
- save Pareto-front candidates

Definition of done:

- training run completes locally
- results CSV saved per generation
- rank-1 policies saved
- at least one evolved policy beats simple baselines on some trade-off region

---

### Milestone 5: Pareto dashboard

Goal: make neuroevolution visible.

Tasks:

- load saved Pareto policies
- display Pareto frontier
- select policy from chart/table
- show selected policy map
- compare selected policy against baselines

Definition of done:

- user can explore trade-offs interactively
- selected Pareto policy appears on the map
- KPIs and changed area update correctly

---

### Milestone 6: Documentation and demo narrative

Goal: make the project understandable and honest.

Tasks:

- document all proxy assumptions
- document action scoring rules
- document limitations
- write demo walkthrough
- add reproducible run commands

Definition of done:

- another developer can reproduce the demo
- assumptions are visible in the app and README
- limitations are clearly stated

---

## 15. Minimal Code Interfaces

### Context dataframe

```python
context_df = pd.DataFrame({
    "cell_id": ..., 
    "land_cover": ...,
    "protected_overlap": ...,
    "biodiversity_proxy": ...,
    "carbon_proxy": ...,
    "wetness_proxy": ...,
    "road_distance": ...,
    "opportunity_cost_proxy": ...,
    "neighbor_natural_share": ...,
})
```

### Prescriptor interface

```python
class ActionPrescriptor:
    def prescribe(self, context_df: pd.DataFrame) -> pd.DataFrame:
        """Return one recommended action per grid cell."""
```

Output:

```python
policy_df = pd.DataFrame({
    "cell_id": ...,
    "action": ...,
})
```

### Simulator interface

```python
class EstoniaLandUseSimulator:
    def score(self, context_df: pd.DataFrame, policy_df: pd.DataFrame) -> pd.DataFrame:
        """Return per-cell and aggregate-compatible outcome metrics."""
```

Output:

```python
outcomes_df = pd.DataFrame({
    "cell_id": ...,
    "biodiversity_gain": ...,
    "carbon_gain": ...,
    "connectivity_gain": ...,
    "restoration_cost": ...,
    "opportunity_cost": ...,
    "fragmentation_penalty": ...,
    "constraint_penalty": ...,
})
```

### Candidate evaluation

```python
def evaluate_candidate(candidate, context_df, simulator):
    policy_df = candidate.prescribe(context_df)
    outcomes_df = simulator.score(context_df, policy_df)

    candidate.metrics = (
        -outcomes_df["biodiversity_gain"].mean(),
        -outcomes_df["carbon_gain"].mean(),
        outcomes_df["restoration_cost"].mean(),
        outcomes_df["fragmentation_penalty"].mean(),
        outcomes_df["constraint_penalty"].mean(),
    )
```

---

## 16. Assumption Register

Maintain an assumption register from the beginning.

Example:

| Assumption | Used in | Risk | Later improvement |
|---|---|---|---|
| Carbon proxy by land-cover class | carbon objective | too simple | add peat/soil/forest age data |
| Biodiversity proxy from naturalness + protected proximity | biodiversity objective | may miss species data | add public observation density / habitat models |
| Wetland suitability from wetness proxy | restoration action | hydrology too simple | add peatland/drainage/elevation data |
| Opportunity cost by land-cover class | cost objective | not real economics | add local land value/agriculture/forestry data |
| Connectivity from neighboring natural cells | habitat objective | simple spatial metric | add graph-based ecological connectivity |

---

## 17. Risks

### Data harmonization risk

Spatial datasets may use different projections, resolutions, and formats.

Mitigation:

- start with few layers
- use one county
- use 1 km grid
- store processed features in one table

### Ecological validity risk

Proxy scores may be too simplistic.

Mitigation:

- label them clearly as proxies
- document all scoring assumptions
- compare policies rather than claiming truth

### Optimizer exploitation risk

Evolution may exploit weaknesses in the simulator.

Mitigation:

- add constraints
- inspect maps visually
- compare against baselines
- use penalties for unrealistic patchwork

### Interpretability risk

Users may not understand why actions are recommended.

Mitigation:

- cell-level explanations
- visible scoring components
- action suitability maps

### Scope risk

Full Estonia, climate scenarios, API, and economic modeling could make v1 too large.

Mitigation:

- one county
- static optimization
- four actions
- Streamlit first

---

## 18. What Not To Build in V1

Do not build these yet:

- full Estonia pipeline
- 250 m grid
- climate scenario modeling
- REST API
- full Project Resilience SDK integration
- detailed economic model
- detailed hydrological wetland model
- land-use transition dynamics over decades
- complex NEAT topology evolution
- official policy recommendation claims

These are v2/v3 extensions.

---

## 19. V2 Extensions

After the demo works:

- expand to all Estonia
- add multiple counties
- add 250 m grid option
- add climate scenario layers
- add peatland and soil carbon data
- add more realistic restoration-cost model
- add agriculture and forestry opportunity-cost models
- add uncertainty estimates
- add REST API
- add Project Resilience-compatible model submission interface
- add user-adjustable objective weights
- add exportable GeoJSON policy layers

---

## 20. Success Criteria

The v1 project is successful if it:

- uses real Estonian spatial data for at least one county
- creates a harmonized grid-cell feature table
- implements a transparent land-use action simulator
- evolves policies with NSGA-II
- compares evolved policies against rule-based baselines
- displays Pareto-front trade-offs
- shows recommended actions on an interactive map
- explains recommendations at cell level
- clearly documents assumptions and limitations

The key success claim should be:

> The demo shows how neuroevolution can explore land-use policy trade-offs under transparent proxy assumptions.

Avoid claiming:

> The system finds the optimal land-use plan for Estonia.

---

## 21. Recommended First Sprint

A realistic first sprint should produce a non-evolutionary baseline demo.

### Sprint goal

Build a map-based baseline simulator for one county.

### Sprint tasks

1. Create 1 km grid for one county.
2. Add land-cover data.
3. Add protected-area overlap.
4. Add road/water distance.
5. Create proxy lookup tables.
6. Implement four actions.
7. Implement simple rule-based policies.
8. Show maps and KPIs in Streamlit.

### Sprint output

A working dashboard where the user can compare:

- no change
- biodiversity-first protection
- wetland restoration
- carbon-first afforestation

Only after this works should NSGA-II be added.

---

## 22. Recommended Positioning

Use careful language:

> This is a research and demo platform for exploring spatial land-use policy trade-offs. It uses neuroevolution to search for policies that perform well under explicitly documented proxy assumptions. It is not an official land-use planning tool and should not be used for real-world decisions without expert validation.

