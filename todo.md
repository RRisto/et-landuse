# TODO — Scientific validation of restoration suitability models

The current hydrology restoration score and wetland restoration carbon potential use heuristic proxy weights (not empirically calibrated). These papers provide scientifically grounded approaches that could replace or validate our formulas.

## Priority: review and evaluate

### GIS-based wetland restoration suitability

1. **Identifying Feasible Locations for Wetland Creation or Restoration in Catchments by Suitability Modelling Using LiDAR DEM** (2018)
   - https://www.mdpi.com/2073-4441/10/4/464
   - Uses DEM-derived slope, flow accumulation, terrain wetness index
   - Relevant for replacing our proxy `low_slope_score` and `lowland_score` with proper TWI

2. **A Multi-Criteria Wetland Suitability Index for Restoration across Ontario's Mixedwood Plains** (2020)
   - https://www.mdpi.com/2071-1050/12/23/9953
   - Multi-criteria weighted index with justified variable selection and weights
   - Could inform better weight choices for `hydrology_restoration_score`

3. **Comparing Two Multi-Criteria Methods for Prioritizing Wetland Restoration Sites** (2017)
   - https://link.springer.com/article/10.1007/s11269-017-1572-2
   - Uses terrain slope, proximity to watercourses, soil permeability
   - Same factors as ours but with validated weights

4. **Prioritizing Wetland Restoration Sites: A Review and Application to a Large-Scale Coastal Restoration Program** (2015)
   - https://muse.jhu.edu/article/597362
   - Literature review of GIS-based prioritization models
   - Key finding: no consensus on variables/weights across studies — our heuristic approach is common

5. **Development and Application of an Automated GIS Based Evaluation to Prioritize Wetland Restoration Opportunities** (2010)
   - https://link.springer.com/article/10.1007/s13157-010-0061-7
   - Three-tier weighted summation approach, scored 0–1
   - Similar methodology to ours

### Peatland + carbon specific

6. **Water-table-driven greenhouse gas emission estimates guide peatland restoration at national scale** (2023)
   - https://bg.copernicus.org/articles/20/2387/2023/
   - Links water table depth directly to CO₂/CH₄ emissions
   - Most scientifically rigorous approach — if water table data is available for Estonia, this could replace our proxy entirely

7. **Assessment and Spatial Planning for Peatland Conservation and Restoration** (2021)
   - https://www.mdpi.com/2073-445X/10/2/174
   - GIS-based peatland prioritization framework

8. **A call for refining the peatland restoration strategy in Europe** (2022)
   - https://www.researchgate.net/publication/362721711_A_call_for_refining_the_peatland_restoration_strategy_in_Europe
   - Discusses three approaches: inundation, topsoil removal, slow rewetting
   - Implications for climate, nutrient fluxes, biodiversity

### Baltic region / EU projects

9. **LIFE PeatCarbon — Peatland restoration for GHG emission reduction in the Baltic Sea region** (Latvia, active EU project)
   - https://webgate.ec.europa.eu/life/publicWebsite/project/LIFE21-CCM-LV-LIFE-PeatCarbon-101074396
   - Directly relevant — Baltic climate/peat context similar to Estonia
   - May publish methodology and calibration data

### Carbon in blue/coastal wetlands

10. **Seas the opportunity: multi-criteria decision analysis to identify and prioritise blue carbon wetland restoration sites** (2024)
    - https://www.frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2024.1431027/full
    - MCDA approach for carbon-focused restoration prioritization
    - Different ecosystem but relevant methodology

## What to do with these

- [ ] Read papers #1, #2, #6 in detail — most relevant to our model
- [ ] Check if any provide weight calibration methodology we can adopt
- [ ] Look for water table depth data for Estonia (paper #6 approach)
- [ ] Consider sensitivity analysis: how much do our scores change if we vary the weights?
- [ ] Check LIFE PeatCarbon outputs for Baltic-specific calibration data
- [ ] Document which assumptions are defensible vs which need replacement
