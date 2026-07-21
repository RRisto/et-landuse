"""Download forest compartment geometries + IDs from WFS for Lääne county.

Downloads from gsavalik.envir.ee GeoServer (CC-BY 4.0, open access).
Saves as GeoPackage with all compartments (RMK + private forest).

Usage:
    from carbon_dataset.forest_registry_wfs import download_laane_compartments
    download_laane_compartments("data/raw/forest_registry/laane_eraldised.gpkg")
"""

import geopandas as gpd
import pandas as pd
import requests
import re
import time
from pathlib import Path

# Config
BBOX = "430000,6480000,530000,6570000"  # Lääne county approx, EPSG:3301
WFS_URL = "https://gsavalik.envir.ee/geoserver/mr_portaal/wfs"
PAGE_SIZE = 1000

LAYERS = [
    ("mr_portaal:eraldis-rmk", "rmk"),   # state forest
    ("mr_portaal:eraldis-era", "era"),    # private forest
]


def get_feature_count(layer: str, bbox: str = BBOX) -> int:
    """Get total feature count for a layer within BBOX."""
    r = requests.get(WFS_URL, params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": layer, "resultType": "hits",
        "BBOX": f"{bbox},EPSG:3301",
    })
    match = re.search(r'numberMatched="(\d+)"', r.text)
    return int(match.group(1)) if match else 0


def download_layer(layer: str, label: str, bbox: str = BBOX) -> gpd.GeoDataFrame:
    """Download all features for a layer, paged."""
    total = get_feature_count(layer, bbox)
    print(f"  {label}: {total:,} features to download")

    all_gdfs = []
    offset = 0

    while offset < total:
        t0 = time.time()
        r = requests.get(WFS_URL, params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "count": str(PAGE_SIZE),
            "startIndex": str(offset),
            "BBOX": f"{bbox},EPSG:3301",
            "srsName": "EPSG:3301",
        })

        if r.status_code != 200:
            print(f"    ERROR at offset {offset}: HTTP {r.status_code}")
            break

        data = r.json()
        features = data.get("features", [])
        if not features:
            break

        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:3301")
        all_gdfs.append(gdf)

        offset += len(features)
        dt = time.time() - t0
        pct = offset / total * 100
        eta = (total - offset) / PAGE_SIZE * dt
        print(f"    {offset:>7,}/{total:,} ({pct:.0f}%) - ETA: {eta/60:.1f}min", end="\r")

    print()

    if not all_gdfs:
        return gpd.GeoDataFrame()

    result = pd.concat(all_gdfs, ignore_index=True)
    result = gpd.GeoDataFrame(result, geometry="geometry", crs="EPSG:3301")
    result["ownership"] = label
    return result


def download_laane_compartments(output_path: str | Path, bbox: str = BBOX):
    """Download all forest compartments for Lääne county."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading forest compartments for Lääne county")
    print(f"BBOX: {bbox} (EPSG:3301)")
    print(f"Output: {output_path}")
    print()

    all_data = []
    t_start = time.time()

    for layer, label in LAYERS:
        print(f"Layer: {layer}")
        gdf = download_layer(layer, label, bbox)
        if len(gdf) > 0:
            all_data.append(gdf)
            print(f"  Downloaded: {len(gdf):,} features")
        print()

    if not all_data:
        print("No data downloaded!")
        return

    combined = pd.concat(all_data, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:3301")
    combined.to_file(output_path, driver="GPKG")

    t_total = time.time() - t_start
    print(f"Done in {t_total/60:.1f} minutes")
    print(f"Total: {len(combined):,} compartments")
    print(f"File: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    download_laane_compartments(Path("data/raw/forest_registry/laane_eraldised.gpkg"))
