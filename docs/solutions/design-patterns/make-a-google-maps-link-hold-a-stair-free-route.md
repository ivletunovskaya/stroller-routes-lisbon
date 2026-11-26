---
title: Make a Google Maps link hold a stair-free route, and verify it on slopes as well as stairs
date: 2026-11-25
category: design-patterns
module: route verification
problem_type: design_pattern
component: service_layer
severity: high
last_updated: 2026-11-26
applies_when:
  - "Handing a route we computed to Google Maps as a walking link with waypoints"
  - "Deciding whether the route Google will actually draw is safe to call suitable"
retire_when: "Google Maps URLs gain pass-through (via) waypoints or a stroller mode; check developers.google.com/maps/documentation/urls"
tags: [google-maps, waypoints, routes-api, slope, verification, dgt]
---

# Make a Google Maps link hold a stair-free route, and verify it on slopes as well as stairs

## Context

The assistant gives parents a Google Maps walking link. Google treats waypoints as stops and walks its own shortest path between them, and a mobile browser accepts only 3 waypoints (`docs/research/2026-11-17-technical-research.md`, Google Maps URLs). Whether a link keeps Google on our route therefore has to be checked by asking Google which route the link draws (Routes API `computeRoutes`, walking, the same points) and examining that line.

Two things went wrong in the first version of that check during the risk check:
- **Waypoints chosen by distance from the ordinary walk made Google worse.** On Praça da Figueira → Castelo (coarse terrain), three such waypoints took Google from 1 staircase to 7 and from 1,357 m to 1,710 m. One waypoint sat almost on the start point (`docs/research/spike-results.md`, Measurement log).
- **Checking stairs alone passed a bad route.** On Praça do Comércio → Sé, Google's own route had no stairs, but on the 2 m terrain model it had a +20% climb over 15 m, while our route stayed at +11%.

## Guidance

1. **Add waypoints one at a time where Google strays furthest.** Ask Google for the route with the current waypoints, find the point of our route farthest from Google's line, add it as the next waypoint, and ask again, up to 3 waypoints. See `pin_to_google` in `spike/spike_routes.py:392`, with the farthest-point step at line 424.
2. **A link holds only if Google's line has no street stairs and is not noticeably steeper than ours.** Stairs come from map matching (see the related learning). The steepest stretch of both lines is measured on the DGT 2 m model over a 15 m window. Google may be at most 2 points steeper (`SLOPE_TOLERANCE`, `spike/spike_routes.py:45`).
   If either slope is unknown (a line leaves the 2 m terrain tiles), the link does not hold: the verdict is "cannot be verified". On the first real trips, Biblioteca de Alcântara → Piscina do Alvito, our detour left the tiles, the comparison was skipped, and Google's direct +18% climb was called "holds" (`docs/research/spike-results.md`, Finding 7). See `slope_known` in `pin_to_google`.
3. **If 3 waypoints do not make it hold, do not send the link as suitable.** Answer honestly instead (the "no route" or least-bad answer).
4. **Use Google's line in memory only.** Under the Google Maps Platform terms it is not stored or drawn (`docs/research/2026-11-17-technical-research.md`, Routes API and terms).

## Why This Matters

The parent walks Google's line, not ours. A link that drifts back onto stairs or a steep street, unchecked, is exactly the failure the product promises to avoid. Stairs and slopes are separate risks: in Lisbon, Google's shortest path often picks a steeper parallel street rather than a staircase.

## When to Apply

- Every time a link built from our route is about to be sent.
- The same slope-plus-stairs check applies to a route a parent sends from Google Maps, recomputed from the link's points.

## Examples

With DGT terrain (2026-11-25; figures from `docs/research/spike-results.md`, Measurement log):

| Trip | Google, no waypoints | After pinning |
|---|---|---|
| Rossio → Praça Luís de Camões | 642 m, 4 staircases, +50% | 2 waypoints: 3,235 m, no stairs, +10% (our route +10%) — holds |
| Praça do Comércio → Sé | 512 m, no stairs, +20% (ours +11%) | 2 waypoints: 582 m, no stairs, +12% — holds |

Both trips are examples picked without local knowledge. Re-measure on real trips before relying on how many waypoints are usually enough.

## Related

- `docs/solutions/design-patterns/detect-stairs-on-foreign-route-by-map-matching.md`
- `docs/research/spike-results.md` (Findings 5 and 6)
