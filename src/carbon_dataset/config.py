"""Carbon dataset pipeline configuration."""

from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_V1 = PROJECT_ROOT / "data" / "processed" / "v1"
DATA_PROCESSED_CARBON = PROJECT_ROOT / "data" / "processed" / "carbon_v1_5"

# Input paths
BASE_GRID_PATH = DATA_PROCESSED_V1 / "base_grid.gpkg"
CORINE_TIF = DATA_RAW / "corine" / "87080" / "Results" / "u2018_clc2018_v2020_20u1_raster100m" / "u2018_clc2018_v2020_20u1_raster100m" / "DATA" / "U2018_CLC2018_V2020_20u1.tif"
BIOMASS_DIR = DATA_RAW / "esa_cci_biomass"

# CRS
CRS = "EPSG:3301"

# Demo county
COUNTY_NAME = "Lääne"

# --- CORINE lookup tables ---
# CORINE pixel value -> standard CLC code
CORINE_PIXEL_TO_CODE = {
    1: 111, 2: 112, 3: 121, 4: 122, 5: 123, 6: 124,
    7: 131, 8: 132, 9: 133, 10: 141, 11: 142,
    12: 211, 13: 212, 14: 213, 15: 221, 16: 222, 17: 223,
    18: 231, 19: 241, 20: 242, 21: 243, 22: 244,
    23: 311, 24: 312, 25: 313,
    26: 321, 27: 322, 28: 323, 29: 324,
    30: 331, 31: 332, 32: 333, 33: 334, 34: 335,
    35: 411, 36: 412, 37: 421, 38: 422, 39: 423,
    40: 511, 41: 512, 42: 521, 43: 522, 44: 523,
}

# CLC code -> simplified group
CORINE_TO_GROUP = {
    111: "urban", 112: "urban", 121: "urban", 122: "urban",
    123: "urban", 124: "urban", 131: "urban", 132: "urban",
    133: "urban", 141: "urban", 142: "urban",
    211: "agriculture", 212: "agriculture", 213: "agriculture",
    221: "agriculture", 222: "agriculture", 223: "agriculture",
    231: "grassland", 241: "agriculture", 242: "agriculture",
    243: "agriculture", 244: "agriculture",
    311: "forest", 312: "forest", 313: "forest",
    321: "grassland", 322: "grassland", 323: "grassland",
    324: "forest",
    331: "other_natural", 332: "other_natural", 333: "other_natural",
    334: "other_natural", 335: "other_natural",
    411: "wetland", 412: "wetland", 421: "wetland", 422: "wetland", 423: "wetland",
    511: "water", 512: "water", 521: "water", 522: "water", 523: "water",
}

ALL_GROUPS = ["urban", "agriculture", "grassland", "forest", "wetland", "water", "other_natural"]

# --- Carbon-relevance lookup scores (from spec Table 4.1) ---
# These serve as fallback when biomass/soil layers are unavailable.
LAND_COVER_CARBON_LOOKUP = {
    "urban": 0.05,
    "agriculture": 0.2,
    "grassland": 0.25,
    "forest": 0.75,
    "wetland": 0.4,
    "water": 0.0,
    "other_natural": 0.4,
}

NATURALNESS_LOOKUP = {
    "urban": 0.0,
    "agriculture": 0.2,
    "grassland": 0.55,
    "forest": 0.75,
    "wetland": 0.9,
    "water": 0.0,
    "other_natural": 0.65,
}

# Soil/peat relevance fallback (when no dedicated soil layer)
SOIL_PEAT_RELEVANCE_FALLBACK = {
    "urban": 0.0,
    "agriculture": 0.1,
    "grassland": 0.2,
    "forest": 0.2,
    "wetland": 1.0,
    "water": 0.0,
    "other_natural": 0.4,
}

# Afforestation base suitability by group
AFFORESTATION_BASE_SUITABILITY = {
    "urban": 0.0,
    "agriculture": 0.7,
    "grassland": 0.6,
    "forest": 0.0,   # already forest
    "wetland": 0.0,  # don't afforest wetlands
    "water": 0.0,
    "other_natural": 0.3,
}

# Wetland restoration base suitability by group
WETLAND_BASE_SUITABILITY = {
    "urban": 0.0,
    "agriculture": 0.4,
    "grassland": 0.5,
    "forest": 0.2,
    "wetland": 0.8,  # partial wetland cells can be restored further
    "water": 0.0,
    "other_natural": 0.3,
}

# --- Normalization ---
# Use percentile-based robust normalization
NORM_LOWER_PERCENTILE = 5
NORM_UPPER_PERCENTILE = 95

# --- Carbon stock score weights (Section 5.1 of spec) ---
# When all layers are available:
CARBON_STOCK_WEIGHTS_FULL = {
    "forest_aboveground_carbon_score": 0.45,
    "soil_carbon_relevance_score": 0.40,
    "land_cover_carbon_lookup_score": 0.15,
}
# When soil/peat layer is missing:
CARBON_STOCK_WEIGHTS_NO_SOIL = {
    "forest_aboveground_carbon_score": 0.60,
    "corine_wetland_peat_fallback": 0.25,
    "land_cover_carbon_lookup_score": 0.15,
}

# --- Biomass conversion ---
# AGB (Mg/ha) -> carbon (Mg C/ha)
AGB_TO_CARBON_FACTOR = 0.47
# Carbon (Mg C/ha) -> CO2e (Mg CO2e/ha)
CARBON_TO_CO2E_FACTOR = 44.0 / 12.0

# --- Forest volume → CO2 conversion (for juurdekasv data) ---
# Source: IPCC Good Practice Guidance for LULUCF, Table 3A.1.9
# https://www.fao.org/4/j2132s/J2132S16.htm
WOOD_DENSITY = {
    "MA": 0.42,   # Pinus sylvestris (Scots pine)
    "KU": 0.40,   # Picea abies (Norway spruce)
    "KS": 0.51,   # Betula spp. (Birch)
    "HB": 0.35,   # Populus tremula (Aspen)
    "LM": 0.45,   # Alnus glutinosa (Black alder)
    "LV": 0.45,   # Alnus incana (Grey alder)
    "SA": 0.57,   # Fraxinus excelsior (Ash)
    "TA": 0.58,   # Quercus robur (Oak)
}

# Carbon fraction of dry biomass (IPCC 2006 Vol 4, Ch 4, Table 4.3)
CARBON_FRACTION = 0.50

# CO2 per C — molecular weight ratio (44/12)
CO2_PER_C = 44.0 / 12.0  # = 3.667

# Biomass Expansion Factor: stem → whole tree (branches, roots, foliage)
# Source: IPCC GPG-LULUCF Table 3A.1.10
# https://www.fao.org/3/j2132s/J2132S18.htm
# Range: 1.15 (mature >200 m³/ha) to 3.0 (young <20 m³/ha); 1.30 = mixed-age average
BEF = 1.30
