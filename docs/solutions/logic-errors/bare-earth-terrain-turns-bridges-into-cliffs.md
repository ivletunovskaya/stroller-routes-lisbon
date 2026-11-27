---
title: A bare-earth terrain model turns footbridges into cliffs, so bridge them over
date: 2026-11-26
category: logic-errors
module: elevation data
problem_type: logic_error
component: service_layer
symptoms:
  - "A stair-free route over a footbridge showed a steepest stretch of +31% / -39% on the DGT 2 m model"
  - "The same check called Google's line over the bridge far steeper than the ground route under it"
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [dgt, lidar, slopes, bridges, osm, layer]
---

# A bare-earth terrain model turns footbridges into cliffs, so bridge them over

## Problem

The DGT MDT 2 m model is bare earth: buildings and bridges are removed. Sampling heights along a route that crosses a footbridge reads the ground under the deck, so a flat bridge looks like a drop and a climb of several metres over 15 m. A route that is in fact easy gets flagged as far too steep, and a Google link over the bridge looks steeper than it is.

## Symptoms

- MACAM → Sud Kids (first real trips, `docs/research/spike-results.md`, Finding 7): the stair-free route over the MAAT footbridge showed +31% / -39%.
- Raised plazas (OSM `layer=2` areas without `bridge=yes`) and tunnels give the same kind of fake slope.

## Solution

Export the walkable ways that are off the ground from OSM (any `highway` way with `bridge`, `tunnel` or a non-zero `layer`) into `data/lisbon-offground.geojson` (`scripts/fetch_osm.sh`). In the slope check, sample points that fall within 8 m of one of them get a height interpolated in a straight line between the nearest ground points on either side (`_load_offground` in `spike/spike_routes.py`, applied in `dgt_profile`). After the fix the stroller route read +3% / -4%.

The 8 m margin is because Google's lines run a few metres off the OSM way: with 3 m, Google's line over the same bridge still showed -39%.

## Prevention

- Any check that samples a bare-earth model along a walking line must mask bridges, raised plazas and tunnels first. Filtering on `bridge=yes` alone misses raised plazas tagged only with `layer`.
- A very steep stretch (beyond about 25%) on a route the router accepted is a hint of a masking gap, not of a real slope.
