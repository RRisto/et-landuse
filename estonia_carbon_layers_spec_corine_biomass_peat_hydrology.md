# Estonia Carbon-Relevance Dataset Specification

**Layers:** CORINE + ESA CCI Biomass + peat/soil + hydrology  
**Use case:** Build a carbon-relevance and action-impact feature layer for an Estonia land-use neuroevolution demo.  
**Target output:** one row per 1 km grid cell, with carbon-stock, carbon-change-potential, wetland-restoration suitability, afforestation suitability, and uncertainty fields.

---

## 1. Purpose

This specification describes how to build a spatial dataset that combines:

1. **CORINE Land Cover**  
   Used for current land-cover context and broad land-use grouping.

2. **ESA CCI Biomass**  
   Used for above-ground biomass and forest above-ground carbon proxy.

3. **Peat / soil data**  
   Used for soil-carbon and peatland relevance, especially for wetland restoration.

4. **Hydrology data**  
   Used for wetland-restoration suitability, water proximity, floodplain/wetness proxy, and drainage context.

The final dataset should support a land-use policy simulator with actions such as:

```text
no_change
protect
restore_wetland
afforest
```

The dataset should not claim to estimate exact CO₂ emissions. It should produce transparent proxy features that can be improved later.

---

## 2. Design Principle

Separate three concepts:

```text
1. Existing carbon stock
2. Carbon-risk / carbon-preservation relevance
3. Action-specific carbon-change potential
```

Example:

```text
High biomass forest:
  high existing above-ground carbon stock
  strong protection/no-change signal

Drained peatland / organic soil:
  potentially high soil-carbon relevance
  strong wetland-restoration signal
  may have low above-ground biomass

Agricultural land:
  low current above-ground biomass
  possible afforestation or wetland-restoration potential
  but higher opportunity cost
```

---

## 3. Target Spatial Unit

### V1.5 / V2 default

Use a **1 × 1 km grid**.

Recommended base grid:

```text
Statistics Estonia 1 × 1 km population grid, EPSG:3301
```

Reason:

- already aligned to Estonia;
- useful for opportunity-cost and settlement-pressure proxy;
- good resolution for a demo;
- not too computationally heavy.

### Coordinate reference system

Use:

```text
EPSG:3301
```

This is the Estonian national projected coordinate system and is suitable for area and distance calculations.

---

## 4. Source Datasets

## 4.1 CORINE Land Cover

### Source

Copernicus Land Monitoring Service  
URL: https://land.copernicus.eu/en/products/corine-land-cover

### Recommended product

```text
CORINE Land Cover 2018
Raster GeoTIFF
100 m resolution
File: u2018_clc2018_v2020_20u1_raster100m
Approx size: ~125 MB
```

### Why raster, not vector?

Use the 100 m raster because:

```text
1 km grid cell = approximately 100 CORINE pixels
```

This makes it easy to calculate class proportions per 1 km cell.

The 4–5 GB vector products are unnecessary for a first carbon/suitability dataset.

### Use in this project

Derived fields:

```text
dominant_clc_code
dominant_clc_label
dominant_clc_share

clc_group

forest_share
wetland_share
agriculture_share
grassland_share
urban_share
water_share
other_natural_share

land_cover_carbon_lookup_score
naturalness_score
afforestation_base_suitability
wetland_base_suitability
urban_or_water_constraint
```

### Processing

1. Download CORINE 2018 100 m raster.
2. Reproject or confirm compatibility with EPSG:3301.
3. Clip to Estonia or the selected county.
4. For every 1 km grid cell:
   - count CORINE pixel classes;
   - calculate dominant class;
   - calculate class proportions;
   - map detailed CORINE classes into simplified groups.

### Simplified CORINE groups

```text
urban
agriculture
forest
wetland
grassland
water
other_natural
other
```

### Example lookup table

| Group | Naturalness | Above-ground carbon fallback | Soil/peat relevance fallback | Notes |
|---|---:|---:|---:|---|
| urban | 0.0 | 0.05 | 0.0 | usually no ecological action |
| agriculture | 0.2 | 0.2 | depends on soil | candidate for afforestation/restoration |
| forest | 0.75 | 0.75 | depends on soil | biomass layer should override carbon fallback |
| wetland / peat bog | 0.9 | 0.4 | 1.0 | soil carbon more important than biomass |
| grassland | 0.55 | 0.25 | depends on soil | may be valuable open habitat |
| water | null | null | null | exclude or no_change |
| other_natural | 0.65 | 0.4 | 0.4 | context dependent |

---

## 4.2 ESA CCI Biomass

### Source

ESA Climate Change Initiative Biomass  
URL: https://climate.esa.int/en/projects/biomass/  
Data portal: https://catalogue.ceda.ac.uk/

### Recommended product

Use the latest available ESA CCI Biomass version, preferably:

```text
ESA CCI Biomass above-ground biomass
Version 7.0 if available
100 m spatial resolution
GeoTIFF preferred
Annual maps, 2005–2012 and 2015–2024
```

If Version 7.0 is not practical to access, use Version 6.0.

### What it contains

ESA CCI Biomass provides:

```text
above-ground biomass, Mg/ha
above-ground biomass uncertainty, Mg/ha
selected change products
quality flags
```

It estimates above-ground woody vegetation biomass, mainly trees and shrubs. It does not estimate peat carbon, soil carbon, below-ground roots, litter, or annual CO₂ emissions.

### Recommended year

For V1.5:

```text
Use 2022, 2023, or latest available year.
```

If combining with CORINE 2018, document the temporal mismatch.

For V2:

```text
Use multiple annual biomass layers:
2018, 2020, 2022, 2024 if available
```

This can support biomass-change indicators.

### Use in this project

Derived fields:

```text
agb_mean_mg_ha
agb_median_mg_ha
agb_p90_mg_ha
agb_max_mg_ha
agb_uncertainty_mean_mg_ha
agb_valid_pixel_share

aboveground_carbon_mean_mg_c_ha
aboveground_co2e_mean_mg_ha
forest_biomass_carbon_score
biomass_uncertainty_score
```

### Conversion

Use a simple documented conversion:

```text
aboveground_carbon_mg_c_ha = agb_mg_ha * 0.47

aboveground_co2e_mg_ha = aboveground_carbon_mg_c_ha * 44 / 12
```

Equivalent:

```text
aboveground_co2e_mg_ha ≈ agb_mg_ha * 1.723
```

### Important limitation

Only use this as a **forest above-ground carbon proxy**.

Do not use low biomass as evidence of low carbon importance, because peatlands and wetlands may have low above-ground biomass but high soil carbon.

---

## 4.3 Peat / soil data

### Preferred source

Estonian Land and Spatial Development Board / Geoportal  
URL: https://geoportaal.maaamet.ee/eng/

Relevant Geoportal sections:

```text
Spatial Data
Estonian Soil Map
Public WMS/WFS services
Geological services / peatlands
```

### Useful access points

Geoportal public WMS/WFS overview:

```text
https://geoportaal.maaamet.ee/eng/services/public-wms-wfs-p346.html
```

General WMS with soil map:

```text
https://kaart.maaamet.ee/wms/alus?
```

Geological / mineral / peatland service mentioned on Geoportal:

```text
https://teenus.maaamet.ee/ows/maardlad
```

The Geoportal page notes that the `maardlad` service includes peatlands described as fixed up, being fixed up, usable, and damaged.

### What to look for

Priority soil/peat fields:

```text
soil_type
peat_soil_indicator
organic_soil_indicator
peatland_polygon
damaged_peatland_indicator
usable_peatland_indicator
drained_or_modified_peatland_indicator if available
soil_texture
soil_moisture_class if available
```

The exact attribute names may differ and must be inspected after download.

### If national soil data is hard to download

Fallback sources:

```text
SoilGrids
European Soil Data Centre
Global peatland/wetland maps
```

But national Estonian soil/peat layers should be preferred.

### Use in this project

Derived fields:

```text
peat_overlap_pct
organic_soil_overlap_pct
dominant_soil_type
peatland_status
soil_carbon_relevance_score
wetland_restoration_soil_score
soil_data_quality_flag
```

### Processing

1. Find/download soil map and peatland layers.
2. Load in QGIS or GeoPandas.
3. Reproject to EPSG:3301.
4. Clip to selected county.
5. For each 1 km cell:
   - compute overlap with peat/organic soil polygons;
   - assign dominant soil type;
   - calculate peat/organic soil share;
   - calculate soil-carbon relevance score.

### Peat/soil score

Example:

```text
soil_carbon_relevance_score =
  1.0 if peat_overlap_pct > 0.5
  0.7 if organic_soil_overlap_pct > 0.3
  0.4 if wetland land cover but no peat layer
  0.2 for mineral forest soils
  0.1 for ordinary agriculture/mineral soils
  0.0 for urban/water/excluded cells
```

### Notes

This layer is essential for wetland restoration. Without peat/soil data, the carbon model will underrepresent soil-carbon and peatland effects.

---

## 4.4 Hydrology data

### Preferred national sources

Estonian Land and Spatial Development Board / Geoportal  
URL: https://geoportaal.maaamet.ee/eng/

Relevant Geoportal services:

```text
Estonian Topographic Database
Public WMS/WFS services
ETAK WFS
```

Public WMS/WFS page lists the Estonian Topographic Database and hydrographic network layers in services. It also lists an ETAK WFS endpoint:

```text
https://gsavalik.envir.ee/geoserver/etak/ows
```

Important: the Geoportal notes that WFS has a 5000-object limit per query and recommends feature paging with page size 5000.

### EELIS / Environmental Portal

URL: https://keskkonnaportaal.ee/en/spatial-data-services-and-use-eelis  
Public service:

```text
https://gsavalik.envir.ee/geoserver/eelis/ows
```

EELIS is useful for protected areas and environmental layers. It may also provide water-related environmental features, depending on available public layers.

### Hydrology features to extract

From topographic / hydrographic layers:

```text
rivers
streams
ditches / drainage channels if available
lakes
ponds
wetlands / marshes if available
shoreline / coast if relevant
```

Derived fields:

```text
distance_to_water_m
distance_to_river_or_stream_m
distance_to_ditch_or_drainage_m
waterbody_overlap_pct
stream_density_1km
ditch_density_1km
hydrological_connectivity_score
wetness_context_score
```

### DEM-derived hydrology

Use DEM together with water layers.

Possible DEM sources:

```text
Estonian elevation data from Geoportal
Copernicus DEM GLO-30
```

Derived DEM features:

```text
elevation_mean
elevation_min
slope_mean
slope_p90
topographic_lowland_score
flow_accumulation_proxy if implemented
terrain_wetness_proxy if implemented
```

For V1.5, simple elevation/slope features are enough. For V2, add proper terrain wetness / flow accumulation if you have time.

### Processing

1. Download or access water/hydrography layers through Geoportal/ETAK WFS.
2. Use paging if using WFS.
3. Reproject to EPSG:3301.
4. Clip to selected county.
5. For each 1 km cell:
   - compute distance to nearest river/stream/waterbody;
   - compute waterbody overlap;
   - compute stream or ditch length inside cell;
   - compute slope/elevation statistics from DEM.
6. Derive hydrology suitability fields.

---

## 5. Combined Carbon-Relevance Model

The combined model should produce two kinds of output:

```text
carbon_stock_score
action_carbon_effect_scores
```

Do not mix these too early.

---

## 5.1 Existing carbon-stock score

Recommended formula:

```text
carbon_stock_score =
  0.45 * forest_aboveground_carbon_score
  + 0.40 * soil_carbon_relevance_score
  + 0.15 * land_cover_carbon_lookup_score
```

Where:

```text
forest_aboveground_carbon_score:
  normalized ESA CCI Biomass AGB, weighted by forest_share

soil_carbon_relevance_score:
  peat/organic soil and wetland indicators

land_cover_carbon_lookup_score:
  CORINE fallback
```

### Alternative if peat/soil layer is weak

```text
carbon_stock_score =
  0.60 * forest_aboveground_carbon_score
  + 0.25 * CORINE wetland/peat fallback
  + 0.15 * land_cover_carbon_lookup_score
```

Add a warning flag:

```text
soil_carbon_data_missing = true
```

---

## 5.2 Protect carbon benefit

Protecting does not create new carbon immediately. It preserves existing high-value carbon and biodiversity areas.

```text
protect_carbon_benefit =
  carbon_stock_score
  * naturalness_score
  * low_opportunity_cost_score
```

Boost if:

```text
protected_overlap_pct > 0
distance_to_protected_area_m is low
forest_share high and AGB high
peat_overlap_pct high
```

---

## 5.3 Afforestation carbon potential

Afforestation should be scored as future above-ground biomass potential, not current stock.

```text
afforestation_carbon_potential =
  low_current_agb_score
  * agriculture_or_degraded_land_score
  * non_wetland_open_habitat_penalty
  * low_population_score
  * low_slope_score
  * non_urban_non_water_mask
```

Rules:

```text
Do not afforest:
  urban cells
  water cells
  high-value wetland cells
  peatland restoration candidates
  valuable open habitats if detected
```

---

## 5.4 Wetland restoration carbon potential

Wetland restoration should be driven by soil/peat and hydrology, not biomass.

```text
wetland_restoration_carbon_potential =
  soil_carbon_relevance_score
  * hydrology_restoration_score
  * wetland_base_suitability
  * low_population_score
  * non_urban_non_water_mask
```

Boost if:

```text
peat_overlap_pct high
distance_to_water_m low
ditch/drainage density high
slope low
CORINE wetland/agriculture/grassland context
near protected wetland
```

Penalize if:

```text
urban_share high
water_share high
slope high
population high
road density high
soil/peat data absent
```

---

## 6. Hydrology Restoration Score

Recommended simple formula:

```text
hydrology_restoration_score =
  0.30 * low_slope_score
  + 0.25 * lowland_score
  + 0.20 * water_proximity_score
  + 0.15 * wetland_neighbor_score
  + 0.10 * ditch_or_drainage_context_score
```

If ditch/drainage layer is unavailable:

```text
hydrology_restoration_score =
  0.35 * low_slope_score
  + 0.30 * lowland_score
  + 0.20 * water_proximity_score
  + 0.15 * wetland_neighbor_score
```

---

## 7. Final Feature Table

Target output:

```text
cell_id
geometry
county
area_m2

# CORINE
dominant_clc_code
dominant_clc_label
dominant_clc_share
clc_group
forest_share
wetland_share
agriculture_share
grassland_share
urban_share
water_share
land_cover_carbon_lookup_score
naturalness_score

# ESA CCI Biomass
agb_mean_mg_ha
agb_median_mg_ha
agb_p90_mg_ha
agb_max_mg_ha
agb_uncertainty_mean_mg_ha
agb_valid_pixel_share
aboveground_carbon_mean_mg_c_ha
aboveground_co2e_mean_mg_ha
forest_aboveground_carbon_score
biomass_uncertainty_score

# Soil / peat
dominant_soil_type
peat_overlap_pct
organic_soil_overlap_pct
peatland_status
soil_carbon_relevance_score
wetland_restoration_soil_score
soil_data_quality_flag

# Hydrology
waterbody_overlap_pct
distance_to_water_m
distance_to_river_or_stream_m
distance_to_ditch_or_drainage_m
stream_density_1km
ditch_density_1km
elevation_mean
elevation_min
slope_mean
slope_p90
lowland_score
low_slope_score
hydrology_restoration_score

# Combined carbon model
carbon_stock_score
protect_carbon_benefit
afforestation_carbon_potential
wetland_restoration_carbon_potential

# Constraints and uncertainty
urban_or_water_constraint
carbon_model_uncertainty_score
missing_data_flags
```

---

## 8. Processing Pipeline

Recommended repository structure:

```text
src/carbon_dataset/
  00_config.yml
  01_prepare_grid.py
  02_process_corine.py
  03_process_biomass.py
  04_process_soil_peat.py
  05_process_hydrology.py
  06_derive_scores.py
  07_export_dataset.py
  08_quality_checks.py
```

Recommended outputs:

```text
data/processed/carbon_v1_5/grid.gpkg
data/processed/carbon_v1_5/corine_features.parquet
data/processed/carbon_v1_5/biomass_features.parquet
data/processed/carbon_v1_5/soil_peat_features.parquet
data/processed/carbon_v1_5/hydrology_features.parquet
data/processed/carbon_v1_5/carbon_features_merged.parquet
data/processed/carbon_v1_5/carbon_features_merged.gpkg
data/processed/carbon_v1_5/metadata.yml
```

---

## 9. Detailed Processing Steps

## 9.1 Prepare grid

Input:

```text
Statistics Estonia 1 km population grid
```

Steps:

```text
1. Load grid.
2. Reproject to EPSG:3301.
3. Clip to selected county.
4. Add stable cell_id.
5. Store geometry area.
```

Output:

```text
grid.gpkg
```

---

## 9.2 Process CORINE

Input:

```text
CORINE 2018 100 m raster GeoTIFF
```

Steps:

```text
1. Open with rasterio.
2. Clip to county bounding box.
3. For each 1 km grid cell:
   - extract raster pixels under polygon;
   - ignore nodata;
   - count CLC classes;
   - calculate dominant class and class shares.
4. Map CLC codes to simplified groups.
5. Derive lookup scores.
```

Output:

```text
corine_features.parquet
```

Quality checks:

```text
dominant_clc_code not null for land cells
class shares sum to 1 or near 1
water cells identified
urban cells identified
```

---

## 9.3 Process ESA CCI Biomass

Input:

```text
ESA CCI Biomass AGB GeoTIFF
ESA CCI Biomass uncertainty GeoTIFF
optional quality flags
```

Steps:

```text
1. Select year.
2. Load AGB raster.
3. Load uncertainty raster.
4. Reproject or align to EPSG:3301 if needed.
5. Clip to county.
6. For each 1 km grid cell:
   - calculate mean, median, p90, max AGB;
   - calculate uncertainty mean;
   - calculate valid pixel share.
7. Convert AGB to carbon and CO2e proxy.
8. Normalize AGB to score 0–1.
9. Mask or downweight using forest_share from CORINE.
```

Output:

```text
biomass_features.parquet
```

Suggested scoring:

```text
forest_aboveground_carbon_score =
  normalized(agb_mean_mg_ha) * forest_share_adjustment
```

Where:

```text
forest_share_adjustment = min(1, forest_share / 0.5)
```

---

## 9.4 Process soil / peat

Input:

```text
Estonian Soil Map
Peatland / geological layers
optional organic soil layers
```

Steps:

```text
1. Download/access national soil and peat layers.
2. Inspect schema manually in QGIS.
3. Identify attributes for soil type, peat, organic soils, peatland status.
4. Reproject to EPSG:3301.
5. Clip to county.
6. Overlay with 1 km grid.
7. Calculate overlap percentages.
8. Assign dominant soil type.
9. Derive soil_carbon_relevance_score.
```

Output:

```text
soil_peat_features.parquet
```

Quality checks:

```text
peat_overlap_pct between 0 and 1
organic_soil_overlap_pct between 0 and 1
dominant_soil_type populated where soil layer exists
soil_data_quality_flag set if missing/ambiguous
```

---

## 9.5 Process hydrology

Input:

```text
ETAK hydrographic network
water bodies
rivers/streams
ditches/drainage if available
DEM
```

Steps:

```text
1. Download waterbody and hydrographic line layers.
2. Download or prepare DEM.
3. Reproject all layers to EPSG:3301.
4. Clip to county.
5. For each grid cell:
   - compute waterbody overlap;
   - compute distance to nearest water;
   - compute river/stream length per cell;
   - compute ditch/drainage length per cell if available;
   - aggregate DEM elevation and slope statistics.
6. Derive hydrology_restoration_score.
```

Output:

```text
hydrology_features.parquet
```

Quality checks:

```text
distances non-negative
waterbody overlap valid
slope values reasonable
hydrology score 0–1
```

---

## 10. Combined Scoring

After all feature tables are built, merge by `cell_id`.

### Normalization

Use robust normalization:

```text
score = clip((x - p5) / (p95 - p5), 0, 1)
```

Prefer percentiles over min/max to avoid outlier domination.

### Missing data

For every source, create missing flags:

```text
missing_corine
missing_biomass
missing_soil
missing_hydrology
missing_dem
```

Then create:

```text
carbon_model_uncertainty_score =
  0.35 * biomass_uncertainty_score
  + 0.35 * missing_soil_penalty
  + 0.20 * missing_hydrology_penalty
  + 0.10 * low_valid_pixel_penalty
```

---

## 11. Action-Relevance Outputs

For the neuroevolution simulator, export action-specific scoring columns:

```text
score_no_change_carbon
score_protect_carbon
score_restore_wetland_carbon
score_afforest_carbon
```

Example:

```text
score_no_change_carbon = 0

score_protect_carbon =
  protect_carbon_benefit

score_restore_wetland_carbon =
  wetland_restoration_carbon_potential

score_afforest_carbon =
  afforestation_carbon_potential
```

The simulator can then combine these with biodiversity, cost, and constraint objectives.

---

## 12. Validation and Sanity Checks

### Map checks

Create maps for:

```text
dominant CLC group
forest_share
wetland_share
AGB mean
AGB uncertainty
peat_overlap_pct
soil_carbon_relevance_score
distance_to_water
hydrology_restoration_score
carbon_stock_score
afforestation_carbon_potential
wetland_restoration_carbon_potential
```

### Statistical checks

Check:

```text
High AGB cells mostly overlap forest_share > 0
Wetland restoration potential is not high in urban/water cells
Afforestation potential is not high in wetlands or water
Peat overlap strongly increases soil carbon relevance
Cells with high missing data have high uncertainty
```

### Manual inspection

Manually inspect 20–50 cells:

```text
high forest carbon
high wetland restoration potential
high afforestation potential
urban cells
water cells
protected wetlands
```

Use QGIS and satellite imagery to check if outputs look plausible.

---

## 13. Known Limitations

### CORINE

```text
2018 land cover may be outdated.
100 m resolution is coarse but usable for 1 km aggregation.
Class labels are broad and may not capture local management.
```

### ESA CCI Biomass

```text
Estimates above-ground woody biomass only.
Does not capture soil carbon or peat carbon.
Uncertainty must be used.
Forest carbon is not the same as annual CO2 flux.
```

### Soil / peat

```text
National layers may require manual schema inspection.
Peat/drainage status may be incomplete.
Soil carbon stock may not be directly available and may need proxies.
```

### Hydrology

```text
Water proximity and slope do not fully represent restoration feasibility.
Drainage data may be incomplete.
True water-table restoration requires more detailed hydrological modelling.
```

### Overall

```text
The output is a carbon-relevance and action-suitability proxy dataset.
It is not an official carbon accounting product.
It should not be used as planning advice without expert validation.
```

---

## 14. Source Links

```text
CORINE Land Cover:
https://land.copernicus.eu/en/products/corine-land-cover

ESA CCI Biomass:
https://climate.esa.int/en/projects/biomass/

ESA CCI Biomass data portal:
https://catalogue.ceda.ac.uk/

Estonian Geoportal:
https://geoportaal.maaamet.ee/eng/

Estonian Geoportal public WMS/WFS:
https://geoportaal.maaamet.ee/eng/services/public-wms-wfs-p346.html

EELIS spatial data services:
https://keskkonnaportaal.ee/en/spatial-data-services-and-use-eelis

EELIS public WMS/WFS:
https://gsavalik.envir.ee/geoserver/eelis/ows

ETAK public WMS/WFS:
https://gsavalik.envir.ee/geoserver/etak/ows

Geological / peatland service:
https://teenus.maaamet.ee/ows/maardlad
```

---

## 15. Recommended First Implementation

For the first working implementation, do this:

```text
1. Use 1 km grid.
2. Process CORINE raster.
3. Process ESA CCI Biomass AGB + uncertainty.
4. Add soil/peat using the best available national layer.
5. Add basic hydrology: water distance + slope + lowland score.
6. Derive carbon_stock_score.
7. Derive protect, afforest, and wetland restoration carbon potentials.
8. Export one GeoPackage and one Parquet.
9. Validate visually in QGIS.
```

Do not start with complex CO2 flux modelling. First build a transparent, inspectable feature layer.
