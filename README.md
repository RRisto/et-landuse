# Estonia Land-Use Neuroevolution

A research sandbox that applies neuroevolution (NSGA-II) to Estonian county-level land-use planning as a decision-support demo.

Explores spatial policy trade-offs between biodiversity, carbon sequestration, habitat connectivity, and restoration cost using transparent proxy assumptions. Inspired by Project Resilience / ELUC, localized to Estonian spatial data.

**This is a research demo, not an official planning tool.** All scores are proxy estimates.

## How it works

1. A **prescriptor** neural network recommends target land-use fractions per 1 km grid cell
2. A **simulator** scores the transition from current to target land use on multiple objectives
3. **NSGA-II** evolves a population of prescriptors to find Pareto-optimal trade-off policies
4. A notebook visualizes results on interactive maps

## Actions

| Action | Description |
|--------|-------------|
| No change | Leave cell as-is |
| Protect | Conservation candidate |
| Restore wetland | Re-wet drained peatland |
| Afforest | Plant forest on agriculture/degraded land |

## Objectives

- Maximize biodiversity proxy
- Maximize carbon proxy (V1.5: spatially-informed)
- Maximize habitat connectivity
- Minimize intervention cost and constraint violations

## Quick start

```bash
# Install dependencies
uv sync

# Launch Jupyter
uv run jupyter lab

# Run notebooks in order:
# 01    — Collect datasets (builds V1 feature table)
# 01.2  — Fetch Rohemeeter biodiversity scores
# 01.3  — Validate features on map
# 02    — Simulator and baselines
# 03    — Neuroevolution (NSGA-II training)
# 03.1  — Neuroevolution with carbon v1.5
# 03.2  — Neuroevolution with Rohemeeter biodiversity
# 04    — UNFCCC data download + NIR model comparison
# 05    — Evolution comparison: flat vs NIR carbon
# 06    — Download forest registry compartment geometries
# 07    — Fetch detailed forest attributes (parallel)
# 08    — Train GBR carbon predictor from real data
# 09    — Spatial join + full model comparison + maps
```

## Interactive visualizer

A standalone HTML/JS app for exploring land-use scenarios without running Python.

```bash
# Generate the grid GeoJSON (one-time, after processing data)
uv run python visualizer/export_geojson.py

# Serve locally (browsers block fetch on file://)
python -m http.server 8000 -d visualizer

# Open http://localhost:8000
```

Features:
- **Action map:** cells colored by assigned action, updates live with sliders
- **Biodiversity map:** Rohemeeter scores (RdYlGn colormap)
- **Metric cards:** CO₂ sequestration, cost, biodiversity, area, cost efficiency — all with confidence intervals
- **Preset scenarios:** Balanced, Max Forest, Restore Wetland, Protect Only
- **Click any cell** for popup with detailed properties

## Project structure

```
├── notebooks/
│   ├── 01_collect_datasets.ipynb       # Build V1 features
│   ├── 01.1_validate_features_map.ipynb # Visual validation of all features
│   ├── 02_simulator_and_baselines.ipynb # Test simulator + baseline policies
│   ├── 03_neuroevolution.ipynb          # NSGA-II evolution
│   ├── 04_learned_carbon_predictor.ipynb # UNFCCC data + NIR vs flat comparison
│   ├── 05_compare_carbon_models.ipynb   # Evolution: flat vs NIR Pareto fronts
│   ├── 06_download_forest_registry.ipynb # Download WFS compartment geometries
│   ├── 07_fetch_forest_details.ipynb    # Fetch detailed attributes (parallel)
│   ├── 08_train_carbon_predictor.ipynb  # Train GBR from real forest data
│   └── 09_spatial_join_and_model.ipynb  # Full pipeline: join + evolve + compare
├── src/
│   ├── estonia_landuse/                 # Main package
│   │   ├── data/                        # Loading, constants
│   │   ├── simulator/                   # Scoring, constraints, config
│   │   │   ├── carbon_tonnes.py         # Lookup-based carbon (V1.5)
│   │   │   ├── carbon_nir.py           # NIR-calibrated carbon model
│   │   │   ├── cost_eur.py             # Cost estimation in EUR with CI
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
| Maa-amet maardlad WFS | Peat deposits | Auto (WFS) |
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
3. **Spatial join** compartment features to the 1km grid (area-weighted)
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

## Cost estimation (EUR)

The module `src/estonia_landuse/simulator/cost_eur.py` estimates implementation cost
and opportunity cost (lost income) in EUR, with confidence intervals.

### Sources for cost estimates

| Parameter | Value range | Source |
|-----------|-------------|--------|
| Afforestation (planting + maintenance) | €1,500–4,000/ha | [Arbonics/AgFunder 2025](https://agfundernews.com/planting-more-forests-comes-with-high-upfront-costs-many-landowners-cant-afford-report) |
| Peatland rewetting | €2,000–15,000/ha | [ERR 2024: €40M+ spent](https://news.err.ee/1609248588/estonia-planning-to-restore-25-000-hectares-of-marshland-by-2050); [€68M meadows plan](https://news.err.ee/1609570045/68-million-meadows-restoration-plan-added-to-updated-climate-act) |
| Agricultural land rent (opportunity cost) | €100–300/ha/yr | [ERR 2026: ~€150/ha/yr](https://news.err.ee/1610026633/agricultural-land-prices-fall-in-estonia-amid-lack-of-large-deals); [Eurostat EU avg €295](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Agricultural_land_prices_and_rents_-_statistics) |
| Agricultural land price | €6,122/ha avg (Estonia 2025) | [ERR 2026](https://news.err.ee/1610026633/agricultural-land-prices-fall-in-estonia-amid-lack-of-large-deals) |

Costs include a configurable time horizon (default 20 years) for opportunity cost annualization.

## Tech stack

Python 3.10+ with uv. Core: GeoPandas, rasterio, PyTorch, NumPy, Pandas, OWSLib.

## Limitations

- All scores are heuristic proxies, not calibrated ecological models
- Weights are chosen by domain intuition, not empirical validation
- CORINE 2018 may be outdated, ESA CCI Biomass is above-ground only
- Peat/soil data from mining registry — does not cover all natural peatland
- Not suitable for real planning decisions without expert validation

See `todo.md` for scientific literature that could improve the model.
