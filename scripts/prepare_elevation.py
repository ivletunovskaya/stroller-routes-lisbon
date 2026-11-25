# /// script
# requires-python = ">=3.12"
# ///
"""Build GraphHopper elevation from DGT's 2 m LiDAR terrain model.

GraphHopper 11 only reads elevation grids of about 30 m (SRTM/HGT tiles). This script
resamples the DGT bare-earth model (MDT 2 m GeoTIFF tiles in data/dgt/) into the
one-arc-second HGT tile that covers Lisbon, N38W010. Where DGT has no data (outside
the downloaded tiles) it falls back to the SRTM tile GraphHopper downloaded earlier.

The full 2 m model is kept as data/dgt/lisbon.vrt for slope checks in our own code.

Requires GDAL on the PATH (brew install gdal).
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DGT_DIR = ROOT / "data" / "dgt"
OUT_DIR = ROOT / "data" / "elevation-hgt"
SRTM_ZIP = ROOT / "data" / "elevation-cache" / "srtm_35_05.zip"

# HGT tiles are centred on whole degrees: a one-arc-second tile has 3601 x 3601
# samples, the first and last on the tile edges.
HALF = 0.5 / 3600
TILE = "N38W010"
EXTENT = [-10 - HALF, 38 - HALF, -9 + HALF, 39 + HALF]


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    tiles = sorted(DGT_DIR.glob("MDT-2m-*.tif"))
    if not tiles:
        raise SystemExit("No DGT tiles in data/dgt/: download MDT 2 m GeoTIFFs first")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = ROOT / "data" / "elevation-work"
    work.mkdir(exist_ok=True)

    vrt = DGT_DIR / "lisbon.vrt"
    run("gdalbuildvrt", "-q", "-overwrite", str(vrt), *map(str, tiles))

    sources = []
    if SRTM_ZIP.exists():
        with zipfile.ZipFile(SRTM_ZIP) as z:
            tif = next(n for n in z.namelist() if n.lower().endswith(".tif"))
            z.extract(tif, work)
        sources.append(str(work / tif))
    sources.append(str(vrt))  # later sources win where they have data

    merged = work / f"{TILE}.tif"
    run(
        "gdalwarp", "-q", "-overwrite",
        "-t_srs", "EPSG:4326",
        "-te", *map(str, EXTENT),
        "-ts", "3601", "3601",
        "-r", "average",
        "-dstnodata", "-32768",
        *sources, str(merged),
    )
    # Elevation is stored in whole metres in HGT; round rather than truncate.
    rounded = work / f"{TILE}-int16.tif"
    run(
        "gdal_translate", "-q", "-ot", "Int16", "-a_nodata", "-32768",
        "-scale", "-32768", "32767", "-32768", "32767",
        str(merged), str(rounded),
    )
    hgt = work / f"{TILE}.hgt"
    run("gdal_translate", "-q", "-of", "SRTMHGT", str(rounded), str(hgt))
    # GraphHopper's HGT provider reads <cache_dir>/<tile>.hgt.zip.
    zipped = OUT_DIR / f"{TILE}.hgt.zip"
    with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(hgt, hgt.name)
    print(f"GraphHopper elevation tile: {zipped.relative_to(ROOT)}")
    print("Delete data/graph-cache and restart GraphHopper to use it.")
    print(f"Full 2 m model for slope checks: {vrt.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
