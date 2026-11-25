---
title: GraphHopper reads custom elevation only as <cache_dir>/<tile>.hgt.zip and silently goes flat otherwise
date: 2026-11-25
category: integration-issues
module: elevation data
problem_type: integration_issue
component: infrastructure
symptoms:
  - "Every route reported steepest +0% / 0% after switching to the DGT-based elevation tile"
  - "All route coordinates came back with elevation 0.0 and no error in the GraphHopper log"
root_cause: config_error
resolution_type: config_change
severity: high
framework_version: graphhopper 11.1
retire_when: "GraphHopper ships an elevation provider for GeoTIFF or fine rasters, or logs an error for a missing tile; check the release notes and the com.graphhopper.reader.dem package for new providers"
tags: [graphhopper, elevation, hgt, dgt, lidar, slopes]
---

# GraphHopper reads custom elevation only as <cache_dir>/<tile>.hgt.zip and silently goes flat otherwise

## Problem

The plan was to feed DGT's 2 m LiDAR terrain model to GraphHopper. GraphHopper 11.1 has no provider for fine rasters, and when it cannot find the tile it expects it silently uses elevation 0 everywhere. The router then treats Lisbon as flat, and every slope rule quietly stops working.

## Symptoms

- After switching `graph.elevation.provider` to `hgt` with a plain `N38W010.hgt` file in the cache directory, every route reported a steepest grade of +0% / 0%.
- Route coordinates all had elevation 0.0; the log had no warning about a missing file.

## What Didn't Work

- Looking for a GeoTIFF or fine-raster provider: the 11.1 jar only ships `CGIARProvider`, `GMTEDProvider`, `HGTProvider`, `SkadiProvider`, `SRTMProvider`, `SRTMGL1Provider` and `MultiSourceElevationProvider`. None of them reads a fine custom raster; all work on grids of about 30 m or coarser.
- A plain `.hgt` file: `HGTProvider` opens the tile with a `ZipInputStream`, so an unzipped file is never read.
- A separate failure on the way (observed in this session): listing only the encoded values the stroller model used made GraphHopper refuse to start ("Encoded values missing: hike_rating, country, foot_road_access, mtb_rating"), because the stock `foot.json` model needs them. That one fails loudly.

## Solution

`scripts/prepare_elevation.py` resamples the DGT bare-earth model into the one-arc-second HGT tile that covers Lisbon (3601 × 3601, whole metres, SRTM filling areas outside the DGT tiles) and writes it zipped, as `data/elevation-hgt/N38W010.hgt.zip` (`scripts/prepare_elevation.py:76`). `config/graphhopper.yml` points `graph.elevation.cache_dir` at that folder with `provider: hgt`, bilinear interpolation, long-edge sampling and moving-average smoothing.

Because GraphHopper only gets a ~30 m, whole-metre grid, the full 2 m model is kept (`data/dgt/lisbon.vrt`) and the steepest stretch of a route, ours or Google's, is measured on it in our own code (`dgt_grades`, `spike/spike_routes.py:77`).

## Why This Works

The provider builds the expected file name from the tile's latitude and longitude, looks for `<cache_dir>/<tile>.hgt.zip`, and reads the first zip entry. A missing file is not an error for it: the node keeps elevation 0. Giving it exactly that file makes the import pick up real heights. After the fix, the ordinary walk from Praça da Figueira climbs from 10 m to 95 m at the castle (`docs/research/spike-results.md`, Measurement log).

## Prevention

- After every graph build, check that a known climb has a height difference: for example, the route from Praça da Figueira to the castle must climb about 85 m. An all-zero elevation profile must fail loudly.
- Rebuild the graph (delete `data/graph-cache`) whenever the elevation tile changes. GraphHopper reads elevation only at import.
- Keep slope decisions that need fine detail in our code against the 2 m model. Inside GraphHopper, slopes come from a 30 m grid with whole-metre steps.

## Related

- `docs/research/spike-results.md` (Findings 3 and 6)
