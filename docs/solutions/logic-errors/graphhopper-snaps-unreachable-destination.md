---
title: GraphHopper silently snaps an unreachable destination, so routes stop short
date: 2026-11-25
category: logic-errors
module: route planning
problem_type: logic_error
component: infrastructure
symptoms:
  - "A stroller route to the Castelo de São Jorge entrance came back as a normal route, but ended 166 m short on a different street"
  - "No error or warning from GraphHopper: status 200 with a plausible distance and time"
root_cause: missing_validation
resolution_type: code_fix
severity: high
framework_version: graphhopper 11.1
tags: [graphhopper, snapping, no-route, honesty, custom-model]
---

# GraphHopper silently snaps an unreachable destination, so routes stop short

## Problem

When a destination can only be reached by edges the profile forbids (stairs, slopes above the cap), GraphHopper does not say "no route". It snaps the point to the nearest edge the profile may use and routes there. A parent would be given a route that never arrives, which breaks the product's honesty rule.

## Symptoms

- The stroller route to the castle entrance looked normal (about 1.1 km, 15 min), but ended 166 m from the requested point, on another street.
- GraphHopper answered with HTTP 200 and no hint that the end point had moved.

## What Didn't Work

- Treating "GraphHopper returned a path" as "a route exists". In this session GraphHopper returned an error (HTTP 400) only when no route existed between the snapped points; an unreachable requested point did not cause one.

## Solution

Compare the requested start and end with the first and last points of the returned path. If either is farther than a small limit (40 m in the spike), report the honest "no route" answer instead of the route. See `SNAP_LIMIT_M` and the check in `main` in `spike/spike_routes.py:43`.

```python
miss_start = math.dist(to_m(start[1], start[0]), to_m(*ours.coords[0]))
miss_end = math.dist(to_m(end[1], end[0]), to_m(*ours.coords[-1]))
if max(miss_start, miss_end) > SNAP_LIMIT_M:
    # honest "no route": do not show this path as a route to the destination
```

## Why This Works

GraphHopper snaps each request point to the closest edge that the profile allows. With a strict custom model (stairs at priority 0, steep edges at 0) the closest allowed edge can be far from where the parent wants to go. The returned path is therefore correct for the snapped point, not the requested one, and only a distance check notices the difference.

## Prevention

- The real planner needs the same check, and a test: a destination only reachable by stairs must give "no route", not a shorter route elsewhere.
- Tune the limit on real trips. 40 m tolerates squares and building entrances set back from the street, but it may need to depend on the place type.
- Never present the snapped end point as the destination in replies or links.

## Related

- `docs/research/spike-results.md` (Finding 4)
