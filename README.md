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
# 01.1  — Validate features on map
# 04    — Build carbon V1.5 dataset (soil, hydrology, biomass)
# 02    — Simulator and baselines
# 03    — Neuroevolution (NSGA-II training)
```

## Project structure

```
├── notebooks/
│   ├── 01_collect_datasets.ipynb       # Build V1 features
│   ├── 01.1_validate_features_map.ipynb # Visual validation of all features
│   ├── 02_simulator_and_baselines.ipynb # Test simulator + baseline policies
│   ├── 03_neuroevolution.ipynb          # NSGA-II evolution
│   └── 04_carbon_dataset.ipynb          # Carbon V1.5 pipeline
├── src/
│   ├── estonia_landuse/                 # Main package
│   │   ├── data/                        # Loading, constants
│   │   ├── simulator/                   # Scoring, constraints, config
│   │   └── optimizer/                   # NSGA-II, prescriptors, seeds
│   └── carbon_dataset/                  # Carbon V1.5 pipeline scripts
│       ├── config.py                    # Lookup tables, weights, paths
│       ├── 01_prepare_grid.py
│       ├── 02_process_corine.py         # Full CORINE raster processing
│       ├── 02a_corine_from_v1.py        # Fast: derive from existing V1
│       ├── 03_process_biomass.py        # ESA CCI Biomass (needs download)
│       ├── 04_process_soil_peat.py      # Estonian WFS: peat + wetlands
│       ├── 05_process_hydrology.py      # ETAK WFS: streams, ditches
│       ├── 06_derive_scores.py          # Combined carbon model
│       └── 07_export_dataset.py         # Merge + export
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

## Key findings (Lääne county)

- 2,806 grid cells at 1 km resolution
- 1,566 cells (56%) have wetland coverage
- 86,469 ditches mapped (mean 3.78 km/cell) — heavily drained landscape
- 27 cells classified as damaged peatland — prime restoration candidates

## Tech stack

Python 3.10+ with uv. Core: GeoPandas, rasterio, PyTorch, NumPy, Pandas, OWSLib.

## Limitations

- All scores are heuristic proxies, not calibrated ecological models
- Weights are chosen by domain intuition, not empirical validation
- CORINE 2018 may be outdated, ESA CCI Biomass is above-ground only
- Peat/soil data from mining registry — does not cover all natural peatland
- Not suitable for real planning decisions without expert validation

See `todo.md` for scientific literature that could improve the model.
