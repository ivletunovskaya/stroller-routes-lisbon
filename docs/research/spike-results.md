# Risk check (U1): results so far

Status: **in progress**. The automated part is done. The part that needs real trips, the DGT terrain model and a Google key is still open (see "Still to do").

Setup: GraphHopper 11.1 running locally on the OSM extract of Lisbon (Geofabrik, downloaded 2026-11-24), with a `foot` profile as the ordinary-walk baseline and a `stroller` profile that forbids stairs and caps slopes (`config/stroller-model.json`, thresholds in `config/thresholds.toml`). Elevation for now: CGIAR/SRTM (about 90 m grid).

## Finding 1: stairs data is rich

The Lisbon bounding box holds **4,159 OSM staircases**. Many carry a name, `step_count`, `incline` and `handrail`, partly imported from the city's open data. Street-level stairs data is good enough to route around.

## Finding 2: detecting stairs by geometry alone does not work; snapping to the street graph does

To check a route that Google draws (requirements R2 and R10), we need to know which staircases that line actually uses. Calibrated on 150 random walking routes in central Lisbon (Baixa, Chiado, Alfama, Bairro Alto, Graça), with GraphHopper's own record of the stairs each route uses as ground truth, and with each line also shifted 5 m sideways to mimic Google's geometry not lining up with OSM:

| Method | Precision | Recall |
|---|---|---|
| Staircase within a buffer of the line (the plan's original rule) | 0.25–0.40 | 0.94–0.95 |
| + bearing check, end-to-end span, stricter buffer | 0.52–0.62 | 0.81–0.91 |
| **Snap the line onto the OSM walking graph (GraphHopper map matching), read the stairs off the matched path** | **0.94–0.95** | **0.96–0.97** |

Why the geometric rule fails:
- Most false hits were stairs **inside metro stations, buildings and escalators** (`indoor`, `level`, `conveying` tags) right under or beside a street. These are now excluded in both methods.
- The rest were short street stairs running alongside a sidewalk, a few metres from the street the route really takes. Geometry alone cannot tell them apart.

**Recommendation:** the route check (plan unit U4) should use map matching rather than a buffer rule. The script now does this (`stairs_by_matching` in `spike/spike_routes.py`). Caveat: the ground truth comes from the same graph the matcher snaps to, so real Google lines may score somewhat lower. The Google part of this check will measure that.

## Finding 3: coarse elevation hides Lisbon's hills

Example trip Praça da Figueira → Castelo de São Jorge entrance:

| | Distance | Time | Steepest (smoothed over 15 m) | Stairs |
|---|---|---|---|---|
| Ordinary walk | 1,181 m | 14 min | +107% / −106% | 1 staircase |
| Stroller profile | 1,145 m | 15 min | +46% / −26% | none |

The stroller route avoids stairs, but it is only one minute longer and still climbs to the castle on foot. In reality the castle hill is the textbook case for the two city lifts. With a 90 m elevation grid the per-edge slopes stay under the 8% cap, so the router does not see the climb, while the point-to-point grades swing wildly (+107% is noise).

GraphHopper 11.1 only reads elevation grids of about 30 m or coarser (SRTM/HGT, CGIAR, GMTED, Skadi). It cannot read DGT's 2 m LiDAR model directly. Options:
1. Resample the DGT bare-earth model (no buildings) to a 1-arc-second HGT grid (about 30 m) for GraphHopper, and check the finished route against the full 2 m raster in application code, rejecting or penalising it there.
2. Write a custom GraphHopper elevation provider in Java that reads the 2 m raster.

Option 1 fits the current Python stack and is the suggested next step. Lifts are not in the router yet (they belong to a later unit), so the castle trip cannot show the lift route either way.

## Still to do

- [ ] 3–4 real trips from the author in `spike/routes.yaml`, with where the stairs actually are and which way she walks with a stroller.
- [ ] DGT account → download the MDT 2 m tiles for Lisbon → rerun with better elevation and tune the slope thresholds.
- [ ] Google Maps Platform key → for each trip, check whether the link with ≤3 waypoints keeps Google on our route (computeRoutes + map matching).
- [ ] The author taps each link inside Telegram and records whether the Google Maps app keeps the waypoints and draws the same route.
- [ ] Go / no-go decision.

## How to reproduce

See `spike/README.md`.
