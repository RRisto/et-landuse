"""Download helpers for raw data sources."""

import zipfile
from pathlib import Path

import requests

from .constants import DATA_RAW


def download_file(url: str, filename: str, subdir: str = "") -> Path:
    """Download a file if it doesn't already exist. Returns path to file."""
    dest_dir = DATA_RAW / subdir if subdir else DATA_RAW
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    if dest.exists():
        print(f"Already exists: {dest}")
        return dest

    print(f"Downloading {url} ...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Saved to {dest}")
    return dest


def unzip(path: Path, dest_dir: Path | None = None) -> Path:
    """Unzip a file. Returns extraction directory."""
    if dest_dir is None:
        dest_dir = path.parent / path.stem
    if dest_dir.exists():
        print(f"Already extracted: {dest_dir}")
        return dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {path} ...")
    with zipfile.ZipFile(path, "r") as zf:
        zf.extractall(dest_dir)
    print(f"Extracted to {dest_dir}")
    return dest_dir
