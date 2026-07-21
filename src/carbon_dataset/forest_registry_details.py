"""Fetch detailed forest compartment attributes from the portal REST API.

The detailed attributes (species, age, volume, increment) come from
the portal API at register.metsad.ee/portaal/api/rest/eraldis/detail/{id}.
This endpoint is publicly accessible without authentication.

Usage:
    from carbon_dataset.forest_registry_details import fetch_details_parallel
    results = fetch_details_parallel(eraldis_ids, n_workers=10)
"""

import asyncio
import aiohttp
import pandas as pd
import time


DETAIL_URL = "https://register.metsad.ee/portaal/api/rest/eraldis/detail"


async def _fetch_one(session: aiohttp.ClientSession, eraldis_id: int) -> dict | None:
    """Fetch details for one compartment."""
    url = f"{DETAIL_URL}/{eraldis_id}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            data["eraldis_id"] = eraldis_id
            return data
    except Exception:
        return None


async def _fetch_batch(eraldis_ids: list[int], n_workers: int,
                       progress_every: int = 100) -> list[dict]:
    """Fetch details for a batch of compartments in parallel."""
    results = []
    sem = asyncio.Semaphore(n_workers)
    t_start = time.time()
    done = 0
    total = len(eraldis_ids)

    async def worker(eid):
        nonlocal done
        async with sem:
            result = await _fetch_one(session, eid)
            done += 1
            if done % progress_every == 0:
                elapsed = time.time() - t_start
                rate = done / elapsed
                eta = (total - done) / rate if rate > 0 else 0
                print(f"  {done:>6,}/{total:,} ({done/total*100:.0f}%) "
                      f"- {rate:.0f} req/s - elapsed: {elapsed:.0f}s - ETA: {eta:.0f}s")
            return result

    connector = aiohttp.TCPConnector(limit=n_workers, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [worker(eid) for eid in eraldis_ids]
        results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


def fetch_details_parallel(
    eraldis_ids: list[int],
    n_workers: int = 10,
    progress_every: int = 100,
) -> pd.DataFrame:
    """Fetch detailed attributes for a list of compartment IDs.

    Args:
        eraldis_ids: List of eraldis_id values to fetch.
        n_workers: Number of parallel requests.
        progress_every: Print progress every N completions.

    Returns:
        DataFrame with detailed attributes for each compartment.
    """
    print(f"Fetching details for {len(eraldis_ids):,} compartments "
          f"({n_workers} parallel workers)")

    t0 = time.time()
    import nest_asyncio
    nest_asyncio.apply()
    results = asyncio.run(_fetch_batch(eraldis_ids, n_workers, progress_every))
    elapsed = time.time() - t0

    print(f"\nDone: {len(results):,} successful / {len(eraldis_ids):,} attempted "
          f"({len(results)/len(eraldis_ids)*100:.0f}%) in {elapsed:.0f}s")

    if not results:
        return pd.DataFrame()

    # Flatten: extract key fields, skip nested objects
    rows = []
    for r in results:
        row = {}
        for k, v in r.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                row[k] = v
        # Extract first layer species info if available
        elemendid = r.get("elemendid", [])
        if elemendid:
            e0 = elemendid[0]
            row["layer1_species"] = e0.get("puuliigiKood")
            row["layer1_age"] = e0.get("vanus")
            row["layer1_volume"] = e0.get("tagavara")
            row["layer1_origin"] = e0.get("paritoluKood")
            row["layer1_share"] = e0.get("osakaal")
        rows.append(row)

    return pd.DataFrame(rows)
