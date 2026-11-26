# Risk check (U1): results so far

Status: **in progress**. The automated part is done. The part that needs real trips, the DGT terrain model and a Google key is still open (see "Still to do").

Setup: GraphHopper 11.1 running locally on the OSM extract of Lisbon (Geofabrik, downloaded 2026-11-24), with a `foot` profile as the ordinary-walk baseline and a `stroller` profile that forbids stairs and caps slopes (`config/stroller-model.json`, thresholds in `config/thresholds.toml`). Elevation: CGIAR/SRTM (about 90 m) until 2026-11-24, DGT LiDAR from 2026-11-25 (see Finding 6).

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

## Finding 4: a route that stops short must be reported as "no route"

GraphHopper snaps the destination to the nearest street the profile may use. When the real destination is only reachable by stairs or a steep climb, it silently snaps elsewhere: the "stroller route" to the castle entrance ended **166 m short**, on a different street. Shown to a parent, that would be a route that never arrives, which breaks the honesty principle (R7). The script now treats a start or end more than 40 m off as the honest "no route" answer. The real planner (U3) needs the same rule.

## Finding 5: first Google checks (key working, 2026-11-24)

| Trip | Stroller route | Google with our waypoints |
|---|---|---|
| Praça da Figueira → Castelo | does not reach the castle without lifts (end 166 m off) | not meaningful: with 0–3 waypoints Google kept using 1–6 staircases |
| Rossio → Praça Luís de Camões | none within the 8% cap on the 90 m terrain | not run |
| Praça do Comércio → Sé | 656 m, 9 min (+2 min), no stairs | holds with 0 waypoints: Google's own route has no stairs either |

Also learned:
- Waypoints placed far from the trip ends make Google wander: on the castle trip, adding waypoints *added* staircases. The script now adds waypoints one by one where Google strays furthest from our route, re-checking each time.
- The Google check currently covers stairs only. Slopes on Google's line need the DGT raster.
- Chiado (Rua do Carmo) comes out "too steep" on the coarse terrain although parents push strollers up it. Thresholds can only be tuned on real trips with real terrain.

None of these trips is a real test yet: they are examples picked without local knowledge. The go/no-go needs the author's own trips.

## Finding 6: with DGT terrain the router sees the hills (2026-11-25)

The author downloaded 106 DGT MDT 2 m tiles (1 × 1 km each, July 2024 survey) covering Lisbon from Belém to Olivais. `scripts/prepare_elevation.py` resamples them into the one-arc-second HGT tile GraphHopper reads (SRTM fills the strip west of the DGT tiles), and keeps the full 2 m model for slope checks in our own code. Two gotchas: GraphHopper's HGT provider only reads `<cache_dir>/N38W010.hgt.zip`, and when the file is missing it silently treats the whole city as flat.

Steepest climb and descent below are measured on the 2 m model over a 15 m window. Google's route counts as holding ours when it uses no street stairs and is at most 2 points steeper than our route.

| Trip | Ordinary walk | Stroller route | Google with our waypoints |
|---|---|---|---|
| Praça da Figueira → Castelo | 1,143 m, 14 min, +100%, 1 staircase | **none** (true without the city lifts) | — |
| Rossio → Praça Luís de Camões | 647 m, 8 min, +37%, 3 staircases | 3,353 m, **44 min** (+36), +10% | holds with 2 waypoints (no stairs, +10%) |
| Praça do Comércio → Sé | 556 m, 7 min, +101%, 1 staircase | 627 m, 8 min (+2), +11% | holds with 2 waypoints; without them Google has no stairs but a **+20%** stretch |

What this says:
- **The terrain model matters.** On SRTM the castle hill looked climbable and Chiado unreachable; on DGT the castle is honestly unreachable without lifts, and Chiado is reachable by a long detour.
- **The Google link mechanism works on these trips.** Two waypoints were enough to keep Google on the stair-free, gentler route in both cases where one exists.
- **Slope checks catch what stair checks miss.** Google's own route to the Sé has no stairs but a +20% climb; with stairs-only checking it would have been passed as fine.
- **The thresholds are not settled.** An 8% cap turns Rossio → Chiado into a 44-minute detour. Whether parents would rather push up Rua do Carmo, and how steep a short ramp is acceptable (our routes still show +10–11% over 15 m), can only come from real trips.

## Finding 7: first real trips (2026-11-26)

Three trips from the author. End points come from her Google Maps links (the first trip's playground was wrongly guessed at first); her notes on stairs and her actual stroller way are still to come.

| Trip | Ordinary walk | Stroller route | Google link |
|---|---|---|---|
| MACAM → Sud Kids (riverside, Av. Brasília 311) | 1,040 m over two footbridge staircases (`w98491671`, `w98491675`), as the author said | 1,578 m over the MAAT footbridge, no stairs in OSM, +3% / −4% | holds with 1 waypoint |
| Biblioteca de Alcântara → Piscina do Alvito | 757 m, +13% | 10,403 m, 137 min, through Monsanto | cannot be verified: the detour leaves the downloaded 2 m tiles |
| Let's Pastrami → Escola de Pedro Nunes | 1,465 m, +27% | 2,387 m, +14% on the 2 m model | "holds", but Google takes another way at the same +14% |

What the real trips exposed in the check itself:
- **Map matching our own route reported stairs it never used.** The stroller route Let's Pastrami → Pedro Nunes was reported with two short staircases (`w1566675914`, 3 steps; `w1566675916`, 2 steps); GraphHopper's route details show no steps. Our own routes now take their stairs from GraphHopper's `road_class` / `osm_way_id` details; matching stays for Google's lines only.
- **A link was called "holds" when our slope was unknown.** On the Alvito trip our route left the 2 m tiles, so the slope comparison was skipped and Google's direct +18% climb passed. A link now holds only when both slopes are known; otherwise the verdict is "cannot be verified".
- **The 8% limit and the 2 m measurement do not agree.** GraphHopper applies the limit to edge averages on a ~30 m grid, while the 2 m check takes the steepest 15 m stretch. Routes within the router's limit show +10% to +14% on the 2 m model, so the "above the uphill limit" flag fires on almost every hill trip. Which number matches what a parent feels needs her account of these streets.
- **The steepest stretch can sit at the destination itself.** The −26% on the MACAM trip is the first 15 m, from the museum point (inside the grounds) to the street.
- **Bridges look like cliffs on the 2 m terrain model.** It is bare earth, so a route over the MAAT footbridge showed +31% / −39%: the ground under the deck. Stretches on bridges, raised plazas and tunnels (OSM `bridge`, `tunnel` or a non-zero `layer`, within 8 m of the line) are now bridged with a straight line between the ground on either side (`data/lisbon-offground.geojson`). The stroller route then reads +3% / −4%.
- **Confirmed by the author:** the MAAT footbridge has a ramp and is fine with a stroller, so the stroller route MACAM → Sud Kids matches how she walks it. This is the first trip where the router's answer is confirmed on the ground.
- **The downloaded 2 m tiles stop short of Monsanto and western Belém.** Trips there need more DGT tiles.

## Measurement log

Raw observations from the session runs, kept so that later documents can cite them.

- Praça da Figueira → Castelo, coarse SRTM terrain, first waypoint method (points farthest from the ordinary walk): Google with 0 waypoints 1,357 m and 1 staircase; with 3 waypoints 1,710 m and 7 staircases; the first waypoint was about 35 m from the start.
- Same trip, proximity rule: the stroller route was flagged as using staircase `w731800499`, an 8 m metro entrance (`highway=steps`, `level=0;-1`) on the square; GraphHopper's route details showed no steps on that route. Map matching instead reported the single staircase the ordinary walk really used, `w244600206`.
- Calibration run (150 routes): of the staircases routes really used, none carried `indoor`, `level` or `conveying`; most false hits of the geometric rule did.
- DGT terrain in GraphHopper, ordinary walk Praça da Figueira → Castelo: elevation along the route rises from 10 m to 95 m.
- DGT terrain, Google route checks: Rossio → Praça Luís de Camões, Google with 0 waypoints 642 m, 4 staircases, steepest +50%; with 2 waypoints 3,235 m, no stairs, +10%. Praça do Comércio → Sé, Google with 0 waypoints 512 m, no stairs, +20%; with 2 waypoints 582 m, no stairs, +12%.
- Before `foot.json`'s encoded values were all listed, GraphHopper refused to start: "Encoded values missing: hike_rating, country, foot_road_access, mtb_rating".

## Still to do

- [x] 3 real trips from the author in `spike/routes.yaml` (points only).
- [ ] Her notes for them: where the stairs actually are and which way she walks with a stroller.
- [ ] DGT tiles for Monsanto and western Belém.
- [x] DGT MDT 2 m tiles downloaded and wired in (GraphHopper grid + 2 m slope check).
- [ ] Tune the slope thresholds on real trips.
- [x] Google Maps Platform key set up; the check runs (computeRoutes + map matching).
- [ ] For each real trip, check whether the link with ≤3 waypoints keeps Google on our route.
- [ ] The author taps each link inside Telegram and records whether the Google Maps app keeps the waypoints and draws the same route.
- [ ] Go / no-go decision.

## How to reproduce

See `spike/README.md`.
