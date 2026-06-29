"""Project-wide constants for the Estonia land-use neuroevolution demo."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed" / "v1"

# CRS
CRS_ESTONIAN = "EPSG:3301"

# Demo county — Lääne (Lääne County)
COUNTY_NAME = "Lääne"

# GADM Estonia counties GeoJSON (level 1 = counties)
GADM_COUNTIES_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_EST_1.json"

# Statistics Estonia 1km population grid (EPSG:3301)
# Each year is a separate zip. Pick the year you want.
STAT_EE_GRID_URLS = {
    2024: "https://stat.ee/sites/default/files/2025-03/2024_3301.zip",
    2025: "https://stat.ee/sites/default/files/2025-10/2025_3301_0.zip",
}
STAT_EE_GRID_YEAR = 2024  # default year to use

# EELIS WFS endpoint for protected areas
EELIS_WFS_URL = "https://gsavalik.envir.ee/geoserver/eelis/ows"

# CORINE Land Cover 2018 raster (100m)
CORINE_TIF = DATA_RAW / "corine" / "87080" / "Results" / "u2018_clc2018_v2020_20u1_raster100m" / "u2018_clc2018_v2020_20u1_raster100m" / "DATA" / "U2018_CLC2018_V2020_20u1.tif"

# Geofabrik Estonia OSM download
OSM_ESTONIA_GPKG_URL = "https://download.geofabrik.de/europe/estonia-latest-free.shp.zip"

# CORINE raster pixel values are sequential (1–44), not the 3-digit CLC codes.
# This maps pixel value -> standard CLC code.
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

# CORINE Land Cover simplified group mapping (3-digit code -> group)
CORINE_TO_GROUP = {
    # Urban
    111: "urban", 112: "urban", 121: "urban", 122: "urban",
    123: "urban", 124: "urban", 131: "urban", 132: "urban",
    133: "urban", 141: "urban", 142: "urban",
    # Agriculture
    211: "agriculture", 212: "agriculture", 213: "agriculture",
    221: "agriculture", 222: "agriculture", 223: "agriculture",
    231: "grassland", 241: "agriculture", 242: "agriculture",
    243: "agriculture", 244: "agriculture",
    # Forest
    311: "forest", 312: "forest", 313: "forest",
    321: "grassland", 322: "grassland", 323: "grassland",
    324: "forest",
    # Wetland
    411: "wetland", 412: "wetland", 421: "wetland", 422: "wetland", 423: "wetland",
    # Water
    511: "water", 512: "water", 521: "water", 522: "water", 523: "water",
}

# Proxy scores by land-cover group
NATURALNESS_SCORES = {
    "urban": 0.0,
    "agriculture": 0.2,
    "grassland": 0.6,
    "forest": 0.7,
    "wetland": 0.9,
    "water": None,
    "other_natural": 0.5,
}

CARBON_SCORES = {
    "urban": 0.1,
    "agriculture": 0.3,
    "grassland": 0.4,
    "forest": 0.8,
    "wetland": 1.0,
    "water": None,
    "other_natural": 0.4,
}
