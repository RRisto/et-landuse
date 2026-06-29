# Tech Stack

## Language

- Python 3.10+

## Package Management

- **uv** — used for dependency management, virtual environments, and running scripts
- pyproject.toml (PEP 621)

## Code Style

- Keep code minimal and concise
- Primary workflow: Jupyter notebooks for running code and exploration
- Reusable logic lives in `.py` files as importable functions
- Avoid over-engineering; prefer simple functions over class hierarchies where possible

## Core Libraries

| Category | Libraries |
|----------|-----------|
| Neural networks | PyTorch |
| Optimization | NSGA-II (custom implementation based on Project Resilience MVP) |
| Geospatial | GeoPandas, Shapely, Fiona, rasterio |
| Data processing | Pandas, NumPy |
| Dashboard | Streamlit |
| Visualization | Folium or Pydeck (maps), Plotly or Altair (charts) |
| Configuration | YAML (PyYAML or OmegaConf) |
| File formats | GeoPackage (.gpkg), Parquet, GeoJSON |

## CRS

All spatial data is processed in **EPSG:3301** (Estonian national coordinate system).

## Common Commands

```bash
# Create venv and install dependencies
uv sync

# Add a dependency
uv add <package>

# Run a script
uv run python src/estonia_landuse/some_module.py

# Run dashboard
uv run streamlit run src/estonia_landuse/dashboard/app.py

# Run tests
uv run pytest tests/

# Run evolution training
uv run python -m estonia_landuse.optimizer.trainer --config configs/demo_laane.yaml

# Launch Jupyter
uv run jupyter lab
```

## Configuration

Experiment configs are YAML files in `configs/`. Key parameters:

```yaml
pop_size: 100
n_generations: 100
p_mutation: 0.2
mutation_factor: 0.1
hidden_size: 16
```

For fast local debugging use `pop_size: 20`, `n_generations: 10`.

## Data Pipeline

Data processing runs in numbered Jupyter notebooks:

```
notebooks/
  01_data_exploration.ipynb
  02_make_base_grid.ipynb
  03_add_land_cover.ipynb
  ...
```

Shared helper functions live in `src/estonia_landuse/` as `.py` modules.

Raw data goes in `data/raw/`, processed outputs in `data/processed/v1/`.
