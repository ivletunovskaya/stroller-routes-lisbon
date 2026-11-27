---
title: Detect stairs on a foreign route line by map matching, not by proximity
date: 2026-11-25
category: design-patterns
module: route verification
problem_type: design_pattern
component: service_layer
severity: high
last_updated: 2026-11-26
applies_when:
  - "Checking whether a route line drawn by another service (Google Maps) uses OSM staircases"
  - "Any check that must say which OSM ways a polyline travels, when the polyline was not built on the OSM graph"
tags: [stairs, map-matching, graphhopper, osm, google-routes, verification]
---

# Detect stairs on a foreign route line by map matching, not by proximity

## Context

The assistant must check routes it did not build: the route Google Maps draws for one of our links (the pre-send check) and a route a parent sends from Google Maps. Google returns only a polyline, so we have to work out which OSM staircases that line uses.

The original plan used a geometric rule: a staircase counts when most of it lies within a buffer (about 10 m) of the line and its bearing roughly matches. During the risk check this was calibrated on 150 random walking routes in central Lisbon (Baixa, Chiado, Alfama, Bairro Alto, Graça). GraphHopper's own record of which staircases each route used was the ground truth, and every line was also shifted 5 m sideways to mimic Google's geometry not lining up with OSM (`spike/calibrate_stairs.py`).

| Method | Precision | Recall |
|---|---|---|
| Staircase within a 10 m buffer of the line | 0.25–0.40 | 0.94–0.95 |
| + bearing check, end-to-end span, tighter buffer | 0.52–0.62 | 0.81–0.91 |
| Snap the line onto the OSM walking graph and read the stairs off the matched path | 0.94–0.95 | 0.96–0.97 |

The geometric rows span runs before and after indoor stairs were excluded; the matching row already excludes them.

Why the geometric rule fails:
- Most false hits were stairs inside metro stations and buildings, and escalators, lying right under or beside a street. The first false positive seen was an 8 m metro entrance at Praça da Figueira.
- The rest were short street stairs running beside a sidewalk a few metres from the street the route actually takes. Geometry alone cannot tell them apart, and tuning the buffer only trades precision for recall.

## Guidance

1. **Snap the foreign line onto the OSM walking graph** with GraphHopper's `/match` endpoint (`foot` profile), then read `road_class` and `osm_way_id` path details. The staircases are the ways on `road_class == steps` segments. See `stairs_by_matching` in `spike/spike_routes.py`.
2. **Densify the line before matching.** Send a point every ~10 m (`gps_accuracy` 15). Google polylines are sparse, and the matcher needs dense points to follow Lisbon's short street segments.
3. **Count street staircases only.** Drop OSM `highway=steps` ways tagged `indoor`, `level` or `conveying` (stations, buildings, escalators); see `load_stairs` in `spike/spike_routes.py`. In this session's calibration run, none of the staircases the routes really used carried these tags.
4. **Ask GraphHopper for `osm_way_id`.** It is not a default path detail: add `osm_way_id` to `graph.encoded_values` and rebuild the graph.

## Why This Matters

False stair hits are not harmless. In the pre-send check a false hit makes the assistant move waypoints, burn its retries and then refuse a route that was fine. In a check of a parent's own Google route it warns about stairs that are not there. Missed stairs break the success criterion that matters most: never calling a route suitable when it has stairs.

## When to Apply

- Any time stairs, or any other OSM way attribute, must be read off a line that was not routed on our graph.
- Never for our own GraphHopper routes: read `road_class` and `osm_way_id` details on the route itself (`gh_route` in `spike/spike_routes.py`). On the first real trips, matching our own stroller route (Let's Pastrami → Escola de Pedro Nunes) reported two short staircases beside the footway (`w1566675914`, 3 steps; `w1566675916`, 2 steps) that the route details show it never used (`docs/research/spike-results.md`, Finding 7).

## Examples

Before, proximity (`docs/research/spike-results.md`, Measurement log): on Praça da Figueira → Castelo the stroller route was reported as using staircase `w731800499`. It is a metro entrance (`level=0;-1`) beside the square, which the route never used.

After, matching: the same route reports no stairs, and the ordinary walk reports exactly the one staircase GraphHopper itself routed over (`w244600206`).

Caveat: matching is not free of false hits. Short staircases right beside a footway can still be picked up, as on the first real trips.

Caveat: the ground truth in the calibration comes from the same graph the matcher snaps to, so real Google lines may score somewhat lower. Re-measure on Google lines once enough real trips are checked.

## Related

- `docs/research/spike-results.md` (Finding 2)
- `spike/calibrate_stairs.py` reruns the calibration.
