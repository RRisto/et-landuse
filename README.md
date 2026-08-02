# Estonia Land-Use Neuroevolution

A research sandbox that applies neuroevolution (NSGA-II) to Estonian county-level land-use planning as a decision-support demo. **The current model, simulations, and visualisations cover Lääne County only; they do not yet represent all of Estonia.**

Explores spatial policy trade-offs between biodiversity, carbon sequestration, habitat connectivity, and restoration cost using transparent proxy assumptions. Inspired by Project Resilience / ELUC, localized to Estonian spatial data.

**This is a research demo, not an official planning tool.** All scores are proxy estimates.

## How it works

1. A **prescriptor** neural network recommends target land-use fractions for each grid cell (currently 500 m × 500 m by default)
2. A **simulator** scores the transition from current to target land use on multiple objectives
3. **NSGA-II** evolves a population of prescriptors to find Pareto-optimal trade-off policies
4. A notebook visualizes results on interactive maps

## Actions

The model does not choose one fixed action from a list. It prescribes target
shares for forest, wetland, agricultural land, and grassland in each grid cell.
The displayed action is the land-use type with the largest modelled increase;
it can therefore also be agricultural-land expansion.

## Objectives

- Maximize the biodiversity proxy (including a connectivity bonus near protected areas)
- Maximize the normalised carbon-gain score (the Notebook 10 scenarios use the learned forest-carbon model together with NIR transition factors)
- Minimize intervention cost
- Minimize the share of land changed

Protected-area and wetland-loss rules, wetland feasibility, and agricultural-land
loss limits are constraints and penalties; they are not separate Pareto objectives.

## Customising a scenario

For a one-off scenario change, edit `make_scenario_config()` in
`notebooks/10_scenario_comparison.ipynb`, then rerun Notebook 10. The current
Notebook 10 scenarios use the learned carbon model and these configuration changes:

| Scenario | Configuration relative to the default |
|----------|---------------------------------------|
| **Green Maximum** | `agriculture_loss_cost=0.3`; `max_total_agri_loss_pct=0.50`; `max_changed_pct=0.40`; `budget_penalty_weight=3`; `total_agri_loss_penalty_weight=5` |
| **Food Security** | `agriculture_loss_cost=15`; `max_total_agri_loss_pct=0.03`; `total_agri_loss_penalty_weight=100`; `max_changed_pct=0.15` |
| **Low Budget** | `max_changed_pct=0.06`; `budget_penalty_weight=50`; `base_change_cost=2` |
| **Wetland Priority** | `wetland_suit_min_for_restore=0.05`; `biodiversity_value=[0.4, 1.0, 0.1, 0.3]`; `max_changed_pct=0.25`; `budget_penalty_weight=5` |
| **Balanced** | Uses all default settings below |

The current Balanced defaults are `base_change_cost=0.3`,
`agriculture_loss_cost=2`, `max_agriculture_loss_pct=0.30` per cell,
`max_changed_pct=0.20`, `budget_penalty_weight=10`,
`max_total_agri_loss_pct=0.15`, `total_agri_loss_penalty_weight=20`,
`wetland_suit_min_for_restore=0.15`, and
`biodiversity_value=[0.7, 0.9, 0.2, 0.6]` for forest, wetland, agriculture,
and grassland respectively.

Common settings to customise are:

- `scoring.base_change_cost` and `scoring.agriculture_loss_cost` for the relative intervention and farmland-loss costs;
- `max_changed_pct` and `budget_penalty_weight` for the allowed extent and penalty of land change;
- `max_total_agri_loss_pct` and `total_agri_loss_penalty_weight` for county-wide agricultural-land protection;
- `constraints.wetland_suit_min_for_restore` and `scoring.biodiversity_value` for wetland priority.

The `Cost` result in Notebook 10 is a relative proxy, not a euro estimate. It combines
the changed-land share, an opportunity-cost proxy, and a farmland-loss penalty. The
opportunity-cost proxy uses land use, population, building density, and road density.
To change how that proxy is derived, edit `opportunity_cost_weights` in
`src/estonia_landuse/simulator/config.py`, rerun Notebook 02 to recreate the derived
features, then rerun Notebooks 09 and 10.

## Quick start

```bash
# Install dependencies
uv sync

# Launch Jupyter
uv run jupyter lab

```

### Run Notebook 10 with the learned-carbon data

To reproduce the current Lääne County scenario simulation, run these notebooks in order:

1. `01_collect_datasets.ipynb` — build the base grid and land-use inputs.
2. `01.2_fetch_rohemeeter.ipynb` — add Rohemeeter biodiversity data.
3. `01.4_process_soil_map.ipynb` — add peat-soil coverage.
4. `02_simulator_and_baselines.ipynb` — derive simulator features such as wetland suitability and opportunity-cost proxy.
5. `06_download_forest_registry.ipynb` — download forest-registry compartment geometries.
6. `07_fetch_forest_details.ipynb` — download detailed forest attributes.
7. `08_train_carbon_predictor.ipynb` — train the GBR forest-carbon predictor.
8. `09_spatial_join_and_model.ipynb` — create `data/processed/learned_carbon/features_with_forest.parquet`, the input used by Notebook 10.
9. `10_scenario_comparison.ipynb` — run the scenario simulations and save their results and maps.

Notebooks `03` through `05` are comparison and earlier-model experiments; they are not prerequisites for Notebook 10.

## Interactive visualizer

A standalone HTML/JS viewer for saved Notebook 10 scenario results.

Open the published visualisation: [ristohinno.com/landuse](https://ristohinno.com/landuse/).

```bash
# Generate the grid GeoJSON (one-time, after processing data)
uv run python visualizer/export_geojson.py

# Serve locally (browsers block fetch on file://)
python -m http.server 8000 -d visualizer

# Open http://localhost:8000
```

Features:
- **Scenario selection:** switching a scenario loads its saved model result and highlights it in the comparison table
- **Current land-use map:** the dominant present land-use type in each cell
- **Scenario map:** cells coloured by the largest modelled land-use increase: forest, wetland, grassland, or agricultural land (or no substantial change)
- **Scenario comparison:** saved representative-policy results for every scenario
- **Cell pop-ups:** click a cell to see its identifier and dominant current land use or modelled increase
- **Important:** map colours are not probabilities and do not show the full source-to-destination transition

## Project structure

```
├── notebooks/
│   ├── 01_collect_datasets.ipynb       # Build base grid + V1 features (500m or 1km)
│   ├── 01.2_fetch_rohemeeter.ipynb     # Rohemeeter biodiversity scores
│   ├── 01.4_process_soil_map.ipynb     # Real peat coverage from Mullakaart SHP
│   ├── 02_simulator_and_baselines.ipynb # Derive features + test baselines
│   ├── 03_neuroevolution.ipynb          # NSGA-II evolution
│   ├── 04_learned_carbon_predictor.ipynb # UNFCCC data + NIR vs flat comparison
│   ├── 05_compare_carbon_models.ipynb   # Evolution: flat vs NIR Pareto fronts
│   ├── 06_download_forest_registry.ipynb # Download WFS compartment geometries
│   ├── 07_fetch_forest_details.ipynb    # Fetch detailed attributes (parallel)
│   ├── 08_train_carbon_predictor.ipynb  # Train GBR from real forest data
│   ├── 09_spatial_join_and_model.ipynb  # Full pipeline: join + evolve + compare
│   └── 10_scenario_comparison.ipynb     # 5 policy scenarios side-by-side
├── src/
│   ├── estonia_landuse/                 # Main package
│   │   ├── data/                        # Loading, constants
│   │   ├── simulator/                   # Scoring, constraints, config
│   │   │   ├── carbon_tonnes.py         # Lookup-based carbon (V1.5)
│   │   │   ├── carbon_nir.py           # NIR-calibrated carbon model
│   │   │   ├── carbon_learned.py       # GBR-based carbon (pre-computed predictions)
│   │   │   ├── cost_eur.py             # Post-processing cost estimates in EUR
│   │   │   ├── simulator.py            # Main scorer (supports model switching)
│   │   │   └── config.py               # Config with carbon_model selector
│   │   └── optimizer/                   # NSGA-II, prescriptors, seeds
│   └── carbon_dataset/                  # Carbon V1.5 + forest registry pipeline
│       ├── config.py                    # Lookup tables, weights, paths
│       ├── 01_prepare_grid.py
│       ├── 02_process_corine.py         # Full CORINE raster processing
│       ├── 02a_corine_from_v1.py        # Fast: derive from existing V1
│       ├── 03_process_biomass.py        # ESA CCI Biomass (needs download)
│       ├── 04_process_soil_peat.py      # Estonian WFS: peat + wetlands
│       ├── 05_process_hydrology.py      # ETAK WFS: streams, ditches
│       ├── 06_derive_scores.py          # Combined carbon model
│       ├── 07_export_dataset.py         # Merge + export
│       ├── forest_registry_wfs.py       # WFS download for metsaregister
│       └── forest_registry_details.py   # Parallel REST API detail fetcher
├── data/
│   ├── raw/                             # Downloaded source data (not committed)
│   └── processed/
│       ├── v1/                          # Base features
│       └── carbon_v1_5/                 # Enhanced carbon features
├── configs/                             # YAML experiment configs
├── pyproject.toml
└── todo.md                              # Scientific validation references
```

## Data sources

| Source | What | Access |
|--------|------|--------|
| Statistics Estonia 1km grid | Base grid + population | Auto-download |
| CORINE Land Cover 2018 | Land cover proportions | Manual download (100m raster) |
| EELIS WFS | Protected areas | Auto (WFS) |
| OpenStreetMap (Geofabrik) | Roads, buildings | Auto-download |
| Maa-amet maardlad WFS | Peat deposits (mining registry) | Auto (WFS) |
| Maa-amet Mullakaart | Soil type map (real peat/organic soil coverage) | Manual download (SHP, ~818 MB) |
| ETAK WFS | Wetlands, streams, ditches, waterbodies | Auto (WFS) |
| ESA CCI Biomass v7 | Above-ground biomass | Manual download |
| Forest Registry (metsaregister) | Compartment boundaries + forestry data | Auto (WFS + REST API) |
| UNFCCC (via unfccc_di_api) | Estonia LULUCF emission factors | Auto (Zenodo snapshot) |

### ESA CCI Biomass download

Optional but recommended for better forest carbon estimates:

1. Register at https://catalogue.ceda.ac.uk/uuid/6429d1aafe1e43b9b414e4a5a7f8b903/
2. Navigate to `geotiff/2022/`
3. Download tile `N60E020` (covers all of Estonia):
   - `N60E020_ESACCI-BIOMASS-L4-AGB-MERGED-100m-2022-fv7.0.tif`
   - `N60E020_ESACCI-BIOMASS-L4-AGB_SD-MERGED-100m-2022-fv7.0.tif`
4. Place in `data/raw/esa_cci_biomass/`

## Carbon model (V1.5)

The enhanced carbon scoring separates three concepts:

1. **Existing carbon stock** — what's stored now (biomass + soil carbon)
2. **Protection benefit** — value of preserving high-stock natural cells
3. **Action-specific potential** — per-cell suitability for afforestation or wetland restoration

Key formula:
```
carbon_stock_score = 0.45 * forest_aboveground_carbon + 0.40 * soil_carbon_relevance + 0.15 * corine_fallback
```

The simulator uses these per-cell scores instead of flat land-type densities, making carbon gain spatially informed.

## Carbon model (NIR-calibrated)

An alternative carbon scoring model that uses emission factors from Estonia's National Inventory Report (NIR) instead of proxy lookups.

### How it differs from V1.5

| Aspect | V1.5 (proxy) | NIR-calibrated |
|--------|-------------|----------------|
| Carbon per transition | Flat density lookup `[0.8, 1.0, 0.3, 0.4]` | Per-transition pair × soil type |
| Source→destination awareness | Only destination matters | Full from→to pair tracked |
| Peat sensitivity | Via `peat_overlap_pct` blending | Same, but with NIR-specific factors |
| Wetland gating | Via constraints only | Carbon credit also gated by `wetland_suitability` |
| Data source | Literature estimates | Estonian NIR 2024 + IPCC tables |

### Key transition factors (tCO2/ha/yr, mid estimate)

| Transition | Mineral soil | Peat soil |
|-----------|-------------|-----------|
| Cropland → Forest | +8.7 | +0.5 |
| Grassland → Forest | +6.3 | +1.0 |
| Cropland → Wetland | +2.5 | +23.0 |
| Forest → Cropland | -8.0 | -34.0 |
| Wetland → Cropland | -2.0 | -26.0 |

Sources: [IPCC GPG Table 3A.1.9](https://www.fao.org/4/j2132s/J2132S16.htm), [EEA LULUCF Emission Factors](https://www.eea.europa.eu/en/ghg-knowledge-hub/lulucf/data-tools/emission-factors-viewer), Estonia NIR Ch. 6.

### Usage

Set `carbon_model` in the simulator config:
```python
config = default_config()
config["carbon_model"] = "nir"  # or "flat" for the old model
```

Module: `src/estonia_landuse/simulator/carbon_nir.py`

## Forest Registry integration (Learned predictor)

Uses real compartment-level data from the Estonian Forest Registry (metsaregister) to train a GBR predictor for forest carbon sequestration.

### Data pipeline

1. **Download geometries** via public WFS at `gsavalik.envir.ee/geoserver/mr_portaal/wfs` (CC-BY 4.0)
2. **Fetch detailed attributes** via REST API at `register.metsad.ee/portaal/api/rest/eraldis/detail/{id}`
3. **Spatial join** compartment features to the configured analysis grid (area-weighted)
4. **Train GBR** to predict tCO2/ha/yr from (species, age, site class, drainage, height)

### Conversion formula

```
tCO2/ha/yr = juurdekasv × wood_density × carbon_fraction × CO2/C × BEF
```

| Parameter | Value | Source |
|-----------|-------|--------|
| Wood density | Species-specific (0.35–0.58 t/m³) | [IPCC GPG Table 3A.1.9](https://www.fao.org/4/j2132s/J2132S16.htm) |
| Carbon fraction | 0.50 | IPCC 2006 Vol 4, Ch 4; Uri et al. 2017, 2019 |
| CO2/C ratio | 3.667 | Molecular weight (fixed) |
| BEF | 1.30 | [IPCC GPG Table 3A.1.10](https://www.fao.org/3/j2132s/J2132S18.htm) |

### Key features per grid cell (from spatial join)

| Feature | Source |
|---------|--------|
| `mean_age` | Area-weighted mean forest age |
| `mean_increment` | Area-weighted juurdekasv (m³/ha/yr) |
| `mean_height` | Area-weighted dominant height |
| `mean_volume` | Area-weighted volume (m³/ha) |
| `pct_drained` | Fraction of compartments with `kuivendatud=true` |
| `dominant_species` | Most common species by area |

### Notebooks

```
06_download_forest_registry.ipynb     # Download compartment geometries via WFS
07_fetch_forest_details.ipynb         # Fetch detailed attributes (parallel, configurable)
08_train_carbon_predictor.ipynb       # Train GBR, compare with NIR flat values
09_spatial_join_and_model.ipynb       # Join to grid + run evolution comparison
```

### Cross-evaluation findings

The NIR model dominates the flat model in cross-evaluation:
- Flat-evolved policies score ~0 carbon under NIR evaluation
- NIR-evolved policies score well under both models
- NIR model finds strategies that also improve biodiversity (avoids ecologically damaging transitions)
- NIR model's Pareto front is shorter but represents achievable gains

## Policy Scenario Comparison (Notebook 10)

Five scenarios explore how different policy priorities shape trade-offs:

| Scenario | Key difference |
|----------|---------------|
| **Green Maximum** | Low agriculture protection, high carbon/bio weights — max ecological gain |
| **Food Security** | High agriculture preservation (max 5% loss), expensive to convert farmland |
| **Low Budget** | Max 10% land change, high intervention cost — what's achievable cheaply? |
| **Wetland Priority** | Lower suitability threshold, higher biodiversity value for wetland |
| **Balanced** | Default constraints — middle ground |

All scenarios use the learned carbon model and pre-computed GBR predictions.

## Grid Resolution

Configurable via `GRID_CELL_SIZE` in `src/estonia_landuse/data/constants.py`:

| Resolution | Cells (Lääne) | CORINE pixels/cell | Runtime/model |
|-----------|--------------|-------------------|---------------|
| 1000m | ~2,800 | ~100 | ~30s |
| 500m | ~11,200 | ~25 | ~8 min |
| 250m | ~45,000 | ~6 | ~30 min |

Default: 500m. All carbon modules (`carbon_nir.py`, `carbon_tonnes.py`, `carbon_learned.py`)
automatically use the correct cell area from `constants.CELL_AREA_HA`.

## Key findings (Lääne county)

- 2,806 grid cells at 1 km resolution
- 1,566 cells (56%) have wetland coverage
- 86,469 ditches mapped (mean 3.78 km/cell) — heavily drained landscape
- 27 cells classified as damaged peatland — prime restoration candidates

## Carbon conversion to real units (tCO2/ha/year)

The module `src/estonia_landuse/simulator/carbon_tonnes.py` converts proxy scores
to estimated tonnes CO2 per hectare per year, with confidence intervals (low/mid/high).

Key feature: **peat-aware coefficients** — cells with higher `peat_overlap_pct` use
drained-peatland emission factors, which are much larger than mineral soil values.

### Sources for emission/sequestration rates

| Rate | Value range | Source |
|------|-------------|--------|
| Drained peat cropland emission | 20–35 tCO2/ha/yr | [IPCC 2014 Wetlands Supplement](https://www.ipcc.ch/publication/2013-supplement-to-the-2006-ipcc-guidelines-for-national-greenhouse-gas-inventories-wetlands/) (~29 default) |
| Peat rewetting benefit | 15–30 tCO2/ha/yr avoided | [ERR/METK 2024](https://news.err.ee/1609382576/clashing-interests-in-the-way-of-reducing-co2-emissions-in-agriculture) (~23 tCO2/ha) |
| Estonian drained peatland total emission | 2–8 Mt CO2e/yr from ~30,000 ha | [ERR 2022](https://news.err.ee/1608756928/reducing-co2-emissions-from-land-restoring-wetlands-or-drainage-systems) |
| Estonian peatland GHG synthesis | 419–676 ktCO2e/yr (drained) | [Mander et al. 2010, Wetlands](https://link.springer.com/article/10.1672/08-206.1) |
| Forest sequestration (hemiboreal) | 2–6 tCO2/ha/yr | [EEA Estonia LULUCF](https://www.eea.europa.eu/en/europe-environment-2025/countries/estonia/lulucf-emissions) |
| Afforestation on cropland | 4–15 tCO2/ha/yr | [ResearchGate/IPCC](https://www.researchgate.net/figure/Carbon-sequestration-rate-tons-CO2-ha-year-of-species-planted-across-boreal_fig4_329074041) (boreal/temperate range) |
| Improved drained peat EF | Supports reduction from IPCC default | [Nature 2023](https://www.nature.com/articles/s43247-023-01091-y) |
| Hemiboreal cropland CO2 flux | First direct measurements | [Copernicus 2025](https://bg.copernicus.org/articles/22/4241/2025/index.html) |

**Disclaimer:** These are order-of-magnitude estimates. Actual values require site-specific
assessment. Use for communication and scenario comparison, not carbon accounting.

## Tech stack

Python 3.10+ with uv. Core: GeoPandas, rasterio, PyTorch, NumPy, Pandas, OWSLib.

## Limitations

- All scores are heuristic proxies, not calibrated ecological models
- Weights are chosen by domain intuition, not empirical validation
- CORINE 2018 may be outdated, ESA CCI Biomass is above-ground only
- Peat/soil data from mining registry — does not cover all natural peatland
- Not suitable for real planning decisions without expert validation

See `todo.md` for scientific literature that could improve the model.
