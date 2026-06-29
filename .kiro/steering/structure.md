# Project Structure

```
estonia-neuro-landuse/
├── configs/                    # YAML experiment configurations
│   ├── demo_laane.yaml
│   └── demo_parnu.yaml
├── data/
│   ├── raw/                    # Original downloaded datasets (not committed)
│   ├── interim/                # Intermediate processing artifacts
│   ├── processed/              # Final feature tables and grids
│   │   └── v1/
│   │       ├── base_grid.gpkg
│   │       ├── features_v1.parquet
│   │       ├── features_v1.gpkg
│   │       ├── metadata_v1.yml
│   │       └── proxy_score_lookups.yml
│   └── lookup_tables/          # Score lookup CSVs
├── notebooks/                  # Exploration and debugging notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_simulator_check.ipynb
│   └── 03_evolution_debug.ipynb
├── src/
│   ├── data_v1/                # Numbered data pipeline scripts
│   │   ├── 01_download_sources.md
│   │   ├── 02_make_base_grid.py
│   │   ├── 03_add_land_cover.py
│   │   ├── 04_add_protected_areas.py
│   │   ├── 05_add_osm_features.py
│   │   ├── 06_add_dem_features.py
│   │   ├── 07_derive_proxy_scores.py
│   │   └── 08_export_features.py
│   └── estonia_landuse/        # Main package
│       ├── data/               # Data loading, encoding, constants
│       ├── simulator/          # Action scoring, feasibility, constraints
│       ├── optimizer/          # NSGA-II, candidates, prescriptors, seeds
│       ├── dashboard/          # Streamlit app, maps, charts, explanations
│       └── io/                 # Policy save/load utilities
├── outputs/
│   ├── policies/               # Saved evolved policy weights
│   ├── metrics/                # Training metrics per generation
│   └── maps/                   # Exported map images
├── tests/                      # Pytest test suite
│   ├── test_simulator.py
│   ├── test_constraints.py
│   └── test_prescriptor.py
├── pyproject.toml
└── README.md
```

## Key Architectural Boundaries

- **data/** — never committed to git (add to .gitignore), except lookup tables
- **src/data_v1/** — standalone pipeline scripts, run in numbered order
- **src/estonia_landuse/** — importable package with clear module separation
- **simulator** — stateless scoring functions, no ML dependencies
- **optimizer** — depends on simulator and PyTorch, owns training loop
- **dashboard** — depends on simulator and optimizer outputs, not the training loop

## Module Interfaces

- `ActionPrescriptor.prescribe(context_df) → policy_df` — maps features to actions
- `EstoniaLandUseSimulator.score(context_df, policy_df) → outcomes_df` — evaluates a policy
- `evaluate_candidate(candidate, context_df, simulator)` — wires prescriptor to simulator for NSGA-II fitness
