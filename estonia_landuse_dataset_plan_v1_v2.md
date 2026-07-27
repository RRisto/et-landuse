# Estonia Neuroevolution Land-Use Demo: Dataset Plan

**Purpose:** Build a staged dataset roadmap for an Estonia land-use neuroevolution demo inspired by Project Resilience / ELUC, but localized to Estonian spatial data.

**Project framing:**  
The first version should be a transparent decision-support sandbox, not a claim to produce authoritative land-use planning recommendations. The dataset should support a simulator that explores trade-offs between biodiversity proxy, carbon proxy, connectivity, restoration cost, opportunity cost, and constraint violations.

---

## 1. Dataset Strategy

The dataset should be built in two stages:

- **V1: Practical demo dataset**
  - One Estonian county or municipality.
  - 1 × 1 km grid.
  - Small number of robust, easy-to-explain features.
  - Simple proxy-based simulator.
  - Main goal: make neuroevolution visible and testable.

- **V2: Research-grade extension**
  - Larger spatial coverage, ideally all Estonia.
  - More ecological, economic, hydrological, forestry, climate, and biodiversity layers.
  - Stronger validation and uncertainty handling.
  - Main goal: improve realism and credibility.

---

## 2. Recommended Demo Area

### Preferred V1 area

Choose one county:

1. **Lääne County**
   - Good for wetlands, protected areas, coast, bird habitats, and restoration logic.
2. **Pärnu County**
   - Good for wetlands, forests, agriculture, coastal areas, and larger spatial variety.
3. **Tartu County**
   - Good balanced mix of city, agriculture, forests, and wetlands.
4. **Harju County**
   - Good if the demo should include urban pressure, roads, and development trade-offs.

### Recommendation

For the first demo, choose **Lääne County** or **Pärnu County**.

Reason: restoration, protection, carbon, wetlands, and biodiversity trade-offs are easier to explain visually.

---

## 3. V1 Dataset Plan: Minimum Practical Demo

### V1 goal

Create a single `features_v1.parquet` / `features_v1.gpkg` file where each row is one 1 × 1 km grid cell.

The file should contain enough features to support four land-use actions:

```text
0. no_change
1. protect
2. restore_wetland
3. afforest
```

### V1 output table

Target columns:

```text
cell_id
geometry
county_or_municipality
area_m2

population_total
land_cover_class
land_cover_group
naturalness_score
carbon_score

protected_overlap_pct
distance_to_protected_area_m

distance_to_road_m
distance_to_settlement_m

elevation_mean
slope_mean
wetland_suitability

biodiversity_proxy
opportunity_cost_proxy
constraint_mask
```

---

## 4. V1 Sources

### 4.1 Base grid and population

**Source:** Statistics Estonia spatial data  
**URL:** https://www.stat.ee/en/find-statistics/spatial-data

Statistics Estonia publishes INSPIRE 1 × 1 km grid maps covering Estonia. The population grid is available in SHP and CSV formats and includes population per cell.

Use this as the **base grid** for V1.

**Use in project:**

```text
cell_id
geometry
population_total
population_density
urban_pressure_proxy
opportunity_cost_proxy
```

**Recommended file:**

- Estonian population 1 × 1 km grid map in EPSG:3301 projection
- Use the latest available year.
- EPSG:3301 is convenient for Estonian spatial processing.

**Processing steps:**

1. Download SHP or CSV.
2. Load with GeoPandas.
3. Clip to selected county.
4. Keep grid geometry and population fields.
5. Use as the master grid for all joins.

---

### 4.2 Land cover

**Source:** Copernicus CORINE Land Cover  
**URL:** https://land.copernicus.eu/en/products/corine-land-cover

CORINE Land Cover provides a pan-European land-cover / land-use inventory with 44 thematic classes. The latest CLC update listed on the Copernicus page is 2018.

**Use in project:**

```text
land_cover_class
land_cover_group
naturalness_score
carbon_score
wetland_candidate
forest_candidate
agriculture_candidate
urban_constraint
```

**V1 simplification:**

Map detailed CORINE classes into simplified groups:

```text
urban
agriculture
forest
wetland
grassland
water
other_natural
```

**Example scoring:**

| Land-cover group | Naturalness score | Carbon score | Notes |
|---|---:|---:|---|
| Urban | 0.0 | 0.1 | Hard constraint: no ecological intervention in V1 |
| Agriculture | 0.2 | 0.3 | Candidate for restoration or afforestation |
| Forest | 0.7 | 0.8 | Candidate for protection |
| Wetland / peat bog | 0.9 | 1.0 | Candidate for protection/restoration |
| Grassland | 0.6 | 0.4 | Be careful: may be valuable open habitat |
| Water | null | null | Exclude from action space |

**Processing steps:**

1. Download CORINE raster/vector.
2. Reproject to EPSG:3301.
3. For each 1 km grid cell, calculate dominant class and class proportions.
4. Add simplified land-cover group.
5. Add proxy scores using lookup table.

---

### 4.3 Protected areas and conservation constraints

**Source:** EELIS / Estonian Environmental Portal  
**URL:** https://keskkonnaportaal.ee/en/spatial-data-services-and-use-eelis  
**Public WMS/WFS endpoint:** https://gsavalik.envir.ee/geoserver/eelis/ows

EELIS public WMS/WFS layers can be used for spatial planning, environmental impact assessment, and nature-conservation decision-making. Sensitive species data, such as category I and II protected species locations and habitats, is not publicly available via public services.

**Use in project:**

```text
protected_overlap_pct
distance_to_protected_area_m
constraint_mask
connectivity_target
biodiversity_proxy_component
```

**V1 use:**

- Use public protected-area polygons.
- Do not use restricted species layers.
- Treat protected-area overlap as both:
  - a positive biodiversity/connectivity signal;
  - a constraint, depending on action.

**Processing steps:**

1. Connect to public WFS.
2. Download protected-area polygons for selected county.
3. Reproject to EPSG:3301.
4. Compute overlap percentage per grid cell.
5. Compute distance to nearest protected area.
6. Add constraint flags.

---

### 4.4 Roads and settlements

**Source:** OpenStreetMap Estonia extract via Geofabrik  
**URL:** https://download.geofabrik.de/europe/estonia.html

Geofabrik provides Estonia OpenStreetMap extracts in `.osm.pbf`, SHP, and GeoPackage formats. The GeoPackage is the easiest option for GeoPandas.

**Recommended V1 file:**

```text
estonia-latest-free.gpkg.zip
```

**Use in project:**

```text
distance_to_road_m
distance_to_settlement_m
fragmentation_proxy
accessibility_proxy
opportunity_cost_proxy
```

**V1 use:**

- Roads: calculate distance to nearest major road.
- Settlements / buildings / urban landuse: calculate settlement proximity.
- Use these as rough proxies for intervention cost and fragmentation.

**Processing steps:**

1. Download GeoPackage from Geofabrik.
2. Extract roads and settlement/building/urban layers.
3. Filter roads to relevant classes if needed.
4. Reproject to EPSG:3301.
5. Compute distances from each grid centroid.

---

### 4.5 Elevation and slope

**Source:** Copernicus DEM GLO-30  
**URL:** https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

Copernicus DEM GLO-30 is suitable for deriving elevation and slope. For the first demo, it is enough for broad wetland-suitability and slope constraints.

**Use in project:**

```text
elevation_mean
slope_mean
lowland_score
wetland_suitability
```

**V1 use:**

- Low elevation and low slope increase wetland-restoration suitability.
- High slope reduces wetland-restoration feasibility.
- Optional in V1; useful if you want more believable wetland restoration.

**Processing steps:**

1. Download DEM tiles for selected county.
2. Mosaic and clip.
3. Reproject if needed.
4. Calculate slope raster.
5. Aggregate mean elevation and mean slope per 1 km cell.

---

## 5. V1 Derived Features

### 5.1 Naturalness score

Derived from land cover and protected-area context.

Example:

```text
naturalness_score =
  land_cover_naturalness_lookup
  + protected_area_bonus
  + road_distance_bonus
```

Normalize to 0–1.

---

### 5.2 Carbon score

Derived from land-cover class.

Example:

```text
wetland / peat bog: high
forest: high
grassland: medium
agriculture: low-medium
urban: low
water: excluded
```

This is only a proxy, not real carbon accounting.

---

### 5.3 Biodiversity proxy

V1 should not pretend to model true biodiversity.

Recommended V1 proxy:

```text
biodiversity_proxy =
  0.40 * naturalness_score
  + 0.30 * protected_area_score
  + 0.20 * habitat_diversity_score
  + 0.10 * road_distance_score
```

Where:

```text
protected_area_score = protected_overlap_pct or inverse distance to protected area
habitat_diversity_score = number/diversity of land-cover groups in neighboring cells
road_distance_score = higher if farther from major roads
```

---

### 5.4 Wetland suitability

Example:

```text
wetland_suitability =
  0.40 * wetland_or_near_wetland_score
  + 0.25 * low_slope_score
  + 0.20 * lowland_score
  + 0.15 * distance_to_water_or_wetland_score
```

For V1, this can be simplified to:

```text
wetland_suitability =
  land_cover_wetland_candidate_score
  + low_slope_score
  + low_elevation_score
```

---

### 5.5 Opportunity cost proxy

V1 proxy:

```text
urban / settlement nearby: very high
high population: high
agriculture: medium-high
commercial forest: medium
semi-natural grassland: medium
wetland/natural land: low
already protected: low economic change potential but high legal constraint
```

This should be labelled as **opportunity-cost proxy**, not true economic value.

---

### 5.6 Constraint mask

Examples:

```text
water cell -> no action
urban cell -> only no_change
already protected + high biodiversity -> protect/no_change preferred
high slope -> no wetland restoration
high population -> no restoration/afforestation
```

---

## 6. V1 Dataset Build Pipeline

Recommended scripts:

```text
src/data_v1/
  01_download_sources.md
  02_make_base_grid.py
  03_add_land_cover.py
  04_add_protected_areas.py
  05_add_osm_features.py
  06_add_dem_features.py
  07_derive_proxy_scores.py
  08_export_features.py
```

Recommended outputs:

```text
data/processed/v1/base_grid.gpkg
data/processed/v1/features_v1.parquet
data/processed/v1/features_v1.gpkg
data/processed/v1/metadata_v1.yml
data/processed/v1/proxy_score_lookups.yml
```

---

## 7. V1 Quality Checks

Before using the dataset in neuroevolution:

### Geometry checks

```text
all geometries valid
all layers in EPSG:3301
no duplicated cell_id
county clip is correct
water cells identified/excluded
```

### Feature checks

```text
population_total non-negative
land_cover_class not missing for land cells
protected_overlap_pct between 0 and 1
distances non-negative
proxy scores between 0 and 1
constraint masks consistent
```

### Map checks

Create quick maps for:

```text
land_cover_group
population_total
protected_overlap_pct
distance_to_road_m
naturalness_score
carbon_score
biodiversity_proxy
wetland_suitability
```

---

## 8. V1 Simulator Support

The V1 dataset should support a simple simulator with four actions.

### Action: no_change

Allowed everywhere except excluded cells.

Effects:

```text
biodiversity_delta = 0
carbon_delta = 0
cost = 0
constraint_penalty = 0
```

---

### Action: protect

Good when:

```text
high biodiversity_proxy
high naturalness_score
near or inside protected area
low opportunity_cost_proxy
```

Effects:

```text
biodiversity_gain = positive if high biodiversity_proxy
connectivity_gain = positive if near protected area
cost = low-medium
```

---

### Action: restore_wetland

Good when:

```text
wetland_suitability high
current land cover is agriculture, degraded wetland, grassland, or low-value open land
low population
low slope
near existing wetland/protected area
```

Effects:

```text
carbon_gain = high if wetland_suitability high
biodiversity_gain = medium-high
cost = medium-high
constraint_penalty = high if urban/water/high-slope/high-population
```

---

### Action: afforest

Good when:

```text
current land cover is low-value agriculture or degraded land
not valuable open habitat
low population
near existing forest
```

Effects:

```text
carbon_gain = medium-high
biodiversity_gain = context-dependent
cost = medium
constraint_penalty = high if wetland/open habitat/urban/water
```

---

## 9. V2 Dataset Plan: Research-Grade Extension

V2 should expand from a demo proxy dataset to a more realistic decision-support dataset.

### V2 goals

```text
cover all Estonia
improve biodiversity representation
improve carbon and soil representation
improve forestry/agriculture opportunity cost
add hydrology and flood risk
add climate scenarios
add uncertainty and validation layers
```

---

## 10. V2 Additional Sources

### 10.1 Biodiversity observations

**Sources:**

- eElurikkus: https://elurikkus.ee/en
- GBIF: https://www.gbif.org

**Use:**

```text
species_observation_density
taxon_group_richness
red-listed species indicator if legally/publicly available
observation_effort_proxy
```

**Important caution:**

Observation density is biased by human activity and sampling effort. Use it carefully, preferably as one component of biodiversity proxy, not the whole proxy.

---

### 10.2 Natura 2000

**Source:** European Environment Agency  
**URL:** https://www.eea.europa.eu/en/datahub/datahubitem-view/6fc8ad2d-195d-40f4-bdec-576e7d1268e4

**Use:**

```text
natura2000_overlap
habitat_directive_site
bird_directive_site
connectivity_target
constraint_layer
```

---

### 10.3 Soil and peatland data

**Possible sources:**

- Estonian national soil data / Geoportal / Land and Spatial Development Board
- Environmental Portal open data
- European Soil Data Centre where useful

**Use:**

```text
soil_type
peat_soil_indicator
organic_soil_indicator
drainage_sensitivity
carbon_stock_proxy
wetland_restoration_potential
```

This is one of the most important V2 upgrades because wetland restoration and carbon scoring depend heavily on soil and peat.

---

### 10.4 Hydrology and water bodies

**Possible sources:**

- Estonian Geoportal / Maa-amet
- Environmental Portal / EELIS
- OpenStreetMap as fallback

**Use:**

```text
distance_to_water_m
river_or_stream_density
floodplain_proxy
drainage_network_proxy
wetland_restoration_suitability
```

---

### 10.5 Forest data

**Possible sources:**

- Estonian forest register / Metsaportaal, depending on access and license
- Environmental Portal forest statistics
- Copernicus High Resolution Layers: Tree Cover Density, Forest Type

**Use:**

```text
forest_type
tree_cover_density
forest_continuity_proxy
forest_management_proxy
carbon_stock_proxy
afforestation_suitability
```

---

### 10.6 Agriculture and land value

**Possible sources:**

- Statistics Estonia
- Agricultural registers if accessible
- Land parcel / cadastral data if license allows
- Soil productivity / land quality layers if available

**Use:**

```text
agriculture_value_proxy
crop_land_indicator
opportunity_cost_proxy
food-production trade-off
```

---

### 10.7 Climate and flood scenarios

**Sources:**

- Copernicus Climate Data Store: https://cds.climate.copernicus.eu/
- Estonian climate atlas / Environmental Portal where useful

**Use:**

```text
future_temperature_scenario
precipitation_change
drought_risk
flood_risk
climate_resilience_score
```

V2 can support scenarios such as:

```text
current climate
wet future
dry future
high flood-risk future
```

---

### 10.8 Higher-resolution land cover / satellite data

**Sources:**

- ESA WorldCover: https://worldcover2021.esa.int/
- Copernicus High Resolution Layers
- Sentinel-2 / ESTHub

**Use:**

```text
10 m land cover
tree cover
imperviousness
grassland/wetland refinement
recent land-cover change
```

V2 can improve spatial precision from 1 km to 250 m or 100 m.

---

## 11. V2 Feature Table

Target V2 columns:

```text
cell_id
geometry
admin_unit
area_m2

land_cover_class
land_cover_group
land_cover_proportions
tree_cover_density
imperviousness

population_total
population_density
distance_to_settlement_m
distance_to_road_m

protected_overlap_pct
natura2000_overlap_pct
distance_to_protected_area_m

species_observation_density
taxon_group_richness
observation_effort_proxy
biodiversity_proxy_v2

soil_type
peat_soil_indicator
organic_soil_indicator
carbon_stock_proxy
carbon_gain_potential

elevation_mean
slope_mean
distance_to_water_m
wetland_suitability_v2
flood_risk

forest_type
forest_continuity_proxy
afforestation_suitability

agriculture_value_proxy
forestry_value_proxy
opportunity_cost_proxy_v2

climate_scenario
climate_resilience_score

constraint_mask
uncertainty_score
```

---

## 12. V2 Simulator Improvements

### V1 simulator

Proxy-based:

```text
simple lookup scores
rule-based constraints
spatial adjacency penalty
basic Pareto objectives
```

### V2 simulator

More realistic:

```text
carbon stock and carbon gain differentiated by soil/peat/forest type
biodiversity score adjusted for sampling effort
connectivity modeled with graph/network methods
wetland restoration constrained by soil/hydrology
opportunity cost based on land use and economic proxies
scenario-dependent climate resilience
uncertainty score for each recommendation
```

---

## 13. V1 vs V2 Summary

| Area | V1 | V2 |
|---|---|---|
| Spatial extent | One county | All Estonia or multiple counties |
| Resolution | 1 km | 1 km, 250 m, or 100 m |
| Land cover | CORINE | CORINE + WorldCover/HRL/Sentinel |
| Biodiversity | Proxy only | Observations + protected areas + habitat proxies |
| Carbon | Land-cover lookup | Soil/peat/forest-aware carbon proxy |
| Economy | Opportunity-cost proxy | Agriculture/forestry/land-value proxies |
| Hydrology | DEM-based wetland suitability | DEM + water + soil + flood risk |
| Climate | Not required | Scenario layers |
| Actions | 4 actions | 6+ actions |
| Validation | Baselines and sanity checks | Baselines + expert review + uncertainty |
| Claim | Demo / sandbox | Research prototype |

---

## 14. Recommended Implementation Order

### Stage 1: Base grid

```text
Download Statistics Estonia 1 km population grid
Clip to selected county
Export base_grid.gpkg
```

### Stage 2: Land cover

```text
Download CORINE
Reproject to EPSG:3301
Assign dominant land-cover class to grid cells
Create land_cover_group
```

### Stage 3: Protected areas

```text
Fetch EELIS public protected-area layers
Compute protected overlap and distance
Add conservation constraint fields
```

### Stage 4: OSM features

```text
Download Estonia GeoPackage from Geofabrik
Extract roads and settlements
Compute distance features
```

### Stage 5: DEM features

```text
Download Copernicus DEM GLO-30
Compute elevation and slope
Aggregate to grid
```

### Stage 6: Proxy features

```text
Create naturalness_score
Create carbon_score
Create biodiversity_proxy
Create wetland_suitability
Create opportunity_cost_proxy
Create constraint_mask
```

### Stage 7: Export

```text
features_v1.parquet
features_v1.gpkg
metadata_v1.yml
lookup_tables.yml
```

---

## 15. Dataset Documentation Template

Each dataset should have a small metadata entry:

```yaml
dataset_name:
  source_name:
  source_url:
  download_date:
  license:
  raw_format:
  processed_format:
  crs_original:
  crs_processed: EPSG:3301
  spatial_resolution:
  temporal_coverage:
  fields_used:
  processing_steps:
  known_limitations:
```

---

## 16. Key Limitations to Document

### V1 limitations

```text
Biodiversity is a proxy, not a true ecological model.
Carbon is a proxy derived mainly from land cover.
Opportunity cost is approximate.
Protected species restricted data is not used.
Hydrology is simplified.
Recommendations are not planning advice.
```

### V2 limitations

```text
Species observations are biased by sampling effort.
Economic value may remain approximate.
Carbon estimates require domain validation.
Climate scenario uncertainty must be communicated.
Higher resolution increases compute and data harmonization complexity.
```

---

## 17. Final Recommended V1 Dataset

For the first working demo, build only this:

```text
Base grid:
  Statistics Estonia 1 × 1 km population grid

Land cover:
  CORINE Land Cover

Protected areas:
  EELIS public WFS protected-area layers

Infrastructure:
  OpenStreetMap Estonia GeoPackage from Geofabrik

Optional but useful:
  Copernicus DEM GLO-30
```

This is enough to build:

```text
one-county feature table
simple simulator
NSGA-II evolved policies
Pareto frontier
interactive map dashboard
```

---

## 18. Source Links

```text
Statistics Estonia spatial data:
https://www.stat.ee/en/find-statistics/spatial-data

Copernicus CORINE Land Cover:
https://land.copernicus.eu/en/products/corine-land-cover

EELIS spatial data services:
https://keskkonnaportaal.ee/en/spatial-data-services-and-use-eelis

EELIS public WMS/WFS:
https://gsavalik.envir.ee/geoserver/eelis/ows

Geofabrik Estonia OpenStreetMap extracts:
https://download.geofabrik.de/europe/estonia.html

Copernicus DEM:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

eElurikkus:
https://elurikkus.ee/en

GBIF:
https://www.gbif.org

ESA WorldCover:
https://worldcover2021.esa.int/

Copernicus Climate Data Store:
https://cds.climate.copernicus.eu/
```
