"""Download helpers for raw data sources."""

import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import NamedTemporaryFile

import requests

from .constants import DATA_RAW


def download_file(url: str, filename: str, subdir: str = "") -> Path:
    """Download a file if it doesn't already exist. Returns path to file."""
    dest_dir = DATA_RAW / subdir if subdir else DATA_RAW
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    if dest.exists() and dest.stat().st_size > 0:
        print(f"Already exists: {dest}")
        return dest

    print(f"Downloading {url} ...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=dest_dir,
            prefix=f"{filename}.",
            suffix=".part",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
        temp_path.replace(dest)
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
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
        for member in zf.infolist():
            _validate_zip_member(dest_dir, member.filename)
        zf.extractall(dest_dir)
    print(f"Extracted to {dest_dir}")
    return dest_dir


def _validate_zip_member(dest_dir: Path, member_name: str) -> None:
    posix_member = PurePosixPath(member_name)
    windows_member = PureWindowsPath(member_name)
    if (
        posix_member.is_absolute()
        or windows_member.is_absolute()
        or ".." in posix_member.parts
        or ".." in windows_member.parts
    ):
        raise ValueError(f"unsafe ZIP member path: {member_name}")

    root = dest_dir.resolve()
    target = (root / Path(*posix_member.parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"unsafe ZIP member path: {member_name}")
