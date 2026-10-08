"""
ZIP-centroid coordinates from the real U.S. Census Bureau Gazetteer
files — no per-address geocoding API calls needed at request time.

Why centroids instead of live geocoding: distance is only 10% of the
Care Access Score, so a ZIP-code-level approximation is accurate enough,
and it means searching doesn't depend on a geocoding API being up or
rate-limiting us. This is standard practice for "near me" style search.

Source (real, official, no key required):
    https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip
This is the full national ZIP Code Tabulation Area (ZCTA) file — tens of
thousands of ZIP codes across the whole US. We download it once, keep
only North Carolina ZIP codes (prefixes 27x/28x), and cache that small
subset locally so later runs never need to re-download the ~1MB
national file.
"""

import csv
import io
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_zcta_national.zip"
)

CACHE_PATH = Path(__file__).parent / "data" / "nc_zip_centroids.csv"

# North Carolina ZIP codes fall in the 27000-28999 range.
NC_ZIP_PREFIXES = ("27", "28")


def _parse_gazetteer_text(text: str) -> Dict[str, Tuple[float, float]]:
    """
    Parse the tab-delimited national ZCTA gazetteer file, keeping only
    North Carolina ZIPs. Locates columns by header name rather than a
    hardcoded position, since the exact column set has changed across
    years (e.g. an added GEOIDFQ column).
    """
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = [h.strip() for h in next(reader)]

    def col(name: str) -> int:
        return header.index(name)

    geoid_idx = col("GEOID")
    lat_idx = col("INTPTLAT")
    lon_idx = col("INTPTLONG")

    result: Dict[str, Tuple[float, float]] = {}
    for row in reader:
        if len(row) <= max(geoid_idx, lat_idx, lon_idx):
            continue
        zip_code = row[geoid_idx].strip()
        if not zip_code.startswith(NC_ZIP_PREFIXES):
            continue
        try:
            result[zip_code] = (float(row[lat_idx]), float(row[lon_idx]))
        except ValueError:
            continue
    return result


def _download_and_cache_nc_centroids() -> Dict[str, Tuple[float, float]]:
    resp = requests.get(GAZETTEER_URL, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The archive contains exactly one .txt file.
        txt_name = next(n for n in zf.namelist() if n.endswith(".txt"))
        # Gazetteer files are encoded latin-1, not utf-8.
        text = zf.read(txt_name).decode("latin-1")

    nc_centroids = _parse_gazetteer_text(text)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["zip", "lat", "lon"])
        for zip_code, (lat, lon) in sorted(nc_centroids.items()):
            writer.writerow([zip_code, lat, lon])

    return nc_centroids


def _load_cached_centroids() -> Optional[Dict[str, Tuple[float, float]]]:
    if not CACHE_PATH.exists():
        return None
    result: Dict[str, Tuple[float, float]] = {}
    with open(CACHE_PATH, newline="") as f:
        for row in csv.DictReader(f):
            try:
                result[row["zip"]] = (float(row["lat"]), float(row["lon"]))
            except (KeyError, ValueError):
                continue
    return result or None


def get_nc_zip_centroids() -> Dict[str, Tuple[float, float]]:
    """
    Return {zip: (lat, lon)} for North Carolina ZIP codes. Uses the
    local cache if present; otherwise downloads the real Census
    Gazetteer file once and caches the NC subset for next time.
    """
    cached = _load_cached_centroids()
    if cached is not None:
        return cached
    return _download_and_cache_nc_centroids()


def coords_for_zip(zip_code: str, centroids: Optional[Dict[str, Tuple[float, float]]] = None) -> Optional[Tuple[float, float]]:
    """Look up (lat, lon) for a 5-digit ZIP, or None if not found."""
    if centroids is None:
        centroids = get_nc_zip_centroids()
    zip5 = (zip_code or "").strip()[:5]
    return centroids.get(zip5)
