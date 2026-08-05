# Estonia Land-Use Neuroevolution

A research sandbox that applies neuroevolution (NSGA-II) to Estonian county-level land-use planning as a decision-support demo.

Explores spatial policy trade-offs between biodiversity, carbon sequestration, habitat connectivity, and restoration cost using transparent proxy assumptions. Inspired by Project Resilience / ELUC, localized to Estonian spatial data.

**This is a research demo, not an official planning tool.** All scores are proxy estimates.

## How it works

1. A **prescriptor** neural network recommends target land-use fractions per 500 m grid cell
2. A **simulator** scores the transition from current to target land use on multiple objectives
3. Feasible-first **NSGA-II** evolves a population of prescriptors to find Pareto-optimal trade-off policies
4. Notebooks compare objectives, select scenario representatives, and save spatial policy maps

## Actions

| Action | Description |
|--------|-------------|
| No change | Leave cell as-is |
| Protect | Conservation candidate |
| Restore wetland | Re-wet drained peatland |
| Afforest | Plant forest on agriculture/degraded land |

## Objectives

- Maximize biodiversity gain, including a protected-area connectivity bonus for
  forest, wetland, and grassland gains (not agricultural expansion)
- Maximize carbon gain using the selected flat, NIR, or learned model
- Minimize intervention cost
- Minimize changed land; Wetland Priority instead maximizes wetland gain

Physical and scenario-specific policy limits are handled as feasibility
constraints, not as objectives that can be traded away.

## Quick start

```bash
# Install dependencies
uv sync

# Launch Jupyter
uv run jupyter lab

# Run notebooks in order:
# 01    — Collect datasets (builds base grid + features, supports 500m/1km)
# 01.2  — Fetch Rohemeeter biodiversity scores
# 01.4  — Process soil map (real peat coverage from Mullakaart)
# 02    — Simulator and baselines (derives wetland_suitability, opportunity_cost, etc.)
# 03    — Neuroevolution (NSGA-II training)
# 03.1  — Neuroevolution with carbon v1.5
# 03.2  — Neuroevolution with Rohemeeter biodiversity
# 04    — UNFCCC data download + NIR model comparison
# 05    — Evolution comparison: flat vs NIR carbon
# 06    — Download forest registry compartment geometries
# 07    — Fetch detailed forest attributes (parallel)
# 08    — Train GBR carbon predictor from real data
# 09    — Predict compartment carbon, then aggregate predictions to the 500m grid
# 10    — Compare 6 constrained policy scenarios and save representative maps
# 10.1  — Reproduce the 6 historical seed-42 scenario results
# 11.1  — Measure stochastic optimizer-seed variation
# 11.2  — Screen one parameter at a time (OAT)
# 11.3  — Rank simultaneous global parameter sensitivity
# 11.4  — Measure selected two-parameter interactions
# 11.5  — Test biodiversity-assumption robustness
```

Remote-data notebooks set `ALLOW_DOWNLOADS = False` by default. Existing local
files are reused unless you explicitly enable a refresh. Notebook 10 performs
no downloads and requires the prepared
`data/processed/learned_carbon/features_with_forest.parquet` produced by
Notebook 09.

See [docs/scenario-comparison.md](docs/scenario-comparison.md) before running
Notebook 10 or interpreting its outputs.

### Installation profiles

The default install contains the numerical core. Add only the tools needed for
your workflow:

```bash
uv sync --extra pipeline   # geospatial processing and external data sources
uv sync --extra notebook   # Jupyter and visualization
uv sync --extra ml         # PyTorch, Streamlit, and Plotly
uv sync --extra all        # complete research environment
uv sync --extra dev        # tests and linting
```

Run the offline quality checks with:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
```

The automated tests use synthetic fixtures and do not download production
datasets.

### Reproducible and feasible evolution

Pass an explicit seed when comparing experiments:

```python
population = train(
    context,
    feature_columns,
    seed=42,
)
```

Each prescriptor exposes `constraint_violation`. NSGA-II uses feasible-first
selection: every policy with zero constraint violation outranks every
infeasible policy. Feasible policies are then compared using biodiversity,
carbon, cost, and the configured fourth objective. The default fourth objective
minimizes changed area; Wetland Priority maximizes wetland gain. Among
infeasible policies, lower total violation ranks first.

Use `estonia_landuse.scenarios.annotate_feasibility` and
`select_scenario_representatives` before `build_scenario_summary` when
preparing scenario reports. The same selected policy must be reused for the
summary and all maps so they describe one consistent representative.

### Reusing local Rohemeeter data

Rohemeeter collection is expensive and can take a long time. Notebook
`01.2_fetch_rohemeeter.ipynb` reuses existing files under `data/processed/`
and saved progress output by default. Set `ALLOW_DOWNLOADS = True` only when
you intentionally want to refresh those data. The repository ignores `data/`,
so local artifacts can be shared between branches or worktrees without
committing or downloading them again.

## Scenario results dashboard

A standalone Estonian HTML/JS dashboard for viewing the completed Notebook 10
scenario results. Generate its data from existing local outputs, without
downloading data or running the optimisation again:

```powershell
.\.venv\Scripts\python.exe visualizer\scenario_results\export_dashboard_data.py
```

Then serve or upload the complete `visualizer/scenario_results/` directory,
including `data/scenario-results.json`. See
[`visualizer/scenario_results/README.md`](visualizer/scenario_results/README.md)
for the upload structure and interpretation notes.

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
│   ├── 10_scenario_comparison.ipynb     # 6 policy scenarios side-by-side
│   ├── 10.1_fast_scenario_reproduction.ipynb # Historical seed-42 reproduction gate
│   ├── 11.1_stochastic_baseline.ipynb   # Optimizer-seed noise baseline
│   ├── 11.2_one_at_a_time.ipynb         # One-at-a-time parameter screening
│   ├── 11.3_global_sensitivity.ipynb    # Simultaneous global sensitivity
│   ├── 11.4_parameter_interactions.ipynb # Selected two-parameter interactions
│   └── 11.5_biodiversity_robustness.ipynb # Biodiversity-assumption robustness
├── src/
│   ├── estonia_landuse/                 # Main package
│   │   ├── data/                        # Loading, constants
│   │   ├── simulator/                   # Scoring, constraints, config
│   │   │   ├── carbon_tonnes.py         # Lookup-based carbon (V1.5)
│   │   │   ├── carbon_nir.py           # NIR-calibrated carbon model
│   │   │   ├── carbon_learned.py       # GBR-based carbon (pre-computed predictions)
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
3. **Train GBR** to predict tCO2/ha/yr from species, age, site class, drainage, and height
4. **Predict each forest compartment** before spatial aggregation
5. **Overlay and area-weight** compartment predictions onto the 500 m grid

Steps 1 and 2 are guarded by `ALLOW_DOWNLOADS = False` and reuse existing
local files by default.

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

Six scenarios explore how hard policy limits and selection priorities shape
trade-offs:

| Scenario | Maximum changed land | Maximum agriculture loss | Maximum agriculture gain (net/gross) | Representative |
|----------|---------------------:|-------------------------:|-------------------------:|----------------|
| **Green Maximum** | 40% | 50% | No scenario cap | Highest normalized biodiversity + carbon |
| **Food Security** | 15% | 3% | No scenario cap | Highest biodiversity among feasible policies |
| **Low Budget** | 6% | 15% | No scenario cap | Normalized biodiversity/carbon/cost knee |
| **Wetland Priority** | 25% | 15% | 5% / 15% | Normalized biodiversity/carbon/cost/wetland knee |
| **Sustainable Agriculture Expansion** | 15% | 2% gross | 5–10% net | Normalized agriculture/biodiversity/carbon/cost knee |
| **Balanced** | 20% | 15% | No scenario cap | Normalized biodiversity/carbon/cost/change knee |

All scenarios use the learned carbon model and prepared grid-cell predictions.
Changed-land and agriculture-loss excess are hard feasibility violations.
Wetland Priority replaces changed-land minimization with wetland-gain
maximization as the fourth objective, caps net agriculture expansion at 5%
and gross expansion at 15%, and prices gross agriculture expansion. Other
existing scenarios minimize changed land. Sustainable Agriculture Expansion
instead maximizes net agriculture gain, requires 5–10% expansion, caps gross
agriculture loss at 2%, and limits biodiversity and carbon loss to 1% each.

Notebook 10 selects one representative per scenario and reuses that exact
policy in the summary, plots, and saved GeoPackages. A dedicated wetland-gain
figure shows rewetting that the dominant-action map can hide. See
[docs/scenario-comparison.md](docs/scenario-comparison.md) for prerequisites,
outputs, and interpretation guidance.

## Historical-model sensitivity analysis (Notebooks 10.1–11.5)

The sensitivity workflow tests whether Notebook 10's selected policies and
reported outcomes remain stable when optimizer randomness or declared model
assumptions change. It uses the same historical trainer and scenario rules as
Notebook 10, wrapped in a resumable manifest runner. Run the notebooks in this
order:

| Notebook | Question answered |
|----------|-------------------|
| **10.1 Fast scenario reproduction** | Can the preserved runner reproduce all six historical Notebook 10 results with the published seed, 42? |
| **11.1 Stochastic baseline** | How much variation is caused by optimizer seeds while scenario defaults stay fixed? |
| **11.2 One-at-a-time (OAT)** | Which individual parameters have effects larger than baseline seed noise, and are their responses nonlinear? |
| **11.3 Global sensitivity** | Which parameters matter when all sampled parameters vary simultaneously? |
| **11.4 Parameter interactions** | Do selected parameter pairs have non-additive effects? |
| **11.5 Biodiversity robustness** | Do alternative dimensionless biodiversity-value assumptions change outcomes, rankings, or spatial recommendations? |

Notebook 10.1 is the scientific gate: only a `full` seed-42 run is compared
with the saved Notebook 10 summary and allowed to pass reproduction. Run
Notebook 11.1 next because its seed-to-seed variation is the noise reference
used when interpreting OAT, global, interaction, and biodiversity effects.

Choose the compute profile and worker count before starting Jupyter:

```powershell
$env:SENSITIVITY_PROFILE = "screen"
$env:SENSITIVITY_N_WORKERS = "2"
uv run jupyter lab
```

- `test` uses a tiny deterministic context as an executable smoke test.
- `screen` uses real inputs with a reduced optimizer budget for exploratory runs.
- `full` uses the historical scientific budget; use it for reproduction and final conclusions.

Outputs default to `data/processed/legacy_sensitivity/`. Valid completed
artifact pairs are reused when a notebook is rerun; set
`SENSITIVITY_OVERWRITE=true` only when intentional recomputation is required.
Increase `SENSITIVITY_N_WORKERS` gradually because each process holds its own
data and optimizer state.

These experiments measure sensitivity of the historical model and optimizer
within the tested parameter ranges. They do **not** estimate empirical
ecological uncertainty or prove that a recommendation is ecologically
correct. See the
[legacy optimizer sensitivity design](docs/superpowers/specs/2026-08-04-legacy-optimizer-sensitivity-design.md)
for the detailed experiment and artifact contract.

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
