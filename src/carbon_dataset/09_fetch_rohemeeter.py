"""Rohemeeter fetcher — run as a standalone script (not inside Jupyter).

Usage:
    uv run python src/carbon_dataset/09_fetch_rohemeeter.py [--delay 1.5] [--batch 100]

Queries every 200m point within 1km grid cells. Saves progress to JSON,
safe to interrupt (Ctrl+C) and resume.
"""

import argparse
import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# --- Paths ---
CARBON_DIR = Path("data/processed/carbon_v1_5")
OUTPUT_RAW = CARBON_DIR / "rohemeeter_scores_raw.parquet"
OUTPUT_AGG = CARBON_DIR / "rohemeeter_scores.parquet"
PROGRESS_PATH = CARBON_DIR / "rohemeeter_progress.json"
GRID_PATH = CARBON_DIR / "grid.gpkg"

ROHEMEETER_URL = "https://shiny.botany.ut.ee/rohemeeter/"

# Query grid: 200m step (5x5 = 25 points per 1km cell)
SUBCELL_STEP = 200
SUBCELL_OFFSET = 100
MAX_RETRIES = 3
TIMEOUT_MS = 15000


def _save_progress(results):
    """Save progress atomically (write to temp, then rename)."""
    import tempfile
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = PROGRESS_PATH.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(results, f)
    # Atomic rename (won't corrupt on crash)
    tmp_path.replace(PROGRESS_PATH)


def generate_query_points(grid):
    """Generate all query points (200m spacing within each 1km cell).
    
    Skips cells that are mostly water (water_pct > 0.5) to avoid
    wasting queries on sea/lake cells that won't return data.
    """
    import pandas as pd

    # Load V1 features to get water_pct
    features_path = Path("data/processed/v1/features_v1.parquet")
    if features_path.exists():
        features = pd.read_parquet(features_path, columns=["cell_id", "water_pct"])
        water_cells = set(features.loc[features["water_pct"] > 0.5, "cell_id"].tolist())
        print(f"Skipping {len(water_cells)} water-dominated cells", flush=True)
    else:
        water_cells = set()

    points = []
    n_per_side = 1000 // SUBCELL_STEP
    skipped = 0
    for idx, row in grid.iterrows():
        cell_id = row["cell_id"] if "cell_id" in grid.columns else idx
        if int(cell_id) in water_cells:
            skipped += 1
            continue
        minx, miny, _, _ = row.geometry.bounds
        for xi in range(n_per_side):
            for yi in range(n_per_side):
                x = minx + SUBCELL_OFFSET + xi * SUBCELL_STEP
                y = miny + SUBCELL_OFFSET + yi * SUBCELL_STEP
                point_key = f"{int(cell_id)}_{xi}_{yi}"
                points.append((point_key, int(cell_id), x, y))

    print(f"Skipped {skipped} water cells, querying {len(points)} points", flush=True)
    return points


def fetch_score(page, x, y):
    """Query Rohemeeter for one coordinate."""
    url = f"{ROHEMEETER_URL}?x={int(x)}&y={int(y)}"
    try:
        page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)
        page.wait_for_timeout(3000)
        result = page.evaluate("""() => {
            // The gauge widget has id="rohemeeter" and class="gauge"
            const gaugeEl = document.querySelector('#rohemeeter svg');
            let gaugeValue = null;
            if (gaugeEl) {
                const textEls = gaugeEl.querySelectorAll('text');
                for (const t of textEls) {
                    const val = parseFloat(t.textContent.trim());
                    // The main score is font-size 23px, value 0-100
                    if (!isNaN(val) && val >= 0 && val <= 100 && t.getAttribute('font-size') === '23px') {
                        gaugeValue = val;
                        break;
                    }
                }
                // Fallback: if no 23px match, get the largest font text with valid number
                if (gaugeValue === null) {
                    for (const t of textEls) {
                        const val = parseFloat(t.textContent.trim());
                        if (!isNaN(val) && val >= 0 && val <= 100) {
                            gaugeValue = val;
                            break;
                        }
                    }
                }
            }

            // Get the description text from #liigid
            const descEl = document.querySelector('#liigid');
            let description = descEl ? descEl.textContent.trim().substring(0, 500) : null;

            return {gauge: gaugeValue, description: description};
        }""")
        if result and (result.get("gauge") is not None or result.get("description")):
            return result
    except Exception as e:
        print(f"  ERROR at ({int(x)}, {int(y)}): {e}", flush=True)
    return None


def run_fetch(delay=1.5, batch_size=100):
    """Main fetch loop."""
    from playwright.sync_api import sync_playwright

    grid = gpd.read_file(GRID_PATH)
    query_points = generate_query_points(grid)
    total = len(query_points)

    # Load progress
    results = {}
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            results = json.load(f)

    remaining = [p for p in query_points if p[0] not in results]
    print(f"Total: {total} points | Done: {len(results)} | Remaining: {len(remaining)}", flush=True)
    print(f"ETA: ~{len(remaining) * delay / 3600:.1f} hours at {delay}s delay", flush=True)

    if not remaining:
        print("All done!", flush=True)
        return results

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        fetched = 0

        try:
            for point_key, cell_id, x, y in remaining:
                result = None
                for attempt in range(MAX_RETRIES):
                    result = fetch_score(page, x, y)
                    if result is not None:
                        break
                    time.sleep(1)

                results[point_key] = {
                    "cell_id": cell_id,
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "gauge_score": result.get("gauge") if result else None,
                    "description": result.get("description") if result else None,
                }
                fetched += 1

                # Report nulls
                if result is None:
                    print(f"  NULL at cell {cell_id} ({int(x)}, {int(y)})", flush=True)

                if fetched % 50 == 0:
                    done = len(results)
                    n_valid = sum(1 for r in results.values() if r.get("gauge_score") is not None)
                    eta_h = (total - done) * delay / 3600
                    print(f"  {done}/{total} ({done/total*100:.1f}%) | "
                          f"valid: {n_valid} | ETA: {eta_h:.1f}h", flush=True)

                if fetched % batch_size == 0 or fetched == 10 or fetched % 25 == 0:
                    _save_progress(results)
                    print(f"  [saved {len(results)} points]", flush=True)

                time.sleep(delay)

        except KeyboardInterrupt:
            print(f"\nInterrupted after {fetched} queries.", flush=True)
        finally:
            browser.close()
            _save_progress(results)
            print(f"Saved progress: {len(results)} points", flush=True)

    return results


def export_parquet():
    """Convert progress JSON to parquet files."""
    if not PROGRESS_PATH.exists():
        print("No progress file found.")
        return

    with open(PROGRESS_PATH) as f:
        results = json.load(f)

    rows = []
    for point_key, data in results.items():
        row = {
            "point_key": point_key,
            "cell_id": data["cell_id"],
            "x": data["x"],
            "y": data["y"],
            "rohemeeter_score": data.get("gauge_score"),
        }
        rows.append(row)

    df_raw = pd.DataFrame(rows)
    df_raw.to_parquet(OUTPUT_RAW, index=False)
    print(f"Saved raw: {OUTPUT_RAW} ({len(df_raw)} points)")

    # Aggregate per 1km cell
    if "rohemeeter_score" in df_raw.columns:
        agg = df_raw.groupby("cell_id")["rohemeeter_score"].agg(
            rohemeeter_mean="mean",
            rohemeeter_std="std",
            rohemeeter_min="min",
            rohemeeter_max="max",
            rohemeeter_median="median",
        ).reset_index()

        valid_counts = df_raw.groupby("cell_id")["rohemeeter_score"].apply(
            lambda s: s.notna().sum()
        ).reset_index(name="rohemeeter_valid_count")
        agg = agg.merge(valid_counts, on="cell_id")

        agg.to_parquet(OUTPUT_AGG, index=False)
        print(f"Saved aggregated: {OUTPUT_AGG} ({len(agg)} cells)")

        valid = agg["rohemeeter_mean"].dropna()
        if len(valid) > 0:
            print(f"  Mean: {valid.mean():.1f}, range: [{valid.min():.1f}, {valid.max():.1f}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Rohemeeter biodiversity scores")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    parser.add_argument("--batch", type=int, default=100, help="Save every N queries")
    parser.add_argument("--export-only", action="store_true", help="Just export existing progress to parquet")
    args = parser.parse_args()

    if args.export_only:
        export_parquet()
    else:
        run_fetch(delay=args.delay, batch_size=args.batch)
        export_parquet()
