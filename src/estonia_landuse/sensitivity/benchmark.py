"""Comparable wall-clock benchmark for historical manifest execution."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from time import perf_counter

import pandas as pd

from .config import ExperimentProfile
from .runner import run_manifest


def benchmark_manifest(
    context: pd.DataFrame,
    feature_columns: list[str],
    manifest: pd.DataFrame,
    profile: str | ExperimentProfile,
) -> pd.DataFrame:
    """Run the same manifest sequentially and in parallel and report speedup."""
    if manifest.empty:
        raise ValueError("benchmark manifest must contain at least one run")
    parallel_workers = min(
        max(2, os.cpu_count() or 2),
        max(2, len(manifest)),
    )
    measurements: list[dict[str, float | int | str]] = []
    with tempfile.TemporaryDirectory(prefix="historical-sensitivity-benchmark-") as temporary:
        root = Path(temporary)
        for execution_mode, n_workers in (
            ("sequential", 1),
            ("parallel", parallel_workers),
        ):
            started = perf_counter()
            results = run_manifest(
                context,
                feature_columns,
                manifest,
                root / execution_mode,
                profile,
                overwrite=True,
                n_workers=n_workers,
            )
            wall_seconds = perf_counter() - started
            failed = results.loc[results["status"] == "failed"]
            if not failed.empty:
                raise RuntimeError(
                    f"benchmark {execution_mode} execution failed for {len(failed)} run(s)"
                )
            optimizer_cpu_seconds = float(
                pd.to_numeric(results["optimizer_cpu_seconds"], errors="coerce")
                .fillna(0.0)
                .sum()
            )
            measurements.append(
                {
                    "execution_mode": execution_mode,
                    "n_workers": n_workers,
                    "wall_seconds": wall_seconds,
                    "optimizer_cpu_seconds": optimizer_cpu_seconds,
                    "run_count": len(manifest),
                }
            )

    sequential_wall = float(measurements[0]["wall_seconds"])
    parallel_wall = float(measurements[1]["wall_seconds"])
    measurements[0]["speedup"] = 1.0
    measurements[1]["speedup"] = (
        sequential_wall / parallel_wall if parallel_wall > 0.0 else float("inf")
    )
    return pd.DataFrame(measurements)
