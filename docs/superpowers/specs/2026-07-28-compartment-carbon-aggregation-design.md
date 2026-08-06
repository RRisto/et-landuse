# Compartment-First Carbon Aggregation Design

## Goal

Use the existing trained Forest Registry carbon model at the level it was
trained for—individual forest compartments—and then aggregate its predictions
into the operational 500 m grid. This replaces Notebook 10's incompatible
attempt to apply compartment feature names to grid-level aggregate columns.

The trial uses only existing local data. It must not download Forest Registry,
Rohemeeter, or any other remote dataset.

## Scope

The change will:

- add a small, tested aggregation helper under `src/carbon_dataset/`;
- update Notebook 09 to predict before its spatial overlay is aggregated;
- save cell-level carbon rate and total columns in both forest feature outputs;
- update Notebook 10 to consume the prepared column and fail clearly when it is
  absent;
- run Notebook 09 with existing data and inspect the resulting distribution.

The change will not:

- retrain or replace the existing GBR model;
- change scenario constraints, objectives, or representative-policy selection;
- rerun Notebook 10's two-hour scenario experiment;
- commit or overwrite the user's current Notebook 10 execution results.

## Data Flow

1. Notebook 09 loads compartment geometries and detailed Forest Registry
   attributes.
2. The existing GBR receives the original compartment fields:
   `peapuuliik`, `keskmVanus`, `boniteediKood`, `kuivendatud`,
   `kasvukohaKood`, `pindala`, and `korgus`.
3. Each compartment receives `predicted_tco2_ha_yr`.
4. The spatial overlay splits compartments at 500 m grid boundaries while
   retaining the compartment prediction.
5. A pure helper aggregates overlay pieces by `cell_id`:
   - `predicted_tco2_yr` is the sum of prediction rate multiplied by valid
     intersection area in hectares;
   - `predicted_tco2_ha_yr` is that total divided by the valid predicted forest
     area.
6. Notebook 09 merges the two columns into
   `grid_forest_features.parquet` and `features_with_forest.parquet`.
7. Notebook 10 reads `predicted_tco2_ha_yr` directly. If the column is absent,
   it raises a clear error instructing the user to run Notebook 09.

The model prediction uses each compartment's original full `pindala` feature.
Only the later grid aggregation is weighted by intersection area, preventing a
compartment that crosses cell boundaries from being counted at full area in
each cell.

## Aggregation Contract

The helper accepts a table containing:

- a cell identifier;
- a per-hectare prediction;
- an intersection-area weight in hectares.

Rows with non-finite predictions, non-finite areas, or non-positive areas do
not contribute. A cell with no valid contribution receives `NaN` for its
per-hectare rate and zero for its annual total. This lets downstream code
distinguish "no usable forest prediction" from a real zero prediction.

The helper returns one row per cell with:

- valid predicted forest area;
- area-weighted `predicted_tco2_ha_yr`;
- total `predicted_tco2_yr`.

## Notebook Behavior

Notebook 09 remains an explicit local preprocessing step. It will not acquire
remote data. Its existing duplicate aggregation block will be removed while
the carbon prediction is integrated.

Notebook 10 will no longer silently substitute a fallback when the prepared
prediction column is missing. A silent fallback previously made a run look as
if it used the GBR when it did not. Failing early makes the experiment's carbon
provenance unambiguous.

## Testing

Tests will be written before implementation and will cover:

- correct area-weighted rate and total for multiple overlay pieces;
- correct handling of one compartment split across cells;
- exclusion of missing predictions and invalid or zero areas;
- output for a cell with no valid prediction;
- Notebook 09's use of the shared aggregation helper;
- Notebook 10's requirement for the prepared prediction and absence of its old
  grid-level model/fallback block.

After focused tests pass, the full Ruff and pytest suites will run. Notebook
code cells will be syntax-compiled without executing them.

## Trial and Review

After implementation, Notebook 09 will run against the existing local files.
The review will report:

- number of cells with valid predictions;
- minimum, median, mean, and maximum per-hectare prediction;
- total predicted annual forest carbon;
- missing-prediction count;
- comparison against the current `mean_increment` fallback distribution.

Notebook 10 will not be rerun until these results are reviewed and accepted.
